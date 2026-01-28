"""Tests for MCP server resources and tools."""

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from bruno_mcp.parsers import BruParser
from bruno_mcp import MCPServer
from bruno_mcp.models import BruRequest, BruResponse, RequestMetadata
from bruno_mcp.resolvers import VariableResolver
from bruno_mcp.executors import RequestExecutor
from bruno_mcp.parsers import EnvParser


class TestCollectionTreeResource:
    """Test collection_tree MCP resource registration and handler."""

    def test_resource_registered_with_correct_uri(self):
        """Test _register_resources calls mcp.resource() with bruno://collection."""
        mock_mcp = Mock()
        MCPServer(
            collection_path=Path("/test"),
            bru_parser=Mock(spec=BruParser),
            env_parser=Mock(),
            executor=Mock(),
            resolver_cls=VariableResolver,
            scanner=Mock(),
            mcp=mock_mcp,
        )

        mock_mcp.resource.assert_called_once_with("bruno://collection")

    def test_collection_tree_handler_returns_all_requests(self):
        """Test collection_tree handler returns all requests from scanner."""
        mock_scanner = Mock()
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
        mock_scanner.scan_collection.return_value = expected_requests
        mock_mcp = Mock()
        MCPServer(
            collection_path=Path("/test"),
            bru_parser=Mock(spec=BruParser),
            env_parser=Mock(),
            executor=Mock(),
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )

        resource_decorator = mock_mcp.resource.return_value
        collection_tree_handler = resource_decorator.call_args[0][0]
        collection_tree = collection_tree_handler()

        assert len(collection_tree) == 2
        assert collection_tree[0]["id"] == "users/get-user"
        assert collection_tree[1]["id"] == "users/create-user"

    def test_collection_tree_handler_includes_complete_metadata(self):
        """Test collection_tree handler returns all required metadata fields."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ]
        mock_mcp = Mock()
        MCPServer(
            collection_path=Path("/test"),
            bru_parser=Mock(spec=BruParser),
            env_parser=Mock(),
            executor=Mock(),
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )

        resource_decorator = mock_mcp.resource.return_value
        handler = resource_decorator.call_args[0][0]
        result = handler()

        request = result[0]
        assert request["id"] == "users/get-user"
        assert request["name"] == "Get User"
        assert request["method"] == "GET"
        assert request["url"] == "https://api.example.com/users/{{userId}}"
        assert request["file_path"] == "users/get-user.bru"


class TestServerCreate:
    """Test MCPServer.create() factory method."""

    @patch("bruno_mcp.server.BruParser")
    @patch("bruno_mcp.server.CollectionScanner")
    @patch("bruno_mcp.server.FastMCP")
    def test_create_initializes_with_env_path(
        self, mock_fastmcp, mock_scanner_class, mock_parser_class, sample_collection_dir
    ):
        """Test MCPServer.create() reads BRUNO_COLLECTION_PATH from environment."""
        mock_parser_instance = mock_parser_class.return_value

        server = MCPServer.create()

        assert server._collection_path.resolve() == sample_collection_dir
        mock_parser_class.assert_called_once()
        mock_scanner_class.assert_called_once_with(mock_parser_instance)
        mock_fastmcp.assert_called_once_with("bruno-mcp")

    @patch.dict(os.environ, {}, clear=True)
    def test_create_raises_error_without_collection_path(self):
        """Test MCPServer.create() raises error when BRUNO_COLLECTION_PATH not set."""
        with pytest.raises(ValueError, match="BRUNO_COLLECTION_PATH"):
            MCPServer.create()


class TestListRequestsTool:
    """Test list_requests MCP tool registration and handler."""

    def test_list_requests_handler_callable(self):
        """Test list_requests handler is registered and callable."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = []
        mock_mcp = Mock()

        MCPServer(
            collection_path=Path("/test"),
            bru_parser=Mock(spec=BruParser),
            env_parser=Mock(),
            executor=Mock(),
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )

        assert mock_mcp.tool.call_count == 2
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        list_requests_handler = all_calls[1][0][0]
        assert callable(list_requests_handler)
        assert list_requests_handler.__name__ == "list_requests"

    def test_list_requests_returns_expected_endpoints(self):
        """Test list_requests returns all requests from collection."""
        mock_scanner = Mock()
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
        mock_scanner.scan_collection.return_value = expected_requests
        mock_mcp = Mock()

        MCPServer(
            collection_path=Path("/test"),
            bru_parser=Mock(spec=BruParser),
            env_parser=Mock(),
            executor=Mock(),
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args[0][0]

        result = handler()

        assert len(result) == 3
        assert result[0]["id"] == "users/get-user"
        assert result[1]["id"] == "posts/create-post"
        assert result[2]["id"] == "posts/list-posts"

    def test_list_requests_returns_complete_endpoint_metadata(self):
        """Test each endpoint includes all required metadata fields."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="users/delete-user",
                name="Delete User",
                method="DELETE",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/delete-user.bru",
            )
        ]
        mock_mcp = Mock()

        MCPServer(
            collection_path=Path("/test"),
            bru_parser=Mock(spec=BruParser),
            env_parser=Mock(),
            executor=Mock(),
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args[0][0]

        result = handler()

        endpoint = result[0]
        assert endpoint["id"] == "users/delete-user"
        assert endpoint["name"] == "Delete User"
        assert endpoint["method"] == "DELETE"
        assert endpoint["url"] == "https://api.example.com/users/{{userId}}"
        assert endpoint["file_path"] == "users/delete-user.bru"
        assert "{{userId}}" in endpoint["url"]

    def test_list_requests_handles_empty_collection(self):
        """Test list_requests returns empty list when collection is empty."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = []
        mock_mcp = Mock()

        MCPServer(
            collection_path=Path("/empty"),
            bru_parser=Mock(spec=BruParser),
            env_parser=Mock(),
            executor=Mock(),
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args[0][0]

        result = handler()

        assert result == []
        assert isinstance(result, list)


class TestRunBrunoRequestTool:
    """Test run_bruno_request MCP tool registration and handler."""

    def test_tool_registered_with_correct_name(self):
        """Test _register_tools calls mcp.tool() for run_request_by_id."""
        mock_mcp = Mock()
        MCPServer(
            collection_path=Path("/test"),
            bru_parser=Mock(spec=BruParser),
            env_parser=Mock(),
            executor=Mock(),
            resolver_cls=VariableResolver,
            scanner=Mock(),
            mcp=mock_mcp,
        )
        assert mock_mcp.tool.call_count == 2
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        run_request_handler = all_calls[0][0][0]
        assert run_request_handler.__name__ == "run_request_by_id"

    def test_tool_executes_request_by_id(self, sample_collection_dir):
        """Test tool handler executes request by ID and returns response."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "users" / "get-user.bru"),
            meta={"name": "Get User"},
            method="GET",
            url="https://api.example.com/users/{{userId}}",
            params={"include": "profile"},
            headers={"Accept": "application/json"},
            body=None,
            auth=None,
        )
        mock_env_parser = Mock(spec=EnvParser)
        mock_env_parser.load_environment.return_value = {
            "baseUrl": "https://api.example.com",
            "userId": "123",
        }
        Mock(spec=VariableResolver)
        mock_executor = Mock(spec=RequestExecutor)
        mock_executor.execute.return_value = BruResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"id": "123", "name": "John"}',
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]

        result = handler(request_id="users/get-user")

        assert result["status"] == 200
        assert result["headers"]["Content-Type"] == "application/json"
        assert result["body"] == '{"id": "123", "name": "John"}'
        mock_parser.parse_file.assert_called_once()
        mock_executor.execute.assert_called_once()
        call_args = mock_executor.execute.call_args
        assert isinstance(call_args[0][0], BruRequest)
        assert call_args[0][0].method == "GET"

    def test_tool_substitutes_single_path_parameter(self, sample_collection_dir):
        """Test single path parameter substitution via path_params."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "users" / "get-user.bru"),
            meta={"name": "Get User"},
            method="GET",
            url="https://api.example.com/users/{{userId}}",
            params={},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = Mock(spec=EnvParser)
        mock_env_parser.load_environment.return_value = {}
        mock_executor = Mock(spec=RequestExecutor)
        mock_executor.execute.return_value = BruResponse(
            status=200,
            headers={},
            body='{"id": "456"}',
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]

        result = handler(request_id="users/get-user", path_params={"userId": "456"})

        assert result["status"] == 200
        mock_executor.execute.assert_called_once()
        call_args = mock_executor.execute.call_args
        resolver = call_args[0][1]
        assert resolver.variables["userId"] == "456"

    def test_tool_substitutes_multiple_path_parameters(self, sample_collection_dir):
        """Test multiple path parameter substitution via path_params."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="groups/users",
                name="Get User in Group",
                method="GET",
                url="https://api.example.com/{{groupId}}/users/{{userId}}",
                file_path="groups/users.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "groups" / "users.bru"),
            meta={"name": "Get User in Group"},
            method="GET",
            url="https://api.example.com/{{groupId}}/users/{{userId}}",
            params={},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = Mock(spec=EnvParser)
        mock_env_parser.load_environment.return_value = {}
        mock_executor = Mock(spec=RequestExecutor)
        mock_executor.execute.return_value = BruResponse(
            status=200,
            headers={},
            body='{"id": "123"}',
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]

        result = handler(request_id="groups/users", path_params={"groupId": "789", "userId": "123"})

        assert result["status"] == 200
        mock_executor.execute.assert_called_once()
        call_args = mock_executor.execute.call_args
        resolver = call_args[0][1]
        assert resolver.variables["groupId"] == "789"
        assert resolver.variables["userId"] == "123"

    def test_tool_path_params_override_environment_variables(self, sample_collection_dir):
        """Test user-provided path_params override environment variables."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "users" / "get-user.bru"),
            meta={"name": "Get User"},
            method="GET",
            url="https://api.example.com/users/{{userId}}",
            params={},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = Mock(spec=EnvParser)
        mock_env_parser.load_environment.return_value = {"userId": "999"}
        mock_executor = Mock(spec=RequestExecutor)
        mock_executor.execute.return_value = BruResponse(
            status=200,
            headers={},
            body='{"id": "456"}',
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]

        result = handler(request_id="users/get-user", path_params={"userId": "456"})

        assert result["status"] == 200
        mock_executor.execute.assert_called_once()
        call_args = mock_executor.execute.call_args
        resolver = call_args[0][1]
        assert resolver.variables["userId"] == "456"

    def test_tool_validates_missing_path_parameters(self, sample_collection_dir):
        """Test error when required path parameters are missing."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "users" / "get-user.bru"),
            meta={"name": "Get User"},
            method="GET",
            url="https://api.example.com/users/{{userId}}",
            params={},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = Mock(spec=EnvParser)
        mock_env_parser.load_environment.return_value = {}
        executor = RequestExecutor()
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]

        with pytest.raises(ValueError) as exc_info:
            handler(request_id="users/get-user")

        assert "Missing required path parameters" in str(exc_info.value)
        assert "userId" in str(exc_info.value)

    def test_tool_handles_path_params_with_existing_env_vars(self, sample_collection_dir):
        """Test mixing user path_params with existing environment variables."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="groups/users",
                name="Get User in Group",
                method="GET",
                url="https://api.example.com/{{groupId}}/users/{{userId}}",
                file_path="groups/users.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "groups" / "users.bru"),
            meta={"name": "Get User in Group"},
            method="GET",
            url="https://api.example.com/{{groupId}}/users/{{userId}}",
            params={},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = Mock(spec=EnvParser)
        mock_env_parser.load_environment.return_value = {"groupId": "100"}
        mock_executor = Mock(spec=RequestExecutor)
        mock_executor.execute.return_value = BruResponse(
            status=200,
            headers={},
            body='{"id": "123"}',
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]

        result = handler(request_id="groups/users", path_params={"userId": "123"})

        assert result["status"] == 200
        mock_executor.execute.assert_called_once()
        call_args = mock_executor.execute.call_args
        resolver = call_args[0][1]
        assert resolver.variables["groupId"] == "100"
        assert resolver.variables["userId"] == "123"

    @pytest.mark.skip
    @patch("bruno_mcp.server.EnvParser")
    @patch("bruno_mcp.server.VariableResolver")
    @patch("bruno_mcp.server.RequestExecutor")
    def test_tool_applies_parameter_overrides(
        self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir
    ):
        """Test tool applies optional parameter overrides to request."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="posts/list-posts",
                name="List Posts",
                method="GET",
                url="https://api.example.com/posts",
                file_path="posts/list-posts.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "posts" / "list-posts.bru"),
            meta={"name": "List Posts"},
            method="GET",
            url="https://api.example.com/posts",
            params={"page": "1", "per_page": "20"},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = mock_env_parser_class.return_value
        mock_env_parser.parse_collection.return_value = {}
        mock_env_parser.parse_environment.return_value = {}
        mock_executor = mock_executor_class.return_value
        mock_executor.execute.return_value = BruResponse(status=200, headers={}, body="[]")
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args[0][0]

        handler(request_id="posts/list-posts", params={"page": "2", "per_page": "50"})

        call_args = mock_executor.execute.call_args
        request = call_args[0][0]
        assert request.params["page"] == "2"
        assert request.params["per_page"] == "50"

    @pytest.mark.skip
    @patch("bruno_mcp.server.EnvParser")
    @patch("bruno_mcp.server.VariableResolver")
    @patch("bruno_mcp.server.RequestExecutor")
    def test_tool_raises_error_for_invalid_request_id(
        self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir
    ):
        """Test tool raises error when request_id not found in collection."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_env_parser = mock_env_parser_class.return_value
        mock_executor = mock_executor_class.return_value
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args[0][0]

        with pytest.raises(ValueError, match="Request not found"):
            handler(request_id="users/nonexistent")

    @pytest.mark.skip
    @patch("bruno_mcp.server.EnvParser")
    @patch("bruno_mcp.server.VariableResolver")
    @patch("bruno_mcp.server.RequestExecutor")
    def test_tool_loads_collection_and_environment_variables(
        self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir
    ):
        """Test tool loads collection and environment variables correctly."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "users" / "get-user.bru"),
            meta={"name": "Get User"},
            method="GET",
            url="https://api.example.com/users/{{userId}}",
            params={},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = mock_env_parser_class.return_value
        mock_env_parser.parse_collection.return_value = {
            "baseUrl": "https://api.example.com",
            "apiKey": "collection-key",
        }
        mock_env_parser.parse_environment.return_value = {"userId": "123", "apiKey": "env-key"}
        mock_executor = mock_executor_class.return_value
        mock_executor.execute.return_value = BruResponse(status=200, headers={}, body="{}")
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args[0][0]

        handler(request_id="users/get-user")

        mock_env_parser.parse_collection.assert_called_once_with(
            sample_collection_dir / "bruno.json"
        )
        mock_env_parser.parse_environment.assert_called_once()
        mock_resolver_class.assert_called_once()
        resolver_vars = mock_resolver_class.call_args[0][0]
        assert resolver_vars["baseUrl"] == "https://api.example.com"
        assert resolver_vars["apiKey"] == "env-key"
        assert resolver_vars["userId"] == "123"

    @pytest.mark.skip
    @patch("bruno_mcp.server.EnvParser")
    @patch("bruno_mcp.server.VariableResolver")
    @patch("bruno_mcp.server.RequestExecutor")
    def test_tool_resolves_variables_before_execution(
        self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir
    ):
        """Test tool resolves variables in URL, headers, params, and body before execution."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="users/get-user",
                name="Get User",
                method="GET",
                url="https://api.example.com/users/{{userId}}",
                file_path="users/get-user.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "users" / "get-user.bru"),
            meta={"name": "Get User"},
            method="GET",
            url="https://api.example.com/users/{{userId}}",
            params={"include": "{{includeFields}}"},
            headers={"Authorization": "Bearer {{authToken}}"},
            body=None,
            auth=None,
        )
        mock_env_parser = mock_env_parser_class.return_value
        mock_env_parser.parse_collection.return_value = {"baseUrl": "https://api.example.com"}
        mock_env_parser.parse_environment.return_value = {
            "userId": "123",
            "includeFields": "profile,posts",
            "authToken": "secret-token",
        }
        mock_resolver = mock_resolver_class.return_value
        mock_resolver.resolve.side_effect = lambda x: {
            "https://api.example.com/users/{{userId}}": "https://api.example.com/users/123",
            "{{includeFields}}": "profile,posts",
            "Bearer {{authToken}}": "Bearer secret-token",
        }.get(x, x)
        mock_executor = mock_executor_class.return_value
        mock_executor.execute.return_value = BruResponse(status=200, headers={}, body="{}")
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        handler = tool_decorator.call_args[0][0]

        handler(request_id="users/get-user")

        assert mock_resolver.resolve.called
        call_args = mock_executor.execute.call_args
        assert call_args is not None


class TestBodyParameter:
    """Test body parameter functionality"""

    @patch("bruno_mcp.server.EnvParser")
    @patch("bruno_mcp.server.VariableResolver")
    @patch("bruno_mcp.server.RequestExecutor")
    def test_tool_applies_body_override(
        self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir
    ):
        """Test tool applies optional body override to request."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="users/create-user",
                name="Create User",
                method="POST",
                url="https://api.example.com/users",
                file_path="users/create-user.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "users" / "create-user.bru"),
            meta={"name": "Create User"},
            method="POST",
            url="https://api.example.com/users",
            params={},
            headers={"Content-Type": "application/json"},
            body={"type": "json", "content": '{"name": "John", "email": "john@example.com"}'},
            auth=None,
        )
        mock_env_parser = mock_env_parser_class.return_value
        mock_env_parser.parse_collection.return_value = {}
        mock_env_parser.parse_environment.return_value = {}
        mock_executor = mock_executor_class.return_value
        mock_executor.execute.return_value = BruResponse(
            status=201, headers={}, body='{"id": "456"}'
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]
        override_body = {"name": "Jane", "email": "jane@example.com"}

        handler(request_id="users/create-user", body=override_body)

        call_args = mock_executor.execute.call_args
        request = call_args[0][0]
        assert request.body["type"] == "json"
        body_content = json.loads(request.body["content"])
        assert body_content["name"] == "Jane"
        assert body_content["email"] == "jane@example.com"

    def test_tool_body_parameter_adds_body_when_none_exists(self, sample_collection_dir):
        """Test body parameter adds body when .bru file has no body."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="posts/create-post",
                name="Create Post",
                method="POST",
                url="https://api.example.com/posts",
                file_path="posts/create-post.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "posts" / "create-post.bru"),
            meta={"name": "Create Post"},
            method="POST",
            url="https://api.example.com/posts",
            params={},
            headers={"Content-Type": "application/json"},
            body=None,
            auth=None,
        )
        mock_env_parser = Mock(spec=EnvParser)
        mock_env_parser.load_environment.return_value = {}
        mock_executor = Mock(spec=RequestExecutor)
        mock_executor.execute.return_value = BruResponse(
            status=201, headers={}, body='{"id": "789"}'
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]
        new_body = {"title": "My Post", "content": "Post content"}

        handler(request_id="posts/create-post", body=new_body)

        call_args = mock_executor.execute.call_args
        request = call_args[0][0]
        assert request.body is not None
        assert request.body["type"] == "json"
        body_content = json.loads(request.body["content"])
        assert body_content["title"] == "My Post"
        assert body_content["content"] == "Post content"


