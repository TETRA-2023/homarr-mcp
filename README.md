# homarr-mcp

MCP server for [Homarr](https://homarr.dev) dashboard management. Manage boards, apps, groups, and users programmatically via the Model Context Protocol.

## Features

- **Boards**: List, create, duplicate, rename, delete, change visibility, view permissions
- **Apps**: List, get, create, update, delete app tiles/bookmarks
- **Groups**: List, get, add/remove members
- **Users**: List, search

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A running Homarr instance with an API key

### Installation

```bash
git clone https://github.com/TETRA-2023/homarr-mcp.git
cd homarr-mcp
uv sync
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your Homarr URL and API key
```

Create an API key in Homarr: **Management > Tools > API Keys**

| Variable | Description | Default |
|----------|-------------|---------|
| `HOMARR_URL` | Homarr instance URL | `http://localhost:7575` |
| `HOMARR_API_KEY` | API key (`<id>.<token>` format) | *required* |
| `HOMARR_TRANSPORT` | Transport mode (`stdio`, `sse`, `streamable-http`) | `stdio` |
| `MCP_HOST` | Bind address for HTTP transports | `127.0.0.1` |
| `MCP_PORT` | Listen port for HTTP transports | `8000` |
| `MCP_BEARER_TOKEN` | Optional bearer token enforced on HTTP transports (no-op for stdio) | *unset* |

## Usage

### stdio (Claude Code / local)

```bash
uv run python src/server.py
```

### streamable-http (Docker / remote)

```bash
uv run python src/server.py --streamable-http
```

### Claude Code configuration

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "homarr": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/homarr-mcp", "python", "src/server.py"],
      "env": {
        "HOMARR_URL": "https://your-homarr-instance.com",
        "HOMARR_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### Docker

```bash
docker build -t homarr-mcp .
docker run --env-file .env homarr-mcp --streamable-http
```

### Deployment behind an HTTP gateway

When fronting the wrapper with a gateway (LiteLLM, Kong, NGINX, etc.) over a
shared network, set `MCP_BEARER_TOKEN` to a random secret. The wrapper will
then reject any HTTP request that does not present a matching
`Authorization: Bearer <token>` header.

```bash
export MCP_BEARER_TOKEN="$(openssl rand -hex 32)"
export HOMARR_TRANSPORT=streamable-http
export MCP_HOST=0.0.0.0   # bind to all interfaces inside the container
uv run python src/server.py
```

Clients pass the token through the standard Bearer scheme. Example using a
generic MCP client:

```http
POST /mcp HTTP/1.1
Authorization: Bearer <your_token>
Content-Type: application/json
Accept: application/json, text/event-stream

{"jsonrpc": "2.0", "method": "initialize", ...}
```

Notes:
- `MCP_BEARER_TOKEN` is **transport-aware** — it has no effect when
  `HOMARR_TRANSPORT=stdio` (which has no HTTP layer). Existing stdio
  consumers keep working untouched.
- The `Bearer` scheme name is matched case-insensitively (RFC 7235 §2.1);
  the token itself is compared byte-for-byte with `secrets.compare_digest`
  for constant-time defence against timing oracles.
- Both 401 paths (missing header, wrong token) emit the same body so a
  client cannot distinguish them.
- Pair the bearer with TLS at the gateway so the token is not exposed on
  the wire.
- To exempt health/probe paths from auth, instantiate the middleware with
  `skip_paths=("/healthz",)`. There is no public env-var hook yet — add a
  custom entry point if you need this in production.

## Tools Reference

### Boards

| Tool | Description |
|------|-------------|
| `list_boards` | List all boards |
| `get_board` | Get board by name (with sections, items, layouts) |
| `create_board` | Create a new board |
| `duplicate_board` | Duplicate a board by ID |
| `rename_board` | Rename a board |
| `delete_board` | Delete a board |
| `change_board_visibility` | Set board to public or private |
| `get_board_permissions` | View user/group permissions |

### Apps

| Tool | Description |
|------|-------------|
| `list_apps` | List all apps/bookmarks |
| `get_app` | Get app by ID |
| `create_app` | Create app (name, href, description, icon_url, ping_url) |
| `update_app` | Update app fields |
| `delete_app` | Delete an app |

### Groups

| Tool | Description |
|------|-------------|
| `list_groups` | List all groups with members |
| `get_group` | Get group by ID |
| `add_group_member` | Add user to group |
| `remove_group_member` | Remove user from group |

### Users

| Tool | Description |
|------|-------------|
| `list_users` | List all users |
| `search_users` | Search users by name/email |

All query tools support a `verbosity` parameter: `minimal`, `standard` (default), or `full`.

## Development

```bash
# Install dev dependencies
uv sync --all-extras --dev

# Run tests
uv run pytest tests/test_server.py -v

# Lint
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Pre-commit hooks
uv run pre-commit install
```

## License

MIT
