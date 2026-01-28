import os
import time
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from dotenv import load_dotenv, set_key

# Use explicit path for .env file relative to this file
ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=ENV_PATH)

APP_ID = os.getenv('INOREADER_APP_ID')
APP_KEY = os.getenv('INOREADER_APP_KEY')
REDIRECT_URI = os.getenv('INOREADER_REDIRECT_URI', 'http://localhost:8080/oauth/redirect')

# Global variables to store the results
auth_code = None
expected_state = None
callback_error = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default logging
        pass

    def do_GET(self):
        global auth_code, callback_error
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Check if it matches our redirect path
        redirect_path = urllib.parse.urlparse(REDIRECT_URI).path
        if parsed_path.path == redirect_path:
            query_params = urllib.parse.parse_qs(parsed_path.query)
            
            # Handle OAuth errors
            if 'error' in query_params:
                error = query_params['error'][0]
                desc = query_params.get('error_description', ['No description'])[0]
                callback_error = f"{error}: {desc}"
                
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(f"""
                <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: red;">Authentication Error</h1>
                    <p><b>Error:</b> {error}</p>
                    <p><b>Description:</b> {desc}</p>
                </body>
                </html>
                """.encode())
                return

            # CSRF State Validation
            state = query_params.get('state', [None])[0]
            if not state or state != expected_state:
                callback_error = "State mismatch or missing (possible CSRF attack)"
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Security error: State mismatch.")
                return

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
                # Do not print the actual code
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
        
        while auth_code is None and callback_error is None:
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
    try:
        response = requests.post(token_url, data=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
    
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
    expires_in_raw = tokens.get('expires_in')
    
    # Validate expires_in
    try:
        expires_in = int(expires_in_raw) if expires_in_raw is not None else 3600
    except (ValueError, TypeError):
        expires_in = 3600
    
    # Calculate expiry timestamp
    expires_at = int(time.time()) + expires_in
    
    # Update .env file
    # We use dotenv.set_key to update the file in place
    set_key(ENV_PATH, "INOREADER_ACCESS_TOKEN", access_token)
    set_key(ENV_PATH, "INOREADER_REFRESH_TOKEN", refresh_token)
    set_key(ENV_PATH, "INOREADER_TOKEN_EXPIRES", str(expires_at))
    
    print("Tokens saved successfully.")

def main():
    global auth_code, expected_state
    
    if not APP_ID or not APP_KEY:
        print("Error: INOREADER_APP_ID or INOREADER_APP_KEY not found in .env")
        return

    # 1. Construct Auth URL
    # Generate a random state string for security
    expected_state = os.urandom(16).hex()
    
    params = {
        'client_id': APP_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'read',
        'state': expected_state
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
    print("   If the redirect fails (e.g. site can't be reached), copy the 'code' AND 'state' parameters from the URL address bar.")
    
    # 3. Wait for code
    # We loop here to allow the user to interrupt or paste manually
    
    manual_code = input("\nPaste the 'code' here (or press Enter if auto-captured): ").strip()
    
    if callback_error:
        print(f"\nAuthentication Error: {callback_error}")
        return

    code_to_use = None
    if manual_code:
        manual_state = input("Paste the 'state' here: ").strip()
        if manual_state != expected_state:
            print("Security error: State mismatch. Possible CSRF or copy-paste error.")
            return
        code_to_use = manual_code
    else:
        # One last check if auth_code came in while user was pressing Enter
        if auth_code:
            code_to_use = auth_code
        else:
            print("No code provided and none captured. Exiting.")
            return

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
