import os
import sys
import json
import time
import socket
import threading
import webbrowser
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from dotenv import load_dotenv, set_key

# Load environment variables
load_dotenv()

APP_ID = os.getenv('INOREADER_APP_ID')
APP_KEY = os.getenv('INOREADER_APP_KEY')
REDIRECT_URI = os.getenv('INOREADER_REDIRECT_URI', 'http://localhost:8080/oauth/redirect')
ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')

# Global variable to store the code
auth_code = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default logging
        pass

    def do_GET(self):
        global auth_code
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Check if it matches our redirect path
        redirect_path = urllib.parse.urlparse(REDIRECT_URI).path
        if parsed_path.path == redirect_path:
            query_params = urllib.parse.parse_qs(parsed_path.query)
            
            if 'code' in query_params:
                auth_code = query_params['code'][0]
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: green;">Authentication Successful!</h1>
                    <p>The authorization code has been captured.</p>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
                """)
                print("\n[Server] Authorization code captured successfully!")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing 'code' parameter.")
        else:
            self.send_response(404)
            self.end_headers()

def start_server():
    try:
        # Extract port from REDIRECT_URI
        port = 8080
        try:
            parsed = urllib.parse.urlparse(REDIRECT_URI)
            if parsed.port:
                port = parsed.port
        except:
            pass
            
        server = HTTPServer(('localhost', port), OAuthCallbackHandler)
        # Set a timeout so handle_request doesn't block forever
        server.timeout = 1
        
        print(f"[Server] Listening on port {port} for callback...")
        
        while auth_code is None:
            server.handle_request()
            
    except Exception as e:
        print(f"\n[Server] Warning: Could not start local server: {e}")

def get_tokens(code):
    token_url = 'https://www.inoreader.com/oauth2/token'
    payload = {
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': APP_ID,
        'client_secret': APP_KEY,
        'grant_type': 'authorization_code',
        'scope': 'read'
    }
    
    print("Exchanging code for tokens...")
    response = requests.post(token_url, data=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error getting tokens: {response.status_code}")
        print(response.text)
        return None

def save_tokens(tokens):
    print("Saving tokens to .env...")
    
    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')
    expires_in = tokens.get('expires_in')
    
    # Calculate expiry timestamp
    expires_at = int(time.time()) + int(expires_in)
    
    # Update .env file
    # We use dotenv.set_key to update the file in place
    set_key(ENV_PATH, "INOREADER_ACCESS_TOKEN", access_token)
    set_key(ENV_PATH, "INOREADER_REFRESH_TOKEN", refresh_token)
    set_key(ENV_PATH, "INOREADER_TOKEN_EXPIRES", str(expires_at))
    
    print("Tokens saved successfully.")

def main():
    global auth_code
    
    if not APP_ID or not APP_KEY:
        print("Error: INOREADER_APP_ID or INOREADER_APP_KEY not found in .env")
        return

    # 1. Construct Auth URL
    # Generate a random state string for security (optional but good practice)
    state = os.urandom(16).hex()
    
    params = {
        'client_id': APP_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'read',
        'state': state
    }
    
    auth_url = f"https://www.inoreader.com/oauth2/auth?{urllib.parse.urlencode(params)}"
    
    print("\n=== Inoreader OAuth Setup ===\n")
    print(f"1. Open this URL in your browser:\n\n{auth_url}\n")
    
    # 2. Start Server in Thread
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()
    
    print("2. Approve the application in Inoreader.")
    print("3. If redirected to localhost successfully, the code will be captured automatically.")
    print("   If the redirect fails (e.g. site can't be reached), copy the 'code' parameter from the URL address bar.")
    
    # 3. Wait for code
    # We loop here to allow the user to interrupt or paste manually
    
    manual_code = input("\nPaste the 'code' here (or press Enter if auto-captured): ").strip()
    
    code_to_use = auth_code if auth_code else manual_code
    
    if not code_to_use:
        # One last check if auth_code came in while user was pressing Enter
        if auth_code:
            code_to_use = auth_code
        else:
            print("No code provided. Exiting.")
            return

    print(f"\nUsing code: {code_to_use[:10]}...")
    
    # 4. Exchange code for tokens
    tokens = get_tokens(code_to_use)
    
    if tokens:
        # 5. Save tokens
        save_tokens(tokens)
        print("\nSetup complete! You can now use the Inoreader MCP server.")
    else:
        print("\nSetup failed.")

if __name__ == "__main__":
    main()
