"""Tests for HTTP request execution."""
import pytest
import respx
import httpx
import os

from bruno_mcp.parsers import BruParser
from bruno_mcp.resolvers import VariableResolver
from bruno_mcp.executors import RequestExecutor


class TestHTTPMethods:
    """Test execution of different HTTP methods."""

    @respx.mock
    def test_execute_get_request(self):
        """Test executing GET request with query params."""
        respx.get("https://api.example.com/users/123").mock(
            return_value=httpx.Response(200, json={"name": "John"})
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={"userId": "123", "authToken": "test_token"})
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/get-user.bru"
        )

        response = executor.execute(request, resolver)

        assert response.status == 200
        assert "John" in response.body

    @respx.mock
    def test_execute_post_with_json_body(self):
        """Test executing POST request with JSON body and auth."""
        route = respx.post("https://api.example.com/users").mock(
            return_value=httpx.Response(201, json={"id": 456})
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={"authToken": "abc123"})
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/create-user.bru"
        )

        response = executor.execute(request, resolver)

        assert response.status == 201
        assert "456" in response.body
        assert route.calls.last.request.headers["Authorization"] == "Bearer abc123"

    @respx.mock
    def test_execute_put_request(self):
        """Test executing PUT request with JSON body and auth."""
        route = respx.put("https://api.example.com/users/123").mock(
            return_value=httpx.Response(200, json={"updated": True})
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={"userId": "123", "authToken": "abc123"})
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/update-user.bru"
        )

        response = executor.execute(request, resolver)

        assert response.status == 200
        assert "updated" in response.body
        assert route.calls.last.request.headers["Authorization"] == "Bearer abc123"

    @respx.mock
    def test_execute_delete_request(self):
        """Test executing DELETE request."""
        respx.delete("https://api.example.com/users/123").mock(
            return_value=httpx.Response(204)
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={"userId": "123", "authToken": "abc123"})
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/delete-user.bru"
        )

        response = executor.execute(request, resolver)

        assert response.status == 204


class TestResponseStructure:
    """Test response structure and metadata."""

    @respx.mock
    def test_response_includes_status_and_headers(self):
        """Test response contains status code and headers."""
        respx.get("https://api.example.com/users/123").mock(
            return_value=httpx.Response(
                200,
                json={"id": 123},
                headers={"Content-Type": "application/json"}
            )
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={"userId": "123", "authToken": "abc123"})
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/get-user.bru"
        )

        response = executor.execute(request, resolver)

        assert response.status == 200
        assert "content-type" in response.headers


class TestAuthentication:
    """Test authentication handling."""

    @respx.mock
    def test_execute_with_bearer_token(self):
        """Test request includes resolved Bearer token in headers."""
        route = respx.get("https://api.example.com/users/123").mock(
            return_value=httpx.Response(200, json={"id": 123})
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={"userId": "123", "authToken": "secret_token"})
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/get-user.bru"
        )

        response = executor.execute(request, resolver)

        assert route.called
        assert route.calls.last.request.headers["Authorization"] == "Bearer secret_token"
        assert response.status == 200
        assert "123" in response.body


class TestErrorHandling:
    """Test handling of HTTP errors and network failures."""

    @respx.mock
    def test_http_error_4xx_response(self):
        """Test handling of 4xx client errors."""
        respx.get("https://api.example.com/users/999").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={"userId": "999", "authToken": "abc123"})
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/get-user.bru"
        )

        response = executor.execute(request, resolver)

        assert response.status == 404
        assert "error" in response.body

    @respx.mock
    def test_http_error_5xx_response(self):
        """Test handling of 5xx server errors."""
        respx.post("https://api.example.com/users").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={"authToken": "abc123"})
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/create-user.bru"
        )

        response = executor.execute(request, resolver)

        assert response.status == 500
        assert "error" in response.body

    @respx.mock
    def test_connection_error(self):
        """Test handling of network connection failures."""
        respx.get("https://api.example.com/users/123").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={"userId": "123", "authToken": "abc123"})
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/get-user.bru"
        )

        with pytest.raises(httpx.ConnectError):
            executor.execute(request, resolver)


class TestIntegration:
    """Integration test with full request flow."""

    @respx.mock
    def test_execute_with_resolved_variables(self):
        """Test complete flow: parse, resolve, execute."""
        respx.get("https://api.example.com/users/123").mock(
            return_value=httpx.Response(200, json={"id": 123, "name": "Test User"})
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={
            "baseUrl": "https://api.example.com",
            "apiVersion": "v1",
            "userId": "123",
            "authToken": "test_token"
        })
        
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/get-user.bru"
        )

        response = executor.execute(request, resolver)

        assert response.status == 200
        assert "Test User" in response.body

    @respx.mock
    def test_execute_with_nested_variables(self):
        """Test complete flow with nested variable resolution."""
        respx.get("https://api.example.com/users/123").mock(
            return_value=httpx.Response(200, json={"id": 123, "name": "Nested Test"})
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={
            "env": "local",
            "urls.local": "http://localhost:3000",
            "urls.prod": "https://api.example.com",
            "userId": "123",
            "authToken": "nested_token"
        })
        
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/get-user.bru"
        )

        response = executor.execute(request, resolver)

        assert response.status == 200
        assert "Nested Test" in response.body

    @respx.mock
    def test_execute_with_process_env_variable(self):
        """Test complete flow with process.env variable resolution."""
        
        os.environ["TEST_API_TOKEN"] = "env_secret_token"
        
        respx.get("https://api.example.com/users/123").mock(
            return_value=httpx.Response(200, json={"id": 123, "name": "Env Test"})
        )
        
        executor = RequestExecutor()
        resolver = VariableResolver(variables={
            "userId": "123",
            "authToken": "{{process.env.TEST_API_TOKEN}}"
        })
        
        request = BruParser().parse_file(
            "tests/fixtures/sample_collection/users/get-user.bru"
        )

        response = executor.execute(request, resolver)

        assert response.status == 200
        assert "Env Test" in response.body
        
        del os.environ["TEST_API_TOKEN"]