class TestQueryParamsParameter:
    """Test query_params parameter functionality"""

    @patch("bruno_mcp.server.EnvParser")
    @patch("bruno_mcp.server.VariableResolver")
    @patch("bruno_mcp.server.RequestExecutor")
    def test_tool_applies_query_params_override(
        self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir
    ):
        """Test tool applies query_params override to request."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="posts/list-posts",
                name="List Posts",
                method="GET",
                url="https://api.example.com/posts",
                file_path="posts/list-posts.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "posts" / "list-posts.bru"),
            meta={"name": "List Posts"},
            method="GET",
            url="https://api.example.com/posts",
            params={"page": "1", "per_page": "20"},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = mock_env_parser_class.return_value
        mock_env_parser.load_environment.return_value = {}
        mock_executor = mock_executor_class.return_value
        mock_executor.execute.return_value = BruResponse(
            status=200, headers={}, body='{"posts": []}'
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]
        override_params = {"page": "2", "per_page": "50"}

        handler(request_id="posts/list-posts", query_params=override_params)

        call_args = mock_executor.execute.call_args
        request = call_args[0][0]
        assert request.params["page"] == "2"
        assert request.params["per_page"] == "50"

    def test_tool_query_params_merge_with_existing_params(self, sample_collection_dir):
        """Test query_params only override specified keys, keeping others from .bru file."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="posts/list-posts",
                name="List Posts",
                method="GET",
                url="https://api.example.com/posts",
                file_path="posts/list-posts.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "posts" / "list-posts.bru"),
            meta={"name": "List Posts"},
            method="GET",
            url="https://api.example.com/posts",
            params={"page": "1", "per_page": "20", "sort": "created_at"},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = Mock(spec=EnvParser)
        mock_env_parser.load_environment.return_value = {}
        mock_executor = Mock(spec=RequestExecutor)
        mock_executor.execute.return_value = BruResponse(
            status=200, headers={}, body='{"posts": []}'
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]

        handler(request_id="posts/list-posts", query_params={"page": "2"})

        call_args = mock_executor.execute.call_args
        request = call_args[0][0]
        assert request.params["page"] == "2"
        assert request.params["per_page"] == "20"
        assert request.params["sort"] == "created_at"

    def test_tool_query_params_add_params_when_none_exist(self, sample_collection_dir):
        """Test query_params can add params when .bru file has no params."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="posts/simple-get",
                name="Simple Get",
                method="GET",
                url="https://api.example.com/posts",
                file_path="posts/simple-get.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "posts" / "simple-get.bru"),
            meta={"name": "Simple Get"},
            method="GET",
            url="https://api.example.com/posts",
            params={},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = Mock(spec=EnvParser)
        mock_env_parser.load_environment.return_value = {}
        mock_executor = Mock(spec=RequestExecutor)
        mock_executor.execute.return_value = BruResponse(
            status=200, headers={}, body='{"posts": []}'
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]
        new_params = {"pageSize": "50", "pageNum": "2"}

        handler(request_id="posts/simple-get", query_params=new_params)

        call_args = mock_executor.execute.call_args
        request = call_args[0][0]
        assert request.params["pageSize"] == "50"
        assert request.params["pageNum"] == "2"

    def test_tool_query_params_override_bru_file_params_with_variables(self, sample_collection_dir):
        """Test query_params override .bru file params even when .bru file params contain variables."""
        mock_scanner = Mock()
        mock_scanner.scan_collection.return_value = [
            RequestMetadata(
                id="posts/list-posts",
                name="List Posts",
                method="GET",
                url="https://api.example.com/posts",
                file_path="posts/list-posts.bru",
            )
        ]
        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath=str(sample_collection_dir / "posts" / "list-posts.bru"),
            meta={"name": "List Posts"},
            method="GET",
            url="https://api.example.com/posts",
            params={"page": "{{defaultPage}}"},
            headers={},
            body=None,
            auth=None,
        )
        mock_env_parser = Mock(spec=EnvParser)
        mock_env_parser.load_environment.return_value = {"defaultPage": "1"}
        mock_executor = Mock(spec=RequestExecutor)
        mock_executor.execute.return_value = BruResponse(
            status=200, headers={}, body='{"posts": []}'
        )
        mock_mcp = Mock()
        MCPServer(
            collection_path=sample_collection_dir,
            bru_parser=mock_parser,
            env_parser=mock_env_parser,
            executor=mock_executor,
            resolver_cls=VariableResolver,
            scanner=mock_scanner,
            mcp=mock_mcp,
        )
        tool_decorator = mock_mcp.tool.return_value
        all_calls = tool_decorator.call_args_list
        handler = all_calls[0][0][0]

        handler(request_id="posts/list-posts", query_params={"page": "5"})

        call_args = mock_executor.execute.call_args
        request = call_args[0][0]
        assert request.params["page"] == "5"
