"""Homarr MCP server — board, app, group, and user management."""

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from src.config import mask_credential, settings
from src.homarr_client import HomarrClient

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# ── Response field filtering ──

RESPONSE_FIELDS: dict[str, dict[str, Optional[list[str]]]] = {
    "board": {
        "minimal": ["id", "name", "isPublic"],
        "standard": ["id", "name", "isPublic", "logoImageUrl", "creator", "isHome", "isMobileHome"],
        "full": None,
    },
    "board_detail": {
        "minimal": ["id", "name", "isPublic", "sections", "items"],
        "standard": [
            "id",
            "name",
            "isPublic",
            "creatorId",
            "logoImageUrl",
            "primaryColor",
            "secondaryColor",
            "opacity",
            "sections",
            "items",
            "layouts",
        ],
        "full": None,
    },
    "app": {
        "minimal": ["id", "name", "href"],
        "standard": ["id", "name", "description", "iconUrl", "href", "pingUrl"],
        "full": None,
    },
    "group": {
        "minimal": ["id", "name"],
        "standard": ["id", "name", "ownerId", "homeBoardId", "mobileHomeBoardId", "members"],
        "full": None,
    },
    "user": {
        "minimal": ["id", "name"],
        "standard": ["id", "name", "email", "emailVerified", "image"],
        "full": None,
    },
}

VALID_VERBOSITY_LEVELS = {"minimal", "standard", "full"}


