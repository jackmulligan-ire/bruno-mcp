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

### 2. Install uv (recommended)

[uv](https://docs.astral.sh/uv/) is the recommended way to install and run bruno-mcp. It includes `uvx`, which handles package installation and execution automatically.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setup

### MCP Configuration (uvx)

Configure the MCP server by adding an entry to your IDE. For Cursor, create or edit the configuration file at `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "bruno-mcp": {
      "command": "uvx",
      "args": ["bruno-mcp"],
      "env": {
        "BRUNO_COLLECTION_PATH": "/path/to/your/bruno/collection"
      }
    }
  }
}
```

The only configuration required is `BRUNO_COLLECTION_PATH`, which should point to your Bruno collection directory. To load multiple collections, separate paths with `:` (Unix/Mac) or `;` (Windows), e.g. `BRUNO_COLLECTION_PATH="/path/to/collection1:/path/to/collection2"`.

### Alternative: Run Server Manually

If you prefer not to use `uvx`, you can clone the repository and run the server directly:

```bash
git clone https://github.com/jackmulligan-ire/bruno-mcp.git
cd bruno-mcp
uv sync
```

Then configure your MCP client with the full paths:

```json
{
  "mcpServers": {
    "bruno-mcp": {
      "command": "/path/to/bruno-mcp/.venv/bin/python",
      "args": ["-m", "bruno_mcp"],
      "cwd": "/path/to/bruno-mcp",
      "env": {
        "BRUNO_COLLECTION_PATH": "/path/to/your/bruno/collection",
        "PYTHONPATH": "/path/to/bruno-mcp/src"
      }
    }
  }
}
```

After updating the configuration file, enable the server in your IDE's MCP settings.

## Usage Notes

### Multiple Collections

When `BRUNO_COLLECTION_PATH` contains multiple paths (separated by `:` on Unix/Mac or `;` on Windows), the server loads all collections at startup. The first path is the initial active collection. Use the `list_collections` tool or `bruno://collections` resource to see available collections, and `set_active_collection` to switch which collection tools operate on.

### Variable Overrides

The `run_request_by_id` tool accepts a `variable_overrides` parameter that maps to the Bruno CLI's `--env-var` flag. This allows you to substitute `{{variable}}` placeholders in your `.bru` files at runtime.

**Important limitation:** `--env-var` can only override variables that are already defined in a Bruno environment. It cannot introduce new variables, or replace the values of pre-request and post-request variables. If a variable is not defined in any environment, the override will be silently ignored and the placeholder will resolve to an empty string.

To use variable overrides:

1. Define the variable in a Bruno environment file (even as an empty string):
   ```
   vars {
     postId:
   }
   ```
2. Pass `variable_overrides` when calling the tool. For example, if you have a `.bru` file with the URL `https://api.example.com/posts/{{postId}}` and an environment called `dev` that defines `postId`, you would call:
   - `variable_overrides`: `{"postId": "42"}`