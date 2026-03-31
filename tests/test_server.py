"""Unit tests for Homarr MCP server."""

from unittest.mock import AsyncMock

import pytest

import src.server
from src.homarr_client import HomarrClient

# ── Fixtures ──


@pytest.fixture
def mock_client():
    """Create a mocked HomarrClient and inject it as the global client."""
    client = AsyncMock(spec=HomarrClient)
    original = src.server._client
    src.server._client = client
    yield client
    src.server._client = original


# ── Board tests ──


class TestBoardTools:
    @pytest.mark.asyncio
    async def test_list_boards(self, mock_client):
        mock_client.list_boards.return_value = [
            {"id": "abc123", "name": "TETRA", "isPublic": False, "logoImageUrl": "/img.png"},
            {"id": "def456", "name": "ICOSA", "isPublic": False, "logoImageUrl": "/img2.png"},
        ]
        result = await src.server.list_boards("standard")
        assert len(result) == 2
        assert result[0]["name"] == "TETRA"
        mock_client.list_boards.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_boards_minimal(self, mock_client):
        mock_client.list_boards.return_value = [
            {"id": "abc", "name": "TETRA", "isPublic": False, "logoImageUrl": "/x", "creator": {}},
        ]
        result = await src.server.list_boards("minimal")
        assert len(result) == 1
        assert "logoImageUrl" not in result[0]
        assert "id" in result[0]

    @pytest.mark.asyncio
    async def test_get_board(self, mock_client):
        mock_client.get_board.return_value = {
            "id": "abc",
            "name": "TETRA",
            "isPublic": False,
            "sections": [{"id": "s1"}],
            "items": [],
        }
        result = await src.server.get_board("TETRA")
        assert result["name"] == "TETRA"
        mock_client.get_board.assert_called_once_with("TETRA")

    @pytest.mark.asyncio
    async def test_create_board(self, mock_client):
        mock_client.create_board.return_value = {"boardId": "new123"}
        result = await src.server.create_board("Test")
        assert result["boardId"] == "new123"
        mock_client.create_board.assert_called_once_with("Test", 10, False)

    @pytest.mark.asyncio
    async def test_create_board_custom(self, mock_client):
        mock_client.create_board.return_value = {"boardId": "new456"}
        await src.server.create_board("Public", column_count=12, is_public=True)
        mock_client.create_board.assert_called_once_with("Public", 12, True)

    @pytest.mark.asyncio
    async def test_duplicate_board(self, mock_client):
        mock_client.duplicate_board.return_value = {"boardId": "dup123"}
        await src.server.duplicate_board("abc123", "TETRA Copy")
        mock_client.duplicate_board.assert_called_once_with("abc123", "TETRA Copy")

    @pytest.mark.asyncio
    async def test_rename_board(self, mock_client):
        mock_client.rename_board.return_value = {"id": "abc", "name": "New Name"}
        await src.server.rename_board("abc", "New Name")
        mock_client.rename_board.assert_called_once_with("abc", "New Name")

    @pytest.mark.asyncio
    async def test_delete_board(self, mock_client):
        mock_client.delete_board.return_value = None
        result = await src.server.delete_board("abc")
        assert result["success"] is True
        assert result["deleted_id"] == "abc"

    @pytest.mark.asyncio
    async def test_change_board_visibility_valid(self, mock_client):
        mock_client.change_board_visibility.return_value = {"id": "abc", "isPublic": True}
        await src.server.change_board_visibility("abc", "public")
        mock_client.change_board_visibility.assert_called_once_with("abc", "public")

    @pytest.mark.asyncio
    async def test_change_board_visibility_invalid(self, mock_client):
        result = await src.server.change_board_visibility("abc", "invalid")
        assert "error" in result
        mock_client.change_board_visibility.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_board_permissions(self, mock_client):
        mock_client.get_board_permissions.return_value = {
            "userPermissions": [],
            "groupPermissions": [],
        }
        await src.server.get_board_permissions("abc")
        mock_client.get_board_permissions.assert_called_once_with("abc")


# ── App tests ──


class TestAppTools:
    @pytest.mark.asyncio
    async def test_list_apps(self, mock_client):
        mock_client.list_apps.return_value = [
            {
                "id": "app1",
                "name": "MyApp",
                "href": "https://example.com",
                "description": None,
                "iconUrl": None,
                "pingUrl": None,
            },
        ]
        result = await src.server.list_apps()
        assert len(result) == 1
        assert result[0]["name"] == "MyApp"

    @pytest.mark.asyncio
    async def test_get_app(self, mock_client):
        mock_client.get_app.return_value = {
            "id": "app1",
            "name": "MyApp",
            "href": "https://example.com",
            "description": "Test",
            "iconUrl": None,
            "pingUrl": None,
        }
        result = await src.server.get_app("app1")
        assert result["name"] == "MyApp"

    @pytest.mark.asyncio
    async def test_create_app(self, mock_client):
        mock_client.create_app.return_value = {"id": "new1", "name": "New App"}
        await src.server.create_app("New App", "https://new.com", description="Desc")
        mock_client.create_app.assert_called_once_with(
            name="New App",
            href="https://new.com",
            description="Desc",
            icon_url="https://cdn.jsdelivr.net/npm/@homarr/icons@latest/svgs/default.svg",
            ping_url=None,
        )

    @pytest.mark.asyncio
    async def test_update_app(self, mock_client):
        mock_client.get_app.return_value = {
            "id": "app1",
            "name": "Old",
            "href": "https://old.com",
            "description": "Old desc",
            "iconUrl": "https://icon.example.com/x.svg",
            "pingUrl": None,
        }
        mock_client.update_app.return_value = {"id": "app1", "name": "Updated"}
        await src.server.update_app("app1", name="Updated")
        mock_client.get_app.assert_called_once_with("app1")
        mock_client.update_app.assert_called_once_with(
            app_id="app1",
            name="Updated",
            href="https://old.com",
            description="Old desc",
            icon_url="https://icon.example.com/x.svg",
            ping_url=None,
        )

    @pytest.mark.asyncio
    async def test_delete_app(self, mock_client):
        mock_client.delete_app.return_value = None
        result = await src.server.delete_app("app1")
        assert result["success"] is True


