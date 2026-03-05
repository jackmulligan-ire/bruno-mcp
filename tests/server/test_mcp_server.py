"""Tests for MCP server resources and tools."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from bruno_mcp import MCPServer
from bruno_mcp.executors import CLIExecutor
from bruno_mcp.models import BruEnvironment, BruResponse, CollectionInfo, RequestMetadata
from bruno_mcp.parsers import EnvParser


# --- Fixtures (server tests only) ---


@pytest.fixture
def second_collection_dir(fixtures_dir):
    """Path to second collection for multi-collection tests."""
    return fixtures_dir / "second_collection"


@pytest.fixture
def collection_info(sample_collection_dir):
    """Single CollectionInfo for sample_collection."""
    return CollectionInfo(name="sample_collection", path=sample_collection_dir.resolve())


@pytest.fixture
def collections_single(collection_info):
    """Single-collection list for backward-compat tests."""
    return [collection_info]


@pytest.fixture
def sample_collection_metadata():
    """Metadata for one request in sample_collection."""
    return [
        RequestMetadata(
            id="users/get-user",
            name="Get User",
            method="GET",
            url="https://api.example.com/users/{{userId}}",
            file_path="users/get-user.bru",
        )
    ]


@pytest.fixture
def collection_metadata_by_name(sample_collection_metadata):
    """Metadata dict keyed by collection name (single collection)."""
    return {"sample_collection": sample_collection_metadata}


@pytest.fixture
def second_collection_metadata():
    """Metadata for one request in second_collection."""
    return [
        RequestMetadata(
            id="health/check",
            name="Health Check",
            method="GET",
            url="https://api.example.com/health",
            file_path="health/check.bru",
        )
    ]


@pytest.fixture
def collections_multi(sample_collection_dir, second_collection_dir):
    """Two collections for multi-collection tests."""
    return [
        CollectionInfo(name="sample_collection", path=sample_collection_dir.resolve()),
        CollectionInfo(name="second_collection", path=second_collection_dir.resolve()),
    ]


@pytest.fixture
def collection_metadata_multi(sample_collection_metadata, second_collection_metadata):
    """Metadata dict for both collections."""
    return {
        "sample_collection": sample_collection_metadata,
        "second_collection": second_collection_metadata,
    }


@pytest.fixture
def bruno_env_single_path(sample_collection_dir):
    """Set BRUNO_COLLECTION_PATH to a single collection for the duration of the test."""
    with patch.dict(os.environ, {"BRUNO_COLLECTION_PATH": str(sample_collection_dir)}):
        yield


@pytest.fixture
def bruno_env_two_paths(sample_collection_dir, second_collection_dir):
    """Set BRUNO_COLLECTION_PATH to two collections for the duration of the test."""
    env_val = f"{sample_collection_dir}{os.pathsep}{second_collection_dir}"
    with patch.dict(os.environ, {"BRUNO_COLLECTION_PATH": env_val}):
        yield


@pytest.fixture
def bruno_env_invalid_path(invalid_fixtures_dir):
    """Set BRUNO_COLLECTION_PATH to an invalid path for the duration of the test."""
    with patch.dict(os.environ, {"BRUNO_COLLECTION_PATH": str(invalid_fixtures_dir)}):
        yield


# --- Helpers ---


def _make_server(
    mock_mcp,
    mock_executor,
    collections,
    collection_metadata,
    env_parser=None,
):
    """Helper to construct MCPServer with common mocks."""
    if env_parser is None:
        env_parser = EnvParser()
    return MCPServer(
        collections=collections,
        collection_metadata=collection_metadata,
        executor=mock_executor,
        mcp=mock_mcp,
        env_parser=env_parser,
    )


class TestMCPServerInit:
    """Test MCPServer.__init__ validation."""

    def test_init_raises_error_for_empty_collections(self, mock_mcp, mock_executor):
        """Test MCPServer.__init__ raises when collections list is empty."""
        with pytest.raises(ValueError, match="At least one collection"):
            MCPServer(
                collections=[],
                collection_metadata={},
                executor=mock_executor,
                mcp=mock_mcp,
                env_parser=EnvParser(),
            )


class TestCollectionMetadataResource:
    """Test bruno://collection_metadata resource (request metadata for the active collection).

    This resource returns the list of requests in the currently active collection,
    i.e. the metadata for all .bru files. Distinct from TestCollectionsResource
    which tests the list of loaded collections themselves.
    """

    def test_resource_registered_with_correct_uri(
        self, mock_mcp, mock_executor, collections_single
    ):
        """Test _register_resources calls mcp.resource() with bruno://collection_metadata."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": []},
        )

        mock_mcp.resource.assert_any_call("bruno://collection_metadata")

    def test_collection_metadata_handler_returns_all_requests(
        self, mock_mcp, mock_executor, collections_single
    ):
        """Test collection_metadata handler returns requests from active collection."""
        expected_requests = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            ),
            RequestMetadata(
                id="users/create-user",
                name="Create User",
                method="POST",
                url="https://api.example.com/users",
                file_path="users/create-user.bru",
            ),
        ]

        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": expected_requests},
        )

        resource_decorator = mock_mcp.resource.return_value
        collection_metadata_handler = resource_decorator.call_args_list[0][0][0]
        collection_metadata = collection_metadata_handler()
        assert len(collection_metadata) == 2
        assert collection_metadata[0]["id"] == "users/get-user"
        assert collection_metadata[1]["id"] == "users/create-user"

    def test_collection_metadata_handler_includes_complete_metadata(
        self, mock_mcp, mock_executor, collections_single
    ):
        """Test collection_metadata handler returns all required metadata fields."""
        expected_requests = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ]

        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": expected_requests},
        )

        resource_decorator = mock_mcp.resource.return_value
        collection_metadata_handler = resource_decorator.call_args_list[0][0][0]
        result = collection_metadata_handler()
        request = result[0]
        assert request["id"] == "users/get-user"
        assert request["name"] == "Get User"
        assert request["method"] == "GET"
        assert request["url"] == "https://api.example.com/users/{{userId}}"
        assert request["file_path"] == "users/get-user.bru"


