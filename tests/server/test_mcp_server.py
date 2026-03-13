"""Tests for MCP server resources and tools."""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from bruno_mcp import MCPServer
from bruno_mcp.executors import CLIExecutor
from bruno_mcp.models import BruEnvironment, BruResponse, RequestMetadata
from bruno_mcp.parsers import EnvParser




@pytest.fixture
def collection_paths(fixtures_dir):
    """All collection-related paths. Use paths.sample_collection, paths.second_collection, etc."""
    return SimpleNamespace(
        sample_collection=fixtures_dir / "sample_collection",
        second_collection=fixtures_dir / "second_collection",
        collection_directory=fixtures_dir / "collection_directory",
        empty_collection_dir=fixtures_dir / "empty_collection_dir",
        collision_a_parent=fixtures_dir / "collision_a" / "parent",
        collision_b_parent=fixtures_dir / "collision_b" / "parent",
    )


@pytest.fixture
def collection_metadata():
    """Metadata for each collection, indexed to match collection_paths. [0]=sample_collection, [1]=second_collection."""
    return [
        [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ],
        [
            RequestMetadata(
                id="health/check",
                name="Health Check",
                method="GET",
                url="https://api.example.com/health",
                file_path="health/check.bru",
            )
        ],
    ]


def _patch_bruno_env_star_path(path):
    """Context manager to set BRUNO_COLLECTION_PATH to path/*."""
    return patch.dict(os.environ, {"BRUNO_COLLECTION_PATH": f"{path}/*"})


@pytest.fixture
def bruno_env_single_path(collection_paths):
    """Set BRUNO_COLLECTION_PATH to a single collection for the duration of the test."""
    with patch.dict(
        os.environ, {"BRUNO_COLLECTION_PATH": str(collection_paths.sample_collection)}
    ):
        yield


@pytest.fixture
def bruno_env_two_paths(collection_paths):
    """Set BRUNO_COLLECTION_PATH to two collections for the duration of the test."""
    env_val = f"{collection_paths.sample_collection}{os.pathsep}{collection_paths.second_collection}"
    with patch.dict(os.environ, {"BRUNO_COLLECTION_PATH": env_val}):
        yield


@pytest.fixture
def bruno_env_invalid_path(invalid_fixtures_dir):
    """Set BRUNO_COLLECTION_PATH to an invalid path for the duration of the test."""
    with patch.dict(os.environ, {"BRUNO_COLLECTION_PATH": str(invalid_fixtures_dir)}):
        yield


@pytest.fixture
def bruno_env_star_path(collection_paths):
    """Set BRUNO_COLLECTION_PATH to a collection directory path (/*) for the duration of the test."""
    with _patch_bruno_env_star_path(collection_paths.collection_directory):
        yield


@pytest.fixture
def bruno_env_mixed_paths(collection_paths):
    """Set BRUNO_COLLECTION_PATH to explicit path + collection directory (/*) for the duration of the test."""
    env_val = f"{collection_paths.sample_collection}{os.pathsep}{collection_paths.collection_directory}/*"
    with patch.dict(os.environ, {"BRUNO_COLLECTION_PATH": env_val}):
        yield


@pytest.fixture
def bruno_env_empty_star_path(collection_paths):
    """Set BRUNO_COLLECTION_PATH to a directory with no valid subcollections (/*) for the duration of the test."""
    with _patch_bruno_env_star_path(collection_paths.empty_collection_dir):
        yield


@pytest.fixture
def bruno_env_collision_paths(collection_paths):
    """Set BRUNO_COLLECTION_PATH to two /* paths that yield the same qualified collection name."""
    env_val = f"{collection_paths.collision_a_parent}/*{os.pathsep}{collection_paths.collision_b_parent}/*"
    with patch.dict(os.environ, {"BRUNO_COLLECTION_PATH": env_val}):
        yield


# --- Helpers ---