# ── Group tests ──


class TestGroupTools:
    @pytest.mark.asyncio
    async def test_list_groups(self, mock_client):
        mock_client.list_groups.return_value = [
            {
                "id": "g1",
                "name": "TETRA",
                "ownerId": "u1",
                "homeBoardId": None,
                "mobileHomeBoardId": None,
                "members": [],
            },
        ]
        result = await src.server.list_groups()
        assert len(result) == 1
        assert result[0]["name"] == "TETRA"

    @pytest.mark.asyncio
    async def test_get_group(self, mock_client):
        mock_client.get_group.return_value = {
            "id": "g1",
            "name": "TETRA",
            "ownerId": "u1",
            "homeBoardId": None,
            "mobileHomeBoardId": None,
            "members": [{"id": "u1"}],
        }
        result = await src.server.get_group("g1")
        assert result["name"] == "TETRA"

    @pytest.mark.asyncio
    async def test_add_group_member(self, mock_client):
        mock_client.add_group_member.return_value = None
        result = await src.server.add_group_member("g1", "u1")
        assert result["success"] is True
        mock_client.add_group_member.assert_called_once_with("g1", "u1")

    @pytest.mark.asyncio
    async def test_remove_group_member(self, mock_client):
        mock_client.remove_group_member.return_value = None
        result = await src.server.remove_group_member("g1", "u1")
        assert result["success"] is True


# ── User tests ──


class TestUserTools:
    @pytest.mark.asyncio
    async def test_list_users(self, mock_client):
        mock_client.list_users.return_value = [
            {
                "id": "u1",
                "name": "Romain VALTIER",
                "email": "rva@tetra-ai.com",
                "emailVerified": None,
                "image": None,
            },
        ]
        result = await src.server.list_users()
        assert len(result) == 1
        assert result[0]["name"] == "Romain VALTIER"

    @pytest.mark.asyncio
    async def test_search_users(self, mock_client):
        mock_client.search_users.return_value = [
            {
                "id": "u1",
                "name": "Romain VALTIER",
                "email": "rva@tetra-ai.com",
                "emailVerified": None,
                "image": None,
            },
        ]
        await src.server.search_users("Romain")
        mock_client.search_users.assert_called_once_with("Romain", 10)


# ── Response filtering tests ──


class TestResponseFiltering:
    def test_filter_minimal(self):
        data = [{"id": "1", "name": "Test", "isPublic": True, "logoImageUrl": "/x"}]
        result = src.server._filter_response(data, "board", "minimal")
        assert "logoImageUrl" not in result[0]
        assert result[0]["id"] == "1"

    def test_filter_full_returns_all(self):
        data = {"id": "1", "name": "Test", "extra": "field"}
        result = src.server._filter_response(data, "board", "full")
        assert result == data

    def test_filter_unknown_type(self):
        data = {"id": "1", "custom": "value"}
        result = src.server._filter_response(data, "unknown_type", "standard")
        assert result == data

    def test_filter_none_input(self):
        result = src.server._filter_response(None, "board", "standard")
        assert result is None

    def test_filter_invalid_verbosity(self):
        data = {"id": "1", "name": "Test"}
        result = src.server._filter_response(data, "board", "invalid")
        # Falls back to standard
        assert "id" in result


# ── Transport resolution tests ──


class TestTransportResolution:
    def test_default_stdio(self):
        assert src.server._resolve_transport(argv=[], env={}) == "stdio"

    def test_sse_flag(self):
        assert src.server._resolve_transport(argv=["--sse"], env={}) == "sse"

    def test_streamable_http_flag(self):
        assert (
            src.server._resolve_transport(argv=["--streamable-http"], env={}) == "streamable-http"
        )

    def test_env_var(self):
        assert src.server._resolve_transport(argv=[], env={"HOMARR_TRANSPORT": "sse"}) == "sse"

    def test_cli_overrides_env(self):
        result = src.server._resolve_transport(
            argv=["--streamable-http"], env={"HOMARR_TRANSPORT": "sse"}
        )
        assert result == "streamable-http"

    def test_invalid_env(self):
        assert (
            src.server._resolve_transport(argv=[], env={"HOMARR_TRANSPORT": "invalid"}) == "stdio"
        )
