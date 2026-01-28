import aiohttp
import asyncio
import base64
import time
import os
from typing import Dict, List, Optional, Any
from cachetools import TTLCache
from dotenv import load_dotenv, set_key
from config import Config

# Use explicit path for .env file relative to this file
ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=ENV_PATH)

class InoreaderClient:
    def __init__(self):
        self.base_url = Config.INOREADER_BASE_URL
        self.app_id = Config.INOREADER_APP_ID
        self.app_key = Config.INOREADER_APP_KEY
        
        # Token state
        self.access_token = Config.INOREADER_ACCESS_TOKEN
        self.refresh_token = Config.INOREADER_REFRESH_TOKEN
        try:
            self.token_expires = float(Config.INOREADER_TOKEN_EXPIRES or 0)
        except ValueError:
            self.token_expires = 0
            
        self.cache = TTLCache(maxsize=100, ttl=Config.CACHE_TTL)
        self.session = None
        self.env_path = os.path.join(os.path.dirname(__file__), '.env')
        
    async def __aenter__(self):
        # Create session with default SSL context (system certs)
        self.session = aiohttp.ClientSession()
        
        # Verify we have tokens
        if not self.access_token or not self.refresh_token:
            raise Exception("OAuth tokens missing. Please run oauth_setup.py first.")
            
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _ensure_token_valid(self):
        """Check if token is expired and refresh if necessary"""
        # Refresh if expired or expiring in next 60 seconds
        if time.time() > (self.token_expires - 60):
            await self._refresh_access_token()

    async def _refresh_access_token(self):
        """Refresh the OAuth access token"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Refreshing access token...")
        
        params = {
            'client_id': self.app_id,
            'client_secret': self.app_key,
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        
        # We use a separate request context here or the existing session
        # Using existing session is fine
        try:
            async with self.session.post(Config.TOKEN_URL, data=params, timeout=Config.REQUEST_TIMEOUT) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    error_msg = f"Token refresh failed: {resp.status} - {text}. Action required: refresh failed; re-run oauth_setup.py"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                data = await resp.json()
                
                new_access_token = data.get('access_token')
                if not new_access_token:
                    error_msg = "Token refresh failed: access_token missing in response. Action required: refresh failed; re-run oauth_setup.py"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                self.access_token = new_access_token
                self.refresh_token = data.get('refresh_token') # Inoreader rotates refresh tokens usually? Check docs. 
                # If a new refresh token is provided, use it. If not, keep old one.
                # RFC 6749: "The authorization server MAY issue a new refresh token".
                if not self.refresh_token:
                    # Keep existing if not returned
                    self.refresh_token = params['refresh_token']
                
                expires_in = data.get('expires_in', 3600)
                self.token_expires = time.time() + int(expires_in)
                
                logger.info("Token refreshed successfully")
                
                # Persist to .env
                self._save_tokens_to_env()
                
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            raise

    def _save_tokens_to_env(self):
        """Save updated tokens to .env file"""
        try:
            set_key(self.env_path, "INOREADER_ACCESS_TOKEN", self.access_token)
            set_key(self.env_path, "INOREADER_REFRESH_TOKEN", self.refresh_token)
            set_key(self.env_path, "INOREADER_TOKEN_EXPIRES", str(int(self.token_expires)))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to save tokens to .env: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'AppId': self.app_id,
            'AppKey': self.app_key,
        }
        
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Any:
        """Make an API request"""
        
        # Ensure token is valid before request
        await self._ensure_token_valid()
        
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers()
        
        timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Making {method} request to {url}")
        
        async with self.session.request(
            method, url, params=params, data=data, headers=headers, timeout=timeout
        ) as resp:
            # Handle 401 explicitly (Token expired but local check didn't catch it?)
            if resp.status == 401:
                logger.warning("Got 401, forcing token refresh...")
                # Force expiry to trigger refresh
                self.token_expires = 0
                await self._ensure_token_valid()
                # Retry request
                headers = self._get_headers()
                async with self.session.request(
                    method, url, params=params, data=data, headers=headers, timeout=timeout
                ) as resp_retry:
                    return await self._process_response(resp_retry)
            
            return await self._process_response(resp)

    async def _process_response(self, resp):
        import logging
        logger = logging.getLogger(__name__)
        
        if resp.status != 200:
            text = await resp.text()
            logger.error(f"API error response: {text}")
            raise Exception(f"API request failed: {resp.status} - {text}")
        
        content_type = resp.headers.get('Content-Type', '')
        
        if 'application/json' in content_type:
            return await resp.json()
        else:
            text = await resp.text()
            return text
                
    async def get_subscription_list(self) -> List[Dict]:
        """Get list of subscribed feeds"""
        cache_key = 'subscription_list'
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        result = await self._request('GET', 'subscription/list')
        subscriptions = result.get('subscriptions', [])
        
        self.cache[cache_key] = subscriptions
        return subscriptions
        
    async def get_stream_contents(self, stream_id: Optional[str] = None, 
                                 count: int = 50, 
                                 exclude_read: bool = True,
                                 newer_than: Optional[int] = None) -> Dict:
        """Get articles from a stream"""
        params = {
            'n': min(count, Config.MAX_ARTICLES_PER_REQUEST),
            'output': 'json'
        }
        
        if exclude_read:
            params['xt'] = 'user/-/state/com.google/read'
            
        if newer_than:
            params['ot'] = newer_than
            
        endpoint = f"stream/contents/{stream_id}" if stream_id else "stream/contents/user/-/state/com.google/reading-list"
        
        result = await self._request('GET', endpoint, params=params)
        
        # Handle string responses (usually errors)
        if isinstance(result, str):
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"API returned string instead of JSON: {result[:500]}")
            
            # Try to parse as JSON if it looks like JSON
            if result.strip().startswith('{'):
                try:
                    import json
                    return json.loads(result)
                except json.JSONDecodeError:
                    pass
            
            # Return empty structure if we can't parse
            return {'items': []}
            
        return result
        
    async def get_stream_item_contents(self, item_ids: List[str]) -> Dict:
        """Get full content for specific items"""
        if not item_ids:
            return {'items': []}
            
        data = {
            'i': item_ids
        }
        
        return await self._request('POST', 'stream/items/contents', data=data)
        
    async def mark_as_read(self, item_ids: List[str]) -> bool:
        """Mark items as read"""
        if not item_ids:
            return True
            
        data = {
            'i': item_ids,
            'a': 'user/-/state/com.google/read'
        }
        
        result = await self._request('POST', 'edit-tag', data=data)
        return result == 'OK'
        
    async def search(self, query: str, count: int = 50, newer_than: Optional[int] = None) -> Dict:
        """Search articles"""
        params = {
            'q': query,
            'n': min(count, Config.MAX_ARTICLES_PER_REQUEST),
            'output': 'json'
        }
        
        if newer_than:
            params['ot'] = newer_than
            
        result = await self._request('GET', 'stream/contents/user/-/state/com.google/search', params=params)
        
        # Handle string responses (usually errors)
        if isinstance(result, str):
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Search API returned string: {result[:500]}")
            
            # Try to parse as JSON if it looks like JSON
            if result.strip().startswith('{'):
                try:
                    import json
                    return json.loads(result)
                except json.JSONDecodeError:
                    pass
            
            # Return empty structure if we can't parse
            return {'items': []}
            
        return result
        
    async def get_unread_count(self) -> Dict:
        """Get unread counts for all feeds"""
        result = await self._request('GET', 'unread-count')
        return result.get('unreadcounts', [])
