"""Homarr tRPC API client."""

import json
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class HomarrAPIError(Exception):
    """Raised when the Homarr API returns an error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class HomarrClient:
    """Async client for Homarr's tRPC API.

    All Homarr API calls go through tRPC:
    - Queries: GET /api/trpc/{procedure}?input={json}
    - Mutations: POST /api/trpc/{procedure} with JSON body
    - Auth: ApiKey header with <id>.<token> format
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"ApiKey": api_key},
            timeout=30.0,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    def _parse_response(self, response: httpx.Response) -> Any:
        """Parse tRPC response, unwrapping the nested structure.

        tRPC responses are nested as: {"result": {"data": {"json": <actual_data>}}}
        tRPC errors are nested as: {"error": {"json": {"message": "...", "data": {...}}}}
        """
        if response.status_code == 401:
            raise HomarrAPIError("Unauthorized: invalid or missing API key", 401)
        if response.status_code == 403:
            raise HomarrAPIError("Forbidden: insufficient permissions", 403)
        if response.status_code == 404:
            raise HomarrAPIError("Not found", 404)

        data = response.json()

        # Handle tRPC error responses (400, 500, etc.)
        if "error" in data:
            error_json = data["error"].get("json", {})
            message = error_json.get("message", "Unknown tRPC error")
            code = error_json.get("data", {}).get("code", "UNKNOWN")
            raise HomarrAPIError(f"{code}: {message}", response.status_code)

        response.raise_for_status()

        # Unwrap tRPC response: result.data.json -> result.data -> raw
        result = data.get("result", data)
        if isinstance(result, dict):
            result_data = result.get("data", result)
            if isinstance(result_data, dict) and "json" in result_data:
                return result_data["json"]
            return result_data
        return result

    async def _query(self, procedure: str, input_data: Optional[dict] = None) -> Any:
        """Execute a tRPC query (GET request)."""
        url = f"/api/trpc/{procedure}"
        params = {}
        if input_data is not None:
            params["input"] = json.dumps({"json": input_data})
        logger.debug(f"tRPC query: {procedure}")
        response = await self._client.get(url, params=params)
        return self._parse_response(response)

    async def _mutate(self, procedure: str, input_data: Optional[dict] = None) -> Any:
        """Execute a tRPC mutation (POST request)."""
        url = f"/api/trpc/{procedure}"
        body = {"json": input_data} if input_data is not None else {"json": {}}
        logger.debug(f"tRPC mutation: {procedure}")
        response = await self._client.post(url, json=body)
        return self._parse_response(response)

    # ── Board operations ──

    async def list_boards(self) -> list[dict]:
        """Get all boards."""
        return await self._query("board.getAllBoards")

    async def get_board(self, name: str) -> dict:
        """Get a board by name (includes sections, items, layouts)."""
        return await self._query("board.getBoardByName", {"name": name})

    async def create_board(
        self, name: str, column_count: int = 10, is_public: bool = False
    ) -> dict:
        """Create a new board. Returns {"boardId": "..."}."""
        return await self._mutate(
            "board.createBoard",
            {"name": name, "columnCount": column_count, "isPublic": is_public},
        )

    async def duplicate_board(self, board_id: str, new_name: str) -> dict:
        """Duplicate an existing board with a new name."""
        return await self._mutate("board.duplicateBoard", {"id": board_id, "name": new_name})

    async def rename_board(self, board_id: str, new_name: str) -> Any:
        """Rename a board."""
        return await self._mutate("board.renameBoard", {"id": board_id, "name": new_name})

    async def delete_board(self, board_id: str) -> Any:
        """Delete a board."""
        return await self._mutate("board.deleteBoard", {"id": board_id})

    async def change_board_visibility(self, board_id: str, visibility: str) -> Any:
        """Change board visibility ('public' or 'private')."""
        return await self._mutate(
            "board.changeBoardVisibility",
            {"id": board_id, "visibility": visibility},
        )

    async def get_board_permissions(self, board_id: str) -> dict:
        """Get user and group permissions for a board."""
        return await self._query("board.getBoardPermissions", {"id": board_id})

    # ── App operations ──

    async def list_apps(self) -> list[dict]:
        """Get all apps."""
        return await self._query("app.all")

    async def get_app(self, app_id: str) -> dict:
        """Get an app by ID."""
        return await self._query("app.byId", {"id": app_id})

    async def create_app(
        self,
        name: str,
        href: str,
        description: str = "",
        icon_url: str = "https://cdn.jsdelivr.net/npm/@homarr/icons@latest/svgs/default.svg",
        ping_url: Optional[str] = None,
    ) -> dict:
        """Create a new app.

        API requires: name (str), href (str), description (str),
        iconUrl (non-empty str), pingUrl ("" for null or a URL string).
        """
        return await self._mutate(
            "app.create",
            {
                "name": name,
                "href": href,
                "description": description,
                "iconUrl": icon_url,
                "pingUrl": ping_url or "",
            },
        )

    async def update_app(
        self,
        app_id: str,
        name: str,
        href: str,
        description: str = "",
        icon_url: str = "https://cdn.jsdelivr.net/npm/@homarr/icons@latest/svgs/default.svg",
        ping_url: Optional[str] = None,
    ) -> dict:
        """Update an app. All fields are required by the API."""
        return await self._mutate(
            "app.update",
            {
                "id": app_id,
                "name": name,
                "href": href,
                "description": description,
                "iconUrl": icon_url,
                "pingUrl": ping_url or "",
            },
        )

    async def delete_app(self, app_id: str) -> Any:
        """Delete an app."""
        return await self._mutate("app.delete", {"id": app_id})

    # ── Group operations ──

    async def list_groups(self) -> list[dict]:
        """Get all groups with members."""
        return await self._query("group.getAll")

    async def get_group(self, group_id: str) -> dict:
        """Get a group by ID with members and permissions."""
        return await self._query("group.getById", {"id": group_id})

    async def add_group_member(self, group_id: str, user_id: str) -> Any:
        """Add a user to a group."""
        return await self._mutate("group.addMember", {"groupId": group_id, "userId": user_id})

    async def remove_group_member(self, group_id: str, user_id: str) -> Any:
        """Remove a user from a group."""
        return await self._mutate("group.removeMember", {"groupId": group_id, "userId": user_id})

    # ── User operations ──

    async def list_users(self) -> list[dict]:
        """Get all users."""
        return await self._query("user.getAll")

    async def search_users(self, query: str, limit: int = 10) -> list[dict]:
        """Search users by name or email."""
        return await self._query("user.search", {"query": query, "limit": limit})

    # ── Connectivity ──

    async def check_connection(self) -> bool:
        """Verify API connectivity by listing boards."""
        try:
            await self.list_boards()
            return True
        except Exception:
            return False