class TestEnvironmentsResource:
    """Test bruno://environments resource (environments for the active collection)."""

    @pytest.fixture
    def mock_env_parser(self):
        """Mock EnvParser instance for environment discovery."""
        return Mock()

    def test_environments_resource_registered_with_correct_uri(
        self, mock_mcp, mock_executor, mock_env_parser, collections_single
    ):
        """Test _register_resources calls mcp.resource() with bruno://environments."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": []},
            env_parser=mock_env_parser,
        )

        mock_mcp.resource.assert_any_call("bruno://environments")

    def test_environments_resource_handler_returns_all_environments(
        self, mock_mcp, mock_executor, mock_env_parser, sample_collection_dir, collections_single
    ):
        """Test handler returns environments from active collection."""
        expected_environments = [
            BruEnvironment(
                name="local", variables={"baseUrl": "http://localhost:3000", "apiVersion": "v1"}
            ),
            BruEnvironment(
                name="production",
                variables={
                    "baseUrl": "https://api.example.com",
                    "apiKey": "{{process.env.API_KEY}}",
                },
            ),
        ]
        mock_env_parser.list_environments.return_value = expected_environments
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": []},
            env_parser=mock_env_parser,
        )
        resource_decorator = mock_mcp.resource.return_value
        environments_handler = resource_decorator.call_args_list[1][0][0]

        environments = environments_handler()

        assert len(environments) == 2
        assert environments[0]["name"] == "local"
        assert environments[1]["name"] == "production"
        mock_env_parser.list_environments.assert_called_once_with(sample_collection_dir)

    def test_environments_resource_includes_name_and_variables_with_secrets(
        self, mock_mcp, mock_executor, mock_env_parser, collections_single
    ):
        """Test each environment includes name and variables dict with secrets as templates."""
        expected_environments = [
            BruEnvironment(
                name="local",
                variables={
                    "baseUrl": "http://localhost:3000",
                    "authToken": "{{process.env.SECRET_TOKEN}}",
                },
            ),
        ]
        mock_env_parser.list_environments.return_value = expected_environments
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": []},
            env_parser=mock_env_parser,
        )
        resource_decorator = mock_mcp.resource.return_value
        environments_handler = resource_decorator.call_args_list[1][0][0]

        environments = environments_handler()

        environment = environments[0]
        assert environment["name"] == "local"
        assert "variables" in environment
        assert environment["variables"]["baseUrl"] == "http://localhost:3000"
        assert environment["variables"]["authToken"] == "{{process.env.SECRET_TOKEN}}"


class TestCollectionsResource:
    """Test bruno://collections resource (list of loaded collections).

    This resource returns all collections that were loaded at startup, with name
    and path. Distinct from TestCollectionMetadataResource which tests the request
    tree within the active collection.
    """

    def test_collections_resource_registered_with_correct_uri(
        self, mock_mcp, mock_executor, collections_single, collection_metadata_by_name
    ):
        """Test _register_resources calls mcp.resource() with bruno://collections."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            collection_metadata_by_name,
        )

        mock_mcp.resource.assert_any_call("bruno://collections")

    def test_collections_resource_returns_all_collections(
        self, mock_mcp, mock_executor, collections_multi, collection_metadata_multi
    ):
        """Test handler returns name and path for each collection."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_multi,
            collection_metadata_multi,
        )

        resource_decorator = mock_mcp.resource.return_value
        collections_handler = resource_decorator.call_args_list[2][0][0]
        result = collections_handler()

        assert len(result) == 2
        assert result[0]["name"] == "sample_collection"
        assert "path" in result[0]
        assert result[1]["name"] == "second_collection"
        assert "path" in result[1]

    def test_collections_resource_works_with_single_collection(
        self, mock_mcp, mock_executor, collections_single, collection_metadata_by_name
    ):
        """Test single collection returns one entry."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            collection_metadata_by_name,
        )

        resource_decorator = mock_mcp.resource.return_value
        collections_handler = resource_decorator.call_args_list[2][0][0]
        result = collections_handler()

        assert len(result) == 1
        assert result[0]["name"] == "sample_collection"
        assert "path" in result[0]


