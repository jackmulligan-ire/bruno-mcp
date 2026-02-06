# Bruno MCP

MCP server for Bruno API collections that executes requests via the Bruno CLI tool.

## Prerequisites

### 1. Install Bruno CLI

The Bruno CLI tool (`bru`) must be installed and available in your PATH.

1. Install Bruno CLI using npm 
  ```bash
  npm install -g @usebruno/cli
  ```

2. Verify installation:
   ```bash
   bru --version
   ```

### 2. Install Python Dependencies

Install the project dependencies using `uv`:

```bash
uv sync
```

This will create a virtual environment and install all required packages.

## Setup

### MCP Configuration

Configure the MCP server by adding an entry to your IDE. For Cursor, create or edit the configuration file at `~/.cursor/mcp.json` with the following:

```json
{
  "mcpServers": {
    "bruno-mcp": {
      "command": "/home/user/Projects/bruno-mcp/.venv/bin/python",
      "args": ["-m", "bruno_mcp"],
      "cwd": "/home/user/Projects/bruno-mcp",
      "env": {
        "BRUNO_COLLECTION_PATH": "/home/user/Documents/My API Collection",
        "PYTHONPATH": "/home/user/Projects/bruno-mcp/src"
      }
    }
  }
}
```

**Configuration Fields:**
- `command`: Path to the Python interpreter in your virtual environment (typically `.venv/bin/python` in the project directory)
- `args`: Command arguments to run the MCP server module
- `cwd`: Working directory (should be the project root directory)
- `env.BRUNO_COLLECTION_PATH`: Path to your Bruno collection directory
- `env.PYTHONPATH`: Path to the `src` directory containing the `bruno_mcp` package

After updating the configuration file, enable the server in your IDE's MCP settings.
