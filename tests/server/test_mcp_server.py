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
        server = MCPServer(
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
        server = MCPServer(
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
        server = MCPServer(
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
    def test_create_initializes_with_env_path(self, mock_fastmcp, mock_scanner_class, mock_parser_class, sample_collection_dir):
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


class TestRunBrunoRequestTool:
    """Test run_bruno_request MCP tool registration and handler."""

    def test_tool_registered_with_correct_name(self):
        """Test _register_tools calls mcp.tool() with bruno://request_by_id."""
        mock_mcp = Mock()
        server = MCPServer(
            collection_path=Path("/test"),
            bru_parser=Mock(spec=BruParser),
            env_parser=Mock(),
            executor=Mock(),
            resolver_cls=VariableResolver,
            scanner=Mock(),
            mcp=mock_mcp,
        )
        mock_mcp.tool.assert_called_once_with()

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
        mock_env_parser.load_environment.return_value = {"baseUrl": "https://api.example.com", "userId": "123"}
        mock_resolver = Mock(spec=VariableResolver)
        mock_executor = Mock(spec=RequestExecutor)
        mock_executor.execute.return_value = BruResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"id": "123", "name": "John"}',
        )
        mock_mcp = Mock()
        server = MCPServer(
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
        
        result = handler(request_id="users/get-user")

        assert result["status"] == 200
        assert result["headers"]["Content-Type"] == "application/json"
        assert result["body"] == '{"id": "123", "name": "John"}'
        mock_parser.parse_file.assert_called_once()
        mock_executor.execute.assert_called_once()
        call_args = mock_executor.execute.call_args
        assert isinstance(call_args[0][0], BruRequest)
        assert call_args[0][0].method == "GET"

    @pytest.mark.skip
    @patch("bruno_mcp.server.EnvParser")
    @patch("bruno_mcp.server.VariableResolver")
    @patch("bruno_mcp.server.RequestExecutor")
    def test_tool_applies_parameter_overrides(self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir):
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
        mock_resolver = mock_resolver_class.return_value
        mock_executor = mock_executor_class.return_value
        mock_executor.execute.return_value = BruResponse(status=200, headers={}, body="[]")
        mock_mcp = Mock()
        server = MCPServer(
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
    def test_tool_applies_body_override(self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir):
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
        mock_resolver = mock_resolver_class.return_value
        mock_executor = mock_executor_class.return_value
        mock_executor.execute.return_value = BruResponse(status=201, headers={}, body='{"id": "456"}')
        mock_mcp = Mock()
        server = MCPServer(
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
        override_body = {"name": "Jane", "email": "jane@example.com"}

        handler(request_id="users/create-user", body=override_body)

        call_args = mock_executor.execute.call_args
        request = call_args[0][0]
        assert request.body["type"] == "json"
        body_content = json.loads(request.body["content"])
        assert body_content["name"] == "Jane"
        assert body_content["email"] == "jane@example.com"

    @pytest.mark.skip
    @patch("bruno_mcp.server.EnvParser")
    @patch("bruno_mcp.server.VariableResolver")
    @patch("bruno_mcp.server.RequestExecutor")
    def test_tool_raises_error_for_invalid_request_id(self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir):
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
        mock_resolver = mock_resolver_class.return_value
        mock_executor = mock_executor_class.return_value
        mock_mcp = Mock()
        server = MCPServer(
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
    def test_tool_loads_collection_and_environment_variables(self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir):
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
        mock_env_parser.parse_collection.return_value = {"baseUrl": "https://api.example.com", "apiKey": "collection-key"}
        mock_env_parser.parse_environment.return_value = {"userId": "123", "apiKey": "env-key"}
        mock_resolver = mock_resolver_class.return_value
        mock_executor = mock_executor_class.return_value
        mock_executor.execute.return_value = BruResponse(status=200, headers={}, body="{}")
        mock_mcp = Mock()
        server = MCPServer(
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

        mock_env_parser.parse_collection.assert_called_once_with(sample_collection_dir / "bruno.json")
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
    def test_tool_resolves_variables_before_execution(self, mock_executor_class, mock_resolver_class, mock_env_parser_class, sample_collection_dir):
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
        mock_env_parser.parse_environment.return_value = {"userId": "123", "includeFields": "profile,posts", "authToken": "secret-token"}
        mock_resolver = mock_resolver_class.return_value
        mock_resolver.resolve.side_effect = lambda x: {
            "https://api.example.com/users/{{userId}}": "https://api.example.com/users/123",
            "{{includeFields}}": "profile,posts",
            "Bearer {{authToken}}": "Bearer secret-token",
        }.get(x, x)
        mock_executor = mock_executor_class.return_value
        mock_executor.execute.return_value = BruResponse(status=200, headers={}, body="{}")
        mock_mcp = Mock()
        server = MCPServer(
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
