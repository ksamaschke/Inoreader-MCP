# Inoreader MCP Integration

An MCP (Model Context Protocol) server that integrates Inoreader with Claude Desktop, enabling intelligent RSS feed management and analysis.

## Features

### Feed and Article Management
- **List feeds**: View all your subscribed feeds
- **List articles**: Browse articles with filters (unread, by feed, by period)
- **Read content**: Access full content of specific articles
- **Mark as read**: Mark articles individually or in bulk

### Search and Analysis
- **Search articles**: Search for keywords across your feeds
- **Summarize articles**: Generate summaries of individual articles
- **Analyze multiple articles**: 
  - Consolidated summaries
  - Trend analysis
  - Sentiment analysis
  - Keyword extraction
- **Statistics**: View unread article counters

## Installation

### Prerequisites

- Python 3.9+
- An Inoreader account
- Registered Inoreader Application (for OAuth)

### 1. Clone and Install

```bash
git clone <repository-url>
cd inoreader_mcp
pip install -r requirements.txt
```

### 2. Configure Credentials & Authenticate (OAuth)

This MCP server uses OAuth 2.0 to securely access your Inoreader account.

1.  **Create an App**: Go to [Inoreader Developers](https://www.inoreader.com/developers/) and create a new application.
    *   **Scope**: Read only
    *   **Redirect URI**: `http://localhost:8080/oauth/redirect`
2.  **Create `.env`**: Copy `.env.example` (if available) or create a new `.env` file:
    ```bash
    INOREADER_APP_ID=your_app_id
    INOREADER_APP_KEY=your_app_key
    INOREADER_REDIRECT_URI=http://localhost:8080/oauth/redirect
    ```
3.  **Run Setup Script**:
    ```bash
    python oauth_setup.py
    ```
    Follow the on-screen instructions to authorize the app in your browser. The script will automatically capture the access tokens and save them to `.env`.

### 3. Configure in Claude Desktop

Add to Claude Desktop's configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "inoreader": {
      "command": "python",
      "args": ["/full/path/to/inoreader_mcp/main.py"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

*Note: The environment variables are loaded from the `.env` file in the directory, so you don't need to duplicate them in the Claude config.*

## Usage

After configuration, restart Claude Desktop. Commands will be available in natural language:

### Example commands

**List feeds:**
- "List my feeds"
- "What feeds do I follow?"

**List articles:**
- "Show the last 20 unread articles"
- "What unread articles do I have from TechCrunch?"
- "Show articles from the last 3 days"

**Search:**
- "Search articles about artificial intelligence"
- "Find Python articles from the last 7 days"

**Read and mark:**
- "Read article [ID]"
- "Mark all articles from feed X as read"

**Analysis:**
- "Summarize the top 5 AI articles this week"
- "Analyze trends in my feeds today"
- "What's the overall sentiment of economy articles?"
- "Extract keywords from unread articles"

**Statistics:**
- "How many unread articles do I have?"
- "Show my feed statistics"

## Project Structure

```
inoreader_mcp/
├── main.py              # Main MCP server
├── inoreader_client.py  # Inoreader API client
├── tools.py             # MCP tools implementation
├── config.py            # Configuration and credentials
├── utils.py             # Helper functions
├── requirements.txt     # Python dependencies
├── oauth_setup.py       # OAuth setup script
└── README.md            # This file
```

## Troubleshooting

**Authentication error:**
- Run `python oauth_setup.py` again to refresh credentials.
- Verify App ID and Key in `.env`.

**Request timeouts:**
- Inoreader API may be slow
- Try reducing the number of requested articles

## License

MIT License - see LICENSE file for details.