def _create_server(
    mock_mcp,
    mock_executor,
    scanner_metadata,
    mock_env_parser=None,
    mock_cli_executor=None,
):
    """Create server via MCPServer.create() with patched dependencies."""
    executor = mock_cli_executor if mock_cli_executor is not None else mock_executor
    with patch("bruno_mcp.server.FastMCP") as mock_fastmcp, patch(
        "bruno_mcp.server.CLIExecutor", return_value=executor
    ), patch("bruno_mcp.server.subprocess") as mock_subprocess, patch(
        "bruno_mcp.server.CollectionScanner"
    ) as mock_scanner_class:
        mock_fastmcp.return_value = mock_mcp
        mock_scanner = mock_scanner_class.return_value
        if len(scanner_metadata) == 1:
            mock_scanner.scan_collection.return_value = scanner_metadata[0]
        else:
            mock_scanner.scan_collection.side_effect = scanner_metadata
        mock_subprocess.run.return_value.returncode = 0
        if mock_env_parser is not None:
            with patch("bruno_mcp.server.EnvParser", return_value=mock_env_parser):
                return MCPServer.create()
        return MCPServer.create()


def _list_collections_via_tool(server):
    """Invoke the list_collections tool handler (public API) to get collection data."""
    tool_decorator = server.mcp.tool.return_value
    list_collections_handler = tool_decorator.call_args_list[3][0][0]
    return list_collections_handler()


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
        self, mock_mcp, mock_executor, bruno_env_single_path
    ):
        """Test _register_resources calls mcp.resource() with bruno://collection_metadata."""
        _create_server(mock_mcp, mock_executor, [[]])
        mock_mcp.resource.assert_any_call("bruno://collection_metadata")

    def test_collection_metadata_handler_returns_all_requests(
        self, mock_mcp, mock_executor, bruno_env_single_path
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

        _create_server(mock_mcp, mock_executor, [expected_requests])

        resource_decorator = mock_mcp.resource.return_value
        collection_metadata_handler = resource_decorator.call_args_list[0][0][0]
        collection_metadata = collection_metadata_handler()
        assert len(collection_metadata) == 2
        assert collection_metadata[0]["id"] == "users/get-user"
        assert collection_metadata[1]["id"] == "users/create-user"

    def test_collection_metadata_handler_includes_complete_metadata(
        self, mock_mcp, mock_executor, collection_metadata, bruno_env_single_path
    ):
        """Test collection_metadata handler returns all required metadata fields."""
        _create_server(mock_mcp, mock_executor, [collection_metadata[0]])

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
        self,
        mock_mcp,
        mock_executor,
        mock_env_parser,
        bruno_env_single_path,
    ):
        """Test _register_resources calls mcp.resource() with bruno://environments."""
        _create_server(mock_mcp, mock_executor, [[]], mock_env_parser=mock_env_parser)
        mock_mcp.resource.assert_any_call("bruno://environments")

    def test_environments_resource_handler_returns_all_environments(
        self,
        mock_mcp,
        mock_executor,
        mock_env_parser,
        collection_paths,
        bruno_env_single_path,
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
        _create_server(mock_mcp, mock_executor, [[]], mock_env_parser=mock_env_parser)

        resource_decorator = mock_mcp.resource.return_value
        environments_handler = resource_decorator.call_args_list[1][0][0]
        environments = environments_handler()

        assert len(environments) == 2
        assert environments[0]["name"] == "local"
        assert environments[1]["name"] == "production"
        mock_env_parser.list_environments.assert_called_once_with(
            collection_paths.sample_collection.resolve()
        )

    def test_environments_resource_includes_name_and_variables_with_secrets(
        self,
        mock_mcp,
        mock_executor,
        mock_env_parser,
        bruno_env_single_path,
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
        _create_server(mock_mcp, mock_executor, [[]], mock_env_parser=mock_env_parser)

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
        self, mock_mcp, mock_executor, collection_metadata, bruno_env_single_path
    ):
        """Test _register_resources calls mcp.resource() with bruno://collections."""
        _create_server(mock_mcp, mock_executor, [collection_metadata[0]])
        mock_mcp.resource.assert_any_call("bruno://collections")

    def test_collections_resource_returns_all_collections(
        self, mock_mcp, mock_executor, collection_metadata, bruno_env_two_paths
    ):
        """Test handler returns name and path for each collection."""
        _create_server(
            mock_mcp, mock_executor, [collection_metadata[0], collection_metadata[1]]
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
        self, mock_mcp, mock_executor, collection_metadata, bruno_env_single_path
    ):
        """Test single collection returns one entry."""
        _create_server(mock_mcp, mock_executor, [collection_metadata[0]])

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
        collection_paths,
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

        collections = _list_collections_via_tool(server)
        assert len(collections) == 1
        assert collections[0]["name"] == "sample_collection"
        assert (
            Path(collections[0]["path"]).resolve()
            == collection_paths.sample_collection.resolve()
        )
        list_requests_handler = server.mcp.tool.return_value.call_args_list[1][0][0]
        assert list_requests_handler() == [r.model_dump() for r in expected_metadata]
        mock_parser_class.assert_called_once()
        mock_scanner_class.assert_called_once_with(mock_parser_instance)
        mock_scanner_instance.scan_collection.assert_called_once_with(
            collection_paths.sample_collection.resolve()
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

        collections = _list_collections_via_tool(server)
        assert len(collections) == 2
        assert collections[0]["name"] == "sample_collection"
        assert collections[1]["name"] == "second_collection"
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

    def test_create_star_path_loads_all_valid_subcollections(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
        collection_paths,
        bruno_env_star_path,
    ):
        """Test path ending in /* loads all valid subcollections from directory."""
        mock_scanner_instance = mock_scanner_class.return_value
        mock_scanner_instance.scan_collection.side_effect = [
            [
                RequestMetadata(
                    id="users/list",
                    name="List Users",
                    method="GET",
                    url="u",
                    file_path="users/list.bru",
                )
            ],
            [
                RequestMetadata(
                    id="posts/list",
                    name="List Posts",
                    method="GET",
                    url="u",
                    file_path="posts/list.bru",
                )
            ],
        ]
        mock_subprocess.run.return_value.returncode = 0

        MCPServer.create()

        mock_scanner_instance.scan_collection.assert_any_call(
            collection_paths.collection_directory / "Users_API"
        )
        mock_scanner_instance.scan_collection.assert_any_call(
            collection_paths.collection_directory / "Posts_API"
        )
        assert mock_scanner_instance.scan_collection.call_count == 2

    def test_create_star_path_uses_qualified_names(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
        bruno_env_star_path,
    ):
        """Test /* path names collections as parent_dir/collection_dir."""
        mock_scanner_instance = mock_scanner_class.return_value
        mock_scanner_instance.scan_collection.side_effect = [
            [RequestMetadata(id="a", name="A", method="GET", url="u", file_path="a.bru")],
            [RequestMetadata(id="b", name="B", method="GET", url="u", file_path="b.bru")],
        ]
        mock_subprocess.run.return_value.returncode = 0

        server = MCPServer.create()

        collections = _list_collections_via_tool(server)
        names = [c["name"] for c in collections]
        assert "collection_directory/Users_API" in names
        assert "collection_directory/Posts_API" in names

    def test_create_mixed_paths_loads_both_explicit_and_directory_collections(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
        bruno_env_mixed_paths,
    ):
        """Test mixed explicit path + /* path loads all collections."""
        mock_scanner_instance = mock_scanner_class.return_value
        mock_scanner_instance.scan_collection.side_effect = [
            [RequestMetadata(id="x", name="X", method="GET", url="u", file_path="x.bru")],
            [RequestMetadata(id="a", name="A", method="GET", url="u", file_path="a.bru")],
            [RequestMetadata(id="b", name="B", method="GET", url="u", file_path="b.bru")],
        ]
        mock_subprocess.run.return_value.returncode = 0

        server = MCPServer.create()

        collections = _list_collections_via_tool(server)
        assert collections[0]["name"] == "sample_collection"
        names = [c["name"] for c in collections]
        assert "collection_directory/Users_API" in names
        assert "collection_directory/Posts_API" in names
        assert len(collections) == 3

    def test_create_star_path_skips_invalid_subdirs(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
        bruno_env_star_path,
    ):
        """Test /* path silently skips subdirs without bruno.json."""
        mock_scanner_instance = mock_scanner_class.return_value
        mock_scanner_instance.scan_collection.side_effect = [
            [RequestMetadata(id="a", name="A", method="GET", url="u", file_path="a.bru")],
            [RequestMetadata(id="b", name="B", method="GET", url="u", file_path="b.bru")],
        ]
        mock_subprocess.run.return_value.returncode = 0

        server = MCPServer.create()

        collections = _list_collections_via_tool(server)
        names = [c["name"] for c in collections]
        assert "collection_directory/not_a_collection" not in names
        assert len(names) == 2

    def test_create_star_path_raises_when_no_valid_collections(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
        bruno_env_empty_star_path,
    ):
        """Test /* path raises ValueError when directory has no valid subcollections."""
        mock_subprocess.run.return_value.returncode = 0

        with pytest.raises(ValueError) as exc_info:
            MCPServer.create()

        assert (
            "no collections" in str(exc_info.value).lower()
            or "not found" in str(exc_info.value).lower()
        )

    def test_create_star_path_raises_when_base_dir_missing(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
        fixtures_dir,
    ):
        """Test /* path raises ValueError when base directory does not exist."""
        nonexistent = fixtures_dir / "definitely_nonexistent_xyz123"
        with patch.dict(os.environ, {"BRUNO_COLLECTION_PATH": f"{nonexistent}/*"}):
            mock_subprocess.run.return_value.returncode = 0

            with pytest.raises(ValueError) as exc_info:
                MCPServer.create()

            assert (
                "exist" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()
            )

    def test_create_raises_on_qualified_name_collision(
        self,
        mock_cli_executor_class,
        mock_fastmcp,
        mock_scanner_class,
        mock_subprocess,
        bruno_env_collision_paths,
    ):
        """Test ValueError when two /* paths produce the same qualified collection name."""
        mock_scanner_instance = mock_scanner_class.return_value
        mock_scanner_instance.scan_collection.side_effect = [
            [RequestMetadata(id="r", name="R", method="GET", url="u", file_path="r.bru")],
            [RequestMetadata(id="r", name="R", method="GET", url="u", file_path="r.bru")],
        ]
        mock_subprocess.run.return_value.returncode = 0

        with pytest.raises(ValueError) as exc_info:
            MCPServer.create()

        assert (
            "collision" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()
        )


class TestListRequestsTool:
    """Test list_requests MCP tool registration and handler."""

    def test_list_requests_handler_callable(
        self, mock_mcp, mock_executor, collection_metadata, bruno_env_single_path
    ):
        """Test list_requests handler is registered and callable."""
        _create_server(mock_mcp, mock_executor, [collection_metadata[0]])

        tool_decorator = mock_mcp.tool.return_value
        list_requests_handler = tool_decorator.call_args_list[1][0][0]

        assert mock_mcp.tool.call_count == 5
        assert callable(list_requests_handler)
        assert list_requests_handler.__name__ == "list_requests"

    def test_list_requests_returns_expected_endpoints(
        self, mock_mcp, mock_executor, bruno_env_single_path
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
        _create_server(mock_mcp, mock_executor, [expected_requests])

        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[1][0][0]
        result = handler()

        assert len(result) == 3
        assert result[0]["id"] == "users/get-user"
        assert result[1]["id"] == "posts/create-post"
        assert result[2]["id"] == "posts/list-posts"

    def test_list_requests_returns_complete_endpoint_metadata(
        self, mock_mcp, mock_executor, bruno_env_single_path
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
        _create_server(mock_mcp, mock_executor, [expected_requests])

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
        self, mock_mcp, mock_executor, bruno_env_single_path
    ):
        """Test list_requests returns empty list when active collection is empty."""
        _create_server(mock_mcp, mock_executor, [[]])

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
        self, mock_mcp, mock_cli_executor, collection_metadata, bruno_env_single_path
    ):
        """Test run_request_by_id tool is registered with correct name."""
        _create_server(mock_mcp, mock_cli_executor, [collection_metadata[0]])

        tool_decorator = mock_mcp.tool.return_value
        run_request_handler = tool_decorator.call_args_list[0][0][0]

        assert run_request_handler.__name__ == "run_request_by_id"

    def test_tool_passes_file_path_and_active_collection_path_to_executor(
        self,
        collection_paths,
        mock_cli_executor,
        mock_mcp,
        collection_metadata,
        bruno_env_single_path,
    ):
        """Test file path and active collection path passed correctly to executor."""
        mock_cli_executor.execute.return_value = BruResponse(
            status=200,
            headers={},
            body="",
        )

        _create_server(mock_mcp, mock_cli_executor, [collection_metadata[0]])

        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[0][0][0]
        handler(request_id="users/get-user")

        mock_cli_executor.execute.assert_called_once()
        call_args = mock_cli_executor.execute.call_args
        assert call_args[0][0] == Path("users/get-user.bru")
        assert call_args[0][1].resolve() == collection_paths.sample_collection.resolve()

    def test_tool_returns_executor_response(
        self,
        mock_cli_executor,
        mock_mcp,
        collection_metadata,
        bruno_env_single_path,
    ):
        """Test handler returns executor response correctly."""
        expected_response = BruResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"id": "123", "name": "John"}',
        )
        mock_cli_executor.execute.return_value = expected_response

        _create_server(mock_mcp, mock_cli_executor, [collection_metadata[0]])

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
        collection_metadata,
        bruno_env_single_path,
    ):
        """Test environment_name passed correctly to executor."""
        mock_cli_executor.execute.return_value = BruResponse(
            status=200,
            headers={},
            body='{"id": "456"}',
        )
        _create_server(mock_mcp, mock_cli_executor, [collection_metadata[0]])

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
        collection_metadata,
        bruno_env_single_path,
    ):
        """Test variable_overrides passed correctly to executor."""
        mock_cli_executor.execute.return_value = BruResponse(
            status=200,
            headers={},
            body='{"id": "456"}',
        )
        _create_server(mock_mcp, mock_cli_executor, [collection_metadata[0]])

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
        collection_metadata,
        bruno_env_single_path,
    ):
        """Test error handling when request_id not found."""
        _create_server(mock_mcp, mock_cli_executor, [collection_metadata[0]])

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
        collection_metadata,
        bruno_env_single_path,
    ):
        """Test list_environments tool is registered and callable."""
        _create_server(
            mock_mcp, mock_executor, [collection_metadata[0]], mock_env_parser=mock_env_parser
        )
        tool_decorator = mock_mcp.tool.return_value
        list_environments_handler = tool_decorator.call_args_list[2][0][0]

        assert callable(list_environments_handler)
        assert list_environments_handler.__name__ == "list_environments"

    def test_list_environments_returns_from_active_collection(
        self,
        mock_mcp,
        mock_executor,
        mock_env_parser,
        collection_paths,
        bruno_env_single_path,
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
        _create_server(mock_mcp, mock_executor, [[]], mock_env_parser=mock_env_parser)
        tool_decorator = mock_mcp.tool.return_value
        list_environments_handler = tool_decorator.call_args_list[2][0][0]

        result = list_environments_handler()

        assert len(result) == 2
        assert result[0]["name"] == "local"
        assert result[0]["variables"]["baseUrl"] == "http://localhost:3000"
        assert result[1]["name"] == "production"
        assert result[1]["variables"]["apiKey"] == "{{process.env.API_KEY}}"
        mock_env_parser.list_environments.assert_called_once_with(
            collection_paths.sample_collection.resolve()
        )

    def test_list_environments_handles_empty_environments_directory(
        self, mock_mcp, mock_executor, mock_env_parser, bruno_env_single_path
    ):
        """Test tool returns empty list when no environments found."""
        mock_env_parser.list_environments.return_value = []
        _create_server(mock_mcp, mock_executor, [[]], mock_env_parser=mock_env_parser)
        tool_decorator = mock_mcp.tool.return_value
        list_environments_handler = tool_decorator.call_args_list[2][0][0]

        result = list_environments_handler()

        assert result == []


class TestListCollectionsTool:
    """Test list_collections MCP tool registration and handler."""

    def test_list_collections_tool_registered_and_callable(
        self, mock_mcp, mock_executor, collection_metadata, bruno_env_single_path
    ):
        """Test list_collections tool is registered and callable."""
        _create_server(mock_mcp, mock_executor, [collection_metadata[0]])
        tool_decorator = mock_mcp.tool.return_value
        list_collections_handler = tool_decorator.call_args_list[3][0][0]

        assert callable(list_collections_handler)
        assert list_collections_handler.__name__ == "list_collections"

    def test_list_collections_returns_all_with_name_and_path(
        self, mock_mcp, mock_executor, collection_metadata, bruno_env_two_paths
    ):
        """Test returns list of {name, path} for each collection."""
        _create_server(
            mock_mcp, mock_executor, [collection_metadata[0], collection_metadata[1]]
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
        self, mock_mcp, mock_executor, collection_metadata, bruno_env_single_path
    ):
        """Test single collection returns one entry."""
        _create_server(mock_mcp, mock_executor, [collection_metadata[0]])
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[3][0][0]
        result = handler()

        assert len(result) == 1
        assert result[0]["name"] == "sample_collection"
        assert "path" in result[0]


class TestSetActiveCollectionTool:
    """Test set_active_collection MCP tool registration and handler."""

    def test_set_active_collection_tool_registered(
        self, mock_mcp, mock_executor, collection_metadata, bruno_env_two_paths
    ):
        """Test set_active_collection tool is registered."""
        _create_server(
            mock_mcp, mock_executor, [collection_metadata[0], collection_metadata[1]]
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[4][0][0]

        assert callable(handler)
        assert handler.__name__ == "set_active_collection"

    def test_set_active_collection_switches_and_returns_name(
        self,
        mock_mcp,
        mock_executor,
        collection_metadata,
        bruno_env_two_paths,
    ):
        """Test switches active collection, returns new name, list_requests reflects change."""
        _create_server(
            mock_mcp, mock_executor, [collection_metadata[0], collection_metadata[1]]
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
        self, mock_mcp, mock_executor, collection_metadata, bruno_env_single_path
    ):
        """Test unknown collection_name raises ValueError with name in message."""
        _create_server(mock_mcp, mock_executor, [collection_metadata[0]])
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args_list[4][0][0]

        with pytest.raises(ValueError) as exc_info:
            handler(collection_name="nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_set_active_collection_works_with_qualified_name(
        self,
        mock_mcp,
        mock_executor,
        collection_metadata,
        bruno_env_star_path,
    ):
        """Test set_active_collection works with qualified names from /* path loading."""
        _create_server(
            mock_mcp,
            mock_executor,
            [collection_metadata[0], collection_metadata[1]],
        )
        tool_decorator = mock_mcp.tool.return_value
        set_handler = tool_decorator.call_args_list[4][0][0]
        list_handler = tool_decorator.call_args_list[1][0][0]

        result = set_handler(collection_name="collection_directory/Users_API")

        assert result == "collection_directory/Users_API"
        list_result = list_handler()
        assert len(list_result) == 1
        assert list_result[0]["id"] == "health/check"