def _filter_response(response: Any, resource_type: str, verbosity: str = "standard") -> Any:
    """Filter response fields based on verbosity level."""
    if response is None:
        return None

    if verbosity not in VALID_VERBOSITY_LEVELS:
        logger.warning(f"Invalid verbosity '{verbosity}', using 'standard'")
        verbosity = "standard"

    if verbosity == "full":
        return response

    if resource_type not in RESPONSE_FIELDS:
        return response

    fields = RESPONSE_FIELDS[resource_type].get(verbosity)
    if fields is None:
        return response

    field_set = set(fields)

    def filter_dict(d: dict) -> dict:
        return {k: v for k, v in d.items() if k in field_set}

    if isinstance(response, list):
        return [filter_dict(item) for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        return filter_dict(response)
    return response


# ── Client accessor ──

_client: Optional[HomarrClient] = None


def _get_client() -> HomarrClient:
    """Get the global Homarr client instance."""
    if _client is None:
        raise RuntimeError(
            "Homarr client not initialized. Ensure HOMARR_URL and HOMARR_API_KEY are set."
        )
    return _client


# ── Server lifecycle ──


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Initialize Homarr client on startup, cleanup on shutdown."""
    global _client

    if not settings.has_api_key:
        logger.error("HOMARR_API_KEY is required. Set it in .env or environment.")
        raise ValueError("HOMARR_API_KEY is required but not set")

    masked_key = mask_credential(settings.get_api_key_value())
    logger.info(f"Connecting to Homarr at {settings.url} (key: {masked_key})")

    client = HomarrClient(
        base_url=settings.url,
        api_key=settings.get_api_key_value(),
    )

    connected = await client.check_connection()
    if connected:
        logger.info("Homarr connection verified.")
    else:
        logger.warning("Could not verify Homarr connection. Tools may fail.")

    _client = client

    try:
        yield
    finally:
        logger.info("Shutting down Homarr MCP server...")
        await client.close()
        _client = None


# ── MCP Server ──

_mcp_port_str = os.environ.get("MCP_PORT", "8000")
try:
    _mcp_port = int(_mcp_port_str)
except ValueError:
    _mcp_port = 8000

mcp = FastMCP(
    "Homarr MCP",
    lifespan=server_lifespan,
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=_mcp_port,
)


# ── Board tools ──


@mcp.tool(
    "list_boards",
    description="List all Homarr boards. Returns board names, IDs, and visibility status.",
)
async def list_boards(verbosity: str = "standard") -> list[dict]:
    """List all boards."""
    client = _get_client()
    boards = await client.list_boards()
    return _filter_response(boards, "board", verbosity)


@mcp.tool(
    "get_board",
    description=(
        "Get a board by name with full details including sections, items, and layouts. "
        "Use list_boards first to see available board names."
    ),
)
async def get_board(name: str, verbosity: str = "standard") -> dict:
    """Get a board by name."""
    client = _get_client()
    board = await client.get_board(name)
    return _filter_response(board, "board_detail", verbosity)


@mcp.tool(
    "create_board",
    description="Create a new Homarr board with the given name.",
)
async def create_board(name: str) -> dict:
    """Create a new board."""
    client = _get_client()
    result = await client.create_board(name)
    logger.info(f"Created board '{name}'")
    return result


@mcp.tool(
    "duplicate_board",
    description="Duplicate an existing board by its ID. Use list_boards to find the board ID.",
)
async def duplicate_board(board_id: str) -> dict:
    """Duplicate a board."""
    client = _get_client()
    result = await client.duplicate_board(board_id)
    logger.info(f"Duplicated board {board_id}")
    return result


@mcp.tool(
    "rename_board",
    description="Rename a board. Requires the board ID and the new name.",
)
async def rename_board(board_id: str, new_name: str) -> dict:
    """Rename a board."""
    client = _get_client()
    result = await client.rename_board(board_id, new_name)
    logger.info(f"Renamed board {board_id} to '{new_name}'")
    return result


@mcp.tool(
    "delete_board",
    description="Delete a board by ID. This action is irreversible.",
)
async def delete_board(board_id: str) -> dict:
    """Delete a board."""
    client = _get_client()
    result = await client.delete_board(board_id)
    logger.info(f"Deleted board {board_id}")
    return {"success": True, "deleted_id": board_id, "result": result}


@mcp.tool(
    "change_board_visibility",
    description="Change board visibility. Visibility must be 'public' or 'private'.",
)
async def change_board_visibility(board_id: str, visibility: str) -> dict:
    """Change board visibility."""
    if visibility not in ("public", "private"):
        return {"error": "visibility must be 'public' or 'private'"}
    client = _get_client()
    result = await client.change_board_visibility(board_id, visibility)
    logger.info(f"Changed board {board_id} visibility to '{visibility}'")
    return result


@mcp.tool(
    "get_board_permissions",
    description="Get user and group permissions for a board.",
)
async def get_board_permissions(board_id: str) -> dict:
    """Get board permissions."""
    client = _get_client()
    return await client.get_board_permissions(board_id)


# ── App tools ──


@mcp.tool(
    "list_apps",
    description="List all apps/bookmarks registered in Homarr.",
)
async def list_apps(verbosity: str = "standard") -> list[dict]:
    """List all apps."""
    client = _get_client()
    apps = await client.list_apps()
    return _filter_response(apps, "app", verbosity)


@mcp.tool(
    "get_app",
    description="Get an app by its ID. Use list_apps to find app IDs.",
)
async def get_app(app_id: str, verbosity: str = "standard") -> dict:
    """Get an app by ID."""
    client = _get_client()
    app = await client.get_app(app_id)
    return _filter_response(app, "app", verbosity)


@mcp.tool(
    "create_app",
    description=(
        "Create a new app/bookmark in Homarr. "
        "Requires name and href (URL). Optional: description, icon_url, ping_url."
    ),
)
async def create_app(
    name: str,
    href: str,
    description: Optional[str] = None,
    icon_url: Optional[str] = None,
    ping_url: Optional[str] = None,
) -> dict:
    """Create a new app."""
    client = _get_client()
    result = await client.create_app(
        name=name,
        href=href,
        description=description,
        icon_url=icon_url,
        ping_url=ping_url,
    )
    logger.info(f"Created app '{name}' -> {href}")
    return result


@mcp.tool(
    "update_app",
    description=(
        "Update an existing app. Pass the app_id and any fields to change: "
        "name, href, description, iconUrl, pingUrl."
    ),
)
async def update_app(
    app_id: str,
    name: Optional[str] = None,
    href: Optional[str] = None,
    description: Optional[str] = None,
    icon_url: Optional[str] = None,
    ping_url: Optional[str] = None,
) -> dict:
    """Update an app."""
    kwargs: dict[str, Any] = {}
    if name is not None:
        kwargs["name"] = name
    if href is not None:
        kwargs["href"] = href
    if description is not None:
        kwargs["description"] = description
    if icon_url is not None:
        kwargs["iconUrl"] = icon_url
    if ping_url is not None:
        kwargs["pingUrl"] = ping_url

    if not kwargs:
        return {"error": "No fields to update"}

    client = _get_client()
    result = await client.update_app(app_id, **kwargs)
    logger.info(f"Updated app {app_id}: {list(kwargs.keys())}")
    return result


@mcp.tool(
    "delete_app",
    description="Delete an app by ID. This action is irreversible.",
)
async def delete_app(app_id: str) -> dict:
    """Delete an app."""
    client = _get_client()
    result = await client.delete_app(app_id)
    logger.info(f"Deleted app {app_id}")
    return {"success": True, "deleted_id": app_id, "result": result}


# ── Group tools ──


@mcp.tool(
    "list_groups",
    description="List all groups with their members.",
)
async def list_groups(verbosity: str = "standard") -> list[dict]:
    """List all groups."""
    client = _get_client()
    groups = await client.list_groups()
    return _filter_response(groups, "group", verbosity)


@mcp.tool(
    "get_group",
    description="Get a group by ID with members and permissions.",
)
async def get_group(group_id: str, verbosity: str = "standard") -> dict:
    """Get a group by ID."""
    client = _get_client()
    group = await client.get_group(group_id)
    return _filter_response(group, "group", verbosity)


@mcp.tool(
    "add_group_member",
    description="Add a user to a group. Requires group_id and user_id.",
)
async def add_group_member(group_id: str, user_id: str) -> dict:
    """Add a user to a group."""
    client = _get_client()
    result = await client.add_group_member(group_id, user_id)
    logger.info(f"Added user {user_id} to group {group_id}")
    return {"success": True, "group_id": group_id, "user_id": user_id, "result": result}


@mcp.tool(
    "remove_group_member",
    description="Remove a user from a group. Requires group_id and user_id.",
)
async def remove_group_member(group_id: str, user_id: str) -> dict:
    """Remove a user from a group."""
    client = _get_client()
    result = await client.remove_group_member(group_id, user_id)
    logger.info(f"Removed user {user_id} from group {group_id}")
    return {"success": True, "group_id": group_id, "user_id": user_id, "result": result}


# ── User tools ──


@mcp.tool(
    "list_users",
    description="List all users in the Homarr instance.",
)
async def list_users(verbosity: str = "standard") -> list[dict]:
    """List all users."""
    client = _get_client()
    users = await client.list_users()
    return _filter_response(users, "user", verbosity)


@mcp.tool(
    "search_users",
    description="Search users by name or email. Returns matching users.",
)
async def search_users(query: str, limit: int = 10, verbosity: str = "standard") -> list[dict]:
    """Search users."""
    client = _get_client()
    users = await client.search_users(query, limit)
    return _filter_response(users, "user", verbosity)


# ── Transport resolution ──

VALID_TRANSPORTS = ("stdio", "sse", "streamable-http")


def _resolve_transport(argv: list[str] | None = None, env: dict[str, str] | None = None) -> str:
    """Determine transport from CLI flags or env var."""
    if argv is None:
        argv = sys.argv
    if env is None:
        env = dict(os.environ)

    if "--sse" in argv:
        return "sse"
    if "--streamable-http" in argv:
        return "streamable-http"

    env_transport = env.get("HOMARR_TRANSPORT", "").lower()
    if env_transport in VALID_TRANSPORTS:
        return env_transport
    return "stdio"


if __name__ == "__main__":
    transport = _resolve_transport()
    logger.info(f"Starting Homarr MCP server with {transport} transport")
    mcp.run(transport=transport)
