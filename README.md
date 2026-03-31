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
| `HOMARR_TRANSPORT` | Transport mode | `stdio` |

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
