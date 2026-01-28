import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    INOREADER_APP_ID = os.getenv('INOREADER_APP_ID')
    INOREADER_APP_KEY = os.getenv('INOREADER_APP_KEY')
    
    # OAuth Tokens
    INOREADER_ACCESS_TOKEN = os.getenv('INOREADER_ACCESS_TOKEN')
    INOREADER_REFRESH_TOKEN = os.getenv('INOREADER_REFRESH_TOKEN')
    INOREADER_TOKEN_EXPIRES = os.getenv('INOREADER_TOKEN_EXPIRES')
    INOREADER_REDIRECT_URI = os.getenv('INOREADER_REDIRECT_URI')
    
    # API Base URL
    INOREADER_BASE_URL = 'https://www.inoreader.com/reader/api/0'
    TOKEN_URL = 'https://www.inoreader.com/oauth2/token'
    
    # Cache settings
    CACHE_TTL = 300  # 5 minutes
    
    # Request settings
    REQUEST_TIMEOUT = 10
    MAX_ARTICLES_PER_REQUEST = 50
    
    @classmethod
    def validate(cls):
        # We definitely need App ID and Key
        required = ['INOREADER_APP_ID', 'INOREADER_APP_KEY']
        missing = [var for var in required if not getattr(cls, var)]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
            
        # We don't strictly validate tokens here because they might be loaded/refreshed
        # or the user might run the setup script to get them.
        # But for the client to work, we will need them.
        return True