class TestServerCreate:
    """Test MCPServer.create() factory method."""

    @pytest.fixture
    def mock_cli_executor_class(self):
        """Mock CLIExecutor class for create() tests."""
        with patch("bruno_mcp.server.CLIExecutor") as mock:
            yield mock

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess module for CLI validation tests."""
        with patch("bruno_mcp.server.subprocess") as mock:
            yield mock

    @pytest.fixture
    def mock_scanner_class(self):
        """Mock CollectionScanner class for create() tests."""
        with patch("bruno_mcp.server.CollectionScanner") as mock:
            yield mock

    @pytest.fixture
    def mock_parser_class(self):
        """Mock BruParser class for create() tests."""
        with patch("bruno_mcp.server.BruParser") as mock:
            yield mock

    @pytest.fixture
    def mock_fastmcp(self):
        """Mock FastMCP class for create() tests."""
        with patch("bruno_mcp.server.FastMCP") as mock:
            yield mock

    def test_create_single_path_backward_compatible(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_parser_class,
        mock_scanner_class,
        mock_subprocess,
        sample_collection_dir,
        bruno_env_single_path,
    ):
        """Test single path loads one collection, first is active, metadata passed."""
        mock_parser_instance = mock_parser_class.return_value
        mock_scanner_instance = mock_scanner_class.return_value
        expected_metadata = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ]
        mock_scanner_instance.scan_collection.return_value = expected_metadata
        mock_subprocess.run.return_value.returncode = 0

        server = MCPServer.create()

        assert len(server._collections) == 1
        assert server._collections[0].name == "sample_collection"
        assert server._collections[0].path.resolve() == sample_collection_dir.resolve()
        assert server._active_collection_name == "sample_collection"
        assert server._collection_metadata == {"sample_collection": expected_metadata}
        mock_parser_class.assert_called_once()
        mock_scanner_class.assert_called_once_with(mock_parser_instance)
        mock_scanner_instance.scan_collection.assert_called_once_with(
            sample_collection_dir.resolve()
        )

    def test_create_multiple_paths_loads_all_collections(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
        bruno_env_two_paths,
    ):
        """Test colon-separated paths load multiple collections, first is active."""
        mock_scanner_instance = mock_scanner_class.return_value
        mock_scanner_instance.scan_collection.side_effect = [
            [RequestMetadata(id="a", name="A", method="GET", url="u", file_path="a.bru")],
            [RequestMetadata(id="b", name="B", method="GET", url="u", file_path="b.bru")],
        ]
        mock_subprocess.run.return_value.returncode = 0

        server = MCPServer.create()

        assert len(server._collections) == 2
        assert server._collections[0].name == "sample_collection"
        assert server._collections[1].name == "second_collection"
        assert server._active_collection_name == "sample_collection"
        assert mock_scanner_instance.scan_collection.call_count == 2

    def test_create_raises_error_for_invalid_collection_path(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
        invalid_fixtures_dir,
        bruno_env_invalid_path,
    ):
        """Test path without bruno.json raises ValueError with path in message."""
        mock_scanner_instance = mock_scanner_class.return_value
        mock_scanner_instance.scan_collection.side_effect = ValueError(
            f"Not a valid Bruno collection: {invalid_fixtures_dir}"
        )
        mock_subprocess.run.return_value.returncode = 0

        with pytest.raises(ValueError) as exc_info:
            MCPServer.create()

        assert "Not a valid Bruno collection" in str(exc_info.value)
        assert str(invalid_fixtures_dir) in str(exc_info.value)

    def test_create_uses_cli_executor_and_validates_cli(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
        bruno_env_single_path,
    ):
        """Test CLIExecutor used and CLI validated at startup."""
        mock_scanner_instance = mock_scanner_class.return_value
        mock_scanner_instance.scan_collection.return_value = []
        mock_subprocess.run.return_value.returncode = 0

        MCPServer.create()

        mock_cli_executor_class.assert_called_once()
        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args
        assert call_args[0][0] == ["bru", "--version"]

    def test_create_raises_error_when_cli_not_found(
        self, mock_scanner_class, mock_subprocess, bruno_env_single_path
    ):
        """Test error when Bruno CLI unavailable."""
        mock_scanner_instance = mock_scanner_class.return_value
        mock_scanner_instance.scan_collection.return_value = []
        mock_subprocess.run.side_effect = FileNotFoundError("bru: command not found")

        with pytest.raises(RuntimeError) as exc_info:
            MCPServer.create()

        assert "Bruno CLI" in str(exc_info.value)

    @patch.dict(os.environ, {}, clear=True)
    def test_create_raises_error_without_collection_path(self):
        """Test MCPServer.create() raises error when BRUNO_COLLECTION_PATH not set."""
        with pytest.raises(ValueError, match="BRUNO_COLLECTION_PATH not set"):
            MCPServer.create()

    def test_create_raises_error_when_paths_empty_after_split(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
    ):
        """Test error when BRUNO_COLLECTION_PATH contains only separators/whitespace."""
        # Use pathsep only so all segments are empty after split (e.g. ":" or ";;" on Windows)
        with patch.dict(os.environ, {"BRUNO_COLLECTION_PATH": os.pathsep * 2}):
            mock_subprocess.run.return_value.returncode = 0

            with pytest.raises(ValueError, match="contains no valid paths"):
                MCPServer.create()


class TestListRequestsTool:
    """Test list_requests MCP tool registration and handler."""

    def test_list_requests_handler_callable(
        self, mock_mcp, mock_executor, collections_single, collection_metadata_by_name
    ):
        """Test list_requests handler is registered and callable."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            collection_metadata_by_name,
        )

        tool_decorator = mock_mcp.tool.return_value
        list_requests_handler = tool_decorator.call_args_list[1][0][0]

        assert mock_mcp.tool.call_count == 5
        assert callable(list_requests_handler)
        assert list_requests_handler.__name__ == "list_requests"

    def test_list_requests_returns_expected_endpoints(
        self, mock_mcp, mock_executor, collections_single
    ):
        """Test list_requests returns requests from active collection."""
        expected_requests = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            ),
            RequestMetadata(
                id="posts/create-post",
                name="Create Post",
                method="POST",
                url="https://api.example.com/posts",
                file_path="posts/create-post.bru",
            ),
            RequestMetadata(
                id="posts/list-posts",
                name="List Posts",
                method="GET",
                url="https://api.example.com/posts",
                file_path="posts/list-posts.bru",
            ),
        ]
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": expected_requests},
        )

        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[1][0][0]
        result = handler()

        assert len(result) == 3
        assert result[0]["id"] == "users/get-user"
        assert result[1]["id"] == "posts/create-post"
        assert result[2]["id"] == "posts/list-posts"

    def test_list_requests_returns_complete_endpoint_metadata(
        self, mock_mcp, mock_executor, collections_single
    ):
        """Test each endpoint includes all required metadata fields."""
        expected_requests = [
            RequestMetadata(
                id="users/delete-user",
                name="Delete User",
                method="DELETE",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/delete-user.bru",
            )
        ]
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": expected_requests},
        )

        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[1][0][0]
        result = handler()

        endpoint = result[0]
        assert endpoint["id"] == "users/delete-user"
        assert endpoint["name"] == "Delete User"
        assert endpoint["method"] == "DELETE"
        assert endpoint["url"] == "https://api.example.com/users/{{userId}}"
        assert endpoint["file_path"] == "users/delete-user.bru"
        assert "{{userId}}" in endpoint["url"]

    def test_list_requests_handles_empty_collection(
        self, mock_mcp, mock_executor, collections_single
    ):
        """Test list_requests returns empty list when active collection is empty."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": []},
        )

        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[1][0][0]
        result = handler()

        assert result == []
        assert isinstance(result, list)


class TestRunBrunoRequestTool:
    """Test run_request_by_id MCP tool registration and handler."""

    @pytest.fixture
    def mock_cli_executor(self):
        """Mock CLIExecutor instance for execution tests."""
        return Mock(spec=CLIExecutor)

    def test_run_request_by_id_tool_registered(
        self, mock_mcp, mock_cli_executor, collections_single, collection_metadata_by_name
    ):
        """Test run_request_by_id tool is registered with correct name."""
        _make_server(
            mock_mcp,
            mock_cli_executor,
            collections_single,
            collection_metadata_by_name,
        )

        tool_decorator = mock_mcp.tool.return_value
        run_request_handler = tool_decorator.call_args_list[0][0][0]

        assert run_request_handler.__name__ == "run_request_by_id"

    def test_tool_passes_file_path_and_active_collection_path_to_executor(
        self,
        sample_collection_dir,
        mock_cli_executor,
        mock_mcp,
        collections_single,
        sample_collection_metadata,
    ):
        """Test file path and active collection path passed correctly to executor."""
        mock_cli_executor.execute.return_value = BruResponse(
            status=200,
            headers={},
            body="",
        )

        _make_server(
            mock_mcp,
            mock_cli_executor,
            collections_single,
            {"sample_collection": sample_collection_metadata},
        )

        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[0][0][0]
        handler(request_id="users/get-user")

        mock_cli_executor.execute.assert_called_once()
        call_args = mock_cli_executor.execute.call_args
        assert call_args[0][0] == Path("users/get-user.bru")
        assert call_args[0][1] == sample_collection_dir

    def test_tool_returns_executor_response(
        self,
        mock_cli_executor,
        mock_mcp,
        collections_single,
        sample_collection_metadata,
    ):
        """Test handler returns executor response correctly."""
        expected_response = BruResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"id": "123", "name": "John"}',
        )
        mock_cli_executor.execute.return_value = expected_response

        _make_server(
            mock_mcp,
            mock_cli_executor,
            collections_single,
            {"sample_collection": sample_collection_metadata},
        )

        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[0][0][0]
        result = handler(request_id="users/get-user")

        assert result["status"] == 200
        assert result["headers"]["Content-Type"] == "application/json"
        assert result["body"] == '{"id": "123", "name": "John"}'

    def test_tool_passes_environment_name_to_executor(
        self,
        mock_cli_executor,
        mock_mcp,
        collections_single,
        sample_collection_metadata,
    ):
        """Test environment_name passed correctly to executor."""
        mock_cli_executor.execute.return_value = BruResponse(
            status=200,
            headers={},
            body='{"id": "456"}',
        )
        _make_server(
            mock_mcp,
            mock_cli_executor,
            collections_single,
            {"sample_collection": sample_collection_metadata},
        )

        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[0][0][0]
        result = handler(request_id="users/get-user", environment_name="local")

        assert result["status"] == 200
        mock_cli_executor.execute.assert_called_once()
        call_args = mock_cli_executor.execute.call_args
        assert call_args[0][2] == "local"

    def test_tool_passes_variable_overrides_to_executor(
        self,
        mock_cli_executor,
        mock_mcp,
        collections_single,
        sample_collection_metadata,
    ):
        """Test variable_overrides passed correctly to executor."""
        mock_cli_executor.execute.return_value = BruResponse(
            status=200,
            headers={},
            body='{"id": "456"}',
        )
        _make_server(
            mock_mcp,
            mock_cli_executor,
            collections_single,
            {"sample_collection": sample_collection_metadata},
        )

        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[0][0][0]
        result = handler(request_id="users/get-user", variable_overrides={"userId": "456"})

        assert result["status"] == 200
        mock_cli_executor.execute.assert_called_once()
        call_args = mock_cli_executor.execute.call_args
        assert call_args[0][3] == {"userId": "456"}

    def test_tool_raises_error_for_invalid_request_id(
        self,
        mock_cli_executor,
        mock_mcp,
        collections_single,
        sample_collection_metadata,
    ):
        """Test error handling when request_id not found."""
        _make_server(
            mock_mcp,
            mock_cli_executor,
            collections_single,
            {"sample_collection": sample_collection_metadata},
        )

        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[0][0][0]

        with pytest.raises(ValueError, match="Request not found"):
            handler(request_id="users/nonexistent")


class TestListEnvironmentsTool:
    """Test list_environments MCP tool registration and handler."""

    @pytest.fixture
    def mock_env_parser(self):
        """Mock EnvParser instance for environment discovery."""
        return Mock()

    def test_list_environments_tool_registered_and_callable(
        self,
        mock_mcp,
        mock_executor,
        mock_env_parser,
        collections_single,
        collection_metadata_by_name,
    ):
        """Test list_environments tool is registered and callable."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            collection_metadata_by_name,
            env_parser=mock_env_parser,
        )
        tool_decorator = mock_mcp.tool.return_value
        list_environments_handler = tool_decorator.call_args_list[2][0][0]

        assert callable(list_environments_handler)
        assert list_environments_handler.__name__ == "list_environments"

    def test_list_environments_returns_from_active_collection(
        self, mock_mcp, mock_executor, mock_env_parser, sample_collection_dir, collections_single
    ):
        """Test tool returns environments from active collection."""
        expected_environments = [
            BruEnvironment(
                name="local", variables={"baseUrl": "http://localhost:3000", "apiVersion": "v1"}
            ),
            BruEnvironment(
                name="production",
                variables={
                    "baseUrl": "https://api.example.com",
                    "apiKey": "{{process.env.API_KEY}}",
                },
            ),
        ]
        mock_env_parser.list_environments.return_value = expected_environments
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": []},
            env_parser=mock_env_parser,
        )
        tool_decorator = mock_mcp.tool.return_value
        list_environments_handler = tool_decorator.call_args_list[2][0][0]

        result = list_environments_handler()

        assert len(result) == 2
        assert result[0]["name"] == "local"
        assert result[0]["variables"]["baseUrl"] == "http://localhost:3000"
        assert result[1]["name"] == "production"
        assert result[1]["variables"]["apiKey"] == "{{process.env.API_KEY}}"
        mock_env_parser.list_environments.assert_called_once_with(sample_collection_dir)

    def test_list_environments_handles_empty_environments_directory(
        self, mock_mcp, mock_executor, mock_env_parser, collections_single
    ):
        """Test tool returns empty list when no environments found."""
        mock_env_parser.list_environments.return_value = []
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            {"sample_collection": []},
            env_parser=mock_env_parser,
        )
        tool_decorator = mock_mcp.tool.return_value
        list_environments_handler = tool_decorator.call_args_list[2][0][0]

        result = list_environments_handler()

        assert result == []


class TestListCollectionsTool:
    """Test list_collections MCP tool registration and handler."""

    def test_list_collections_tool_registered_and_callable(
        self, mock_mcp, mock_executor, collections_single, collection_metadata_by_name
    ):
        """Test list_collections tool is registered and callable."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            collection_metadata_by_name,
        )
        tool_decorator = mock_mcp.tool.return_value
        list_collections_handler = tool_decorator.call_args_list[3][0][0]

        assert callable(list_collections_handler)
        assert list_collections_handler.__name__ == "list_collections"

    def test_list_collections_returns_all_with_name_and_path(
        self, mock_mcp, mock_executor, collections_multi, collection_metadata_multi
    ):
        """Test returns list of {name, path} for each collection."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_multi,
            collection_metadata_multi,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[3][0][0]
        result = handler()

        assert len(result) == 2
        assert result[0]["name"] == "sample_collection"
        assert "path" in result[0]
        assert result[1]["name"] == "second_collection"
        assert "path" in result[1]

    def test_list_collections_works_with_single_collection(
        self, mock_mcp, mock_executor, collections_single, collection_metadata_by_name
    ):
        """Test single collection returns one entry."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            collection_metadata_by_name,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[3][0][0]
        result = handler()

        assert len(result) == 1
        assert result[0]["name"] == "sample_collection"
        assert "path" in result[0]


class TestSetActiveCollectionTool:
    """Test set_active_collection MCP tool registration and handler."""

    def test_set_active_collection_tool_registered(
        self, mock_mcp, mock_executor, collections_multi, collection_metadata_multi
    ):
        """Test set_active_collection tool is registered."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_multi,
            collection_metadata_multi,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[4][0][0]

        assert callable(handler)
        assert handler.__name__ == "set_active_collection"

    def test_set_active_collection_switches_and_returns_name(
        self,
        mock_mcp,
        mock_executor,
        collections_multi,
        collection_metadata_multi,
    ):
        """Test switches active collection, returns new name, list_requests reflects change."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_multi,
            collection_metadata_multi,
        )
        tool_decorator = mock_mcp.tool.return_value
        set_handler = tool_decorator.call_args_list[4][0][0]
        list_handler = tool_decorator.call_args_list[1][0][0]

        result = set_handler(collection_name="second_collection")

        assert result == "second_collection"
        list_result = list_handler()
        assert len(list_result) == 1
        assert list_result[0]["id"] == "health/check"

    def test_set_active_collection_raises_for_unknown_name(
        self, mock_mcp, mock_executor, collections_single, collection_metadata_by_name
    ):
        """Test unknown collection_name raises ValueError with name in message."""
        _make_server(
            mock_mcp,
            mock_executor,
            collections_single,
            collection_metadata_by_name,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[4][0][0]

        with pytest.raises(ValueError) as exc_info:
            handler(collection_name="nonexistent")

        assert "nonexistent" in str(exc_info.value)
