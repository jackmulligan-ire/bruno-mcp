"""Tests for variable resolver - resolves {{variable}} placeholders."""

import pytest
import os

from bruno_mcp.resolvers import VariableResolver


class TestSimpleResolution:
    """Test basic variable resolution."""

    def test_resolve_collection_level_variable(self):
        """Test resolving variable from collection level."""
        resolver = VariableResolver(variables={"timeout": "5000"})

        result = resolver.resolve("Timeout is {{timeout}}ms")

        assert result == "Timeout is 5000ms"

    def test_resolve_environment_level_variable(self):
        """Test resolving variable from environment level."""
        resolver = VariableResolver(variables={"baseUrl": "http://localhost:3000"})

        result = resolver.resolve("{{baseUrl}}/api")

        assert result == "http://localhost:3000/api"

    def test_resolve_variable_in_url(self):
        """Test resolving multiple variables in URL."""
        resolver = VariableResolver(variables={"baseUrl": "http://localhost:3000", "userId": "123"})

        result = resolver.resolve("{{baseUrl}}/users/{{userId}}")

        assert result == "http://localhost:3000/users/123"

    def test_resolve_variable_in_headers(self):
        """Test resolving variables in header values."""
        resolver = VariableResolver(variables={"authToken": "abc123token"})

        result = resolver.resolve("Bearer {{authToken}}")

        assert result == "Bearer abc123token"

    def test_resolve_variable_in_body(self):
        """Test resolving variables in request body."""
        resolver = VariableResolver(variables={"userId": "123", "name": "John"})
        body = '{"userId": "{{userId}}", "name": "{{name}}"}'

        result = resolver.resolve(body)

        assert result == '{"userId": "123", "name": "John"}'


class TestPrecedenceAndOverriding:
    """Test variable precedence when multiple sources exist."""

    def test_environment_variable_overrides_collection(self):
        """Test that environment vars take precedence over collection vars."""
        collection_vars = {"baseUrl": "https://api.example.com"}
        environment_vars = {"baseUrl": "http://localhost:3000"}

        resolver = VariableResolver(variables={**collection_vars, **environment_vars})

        result = resolver.resolve("{{baseUrl}}")

        assert result == "http://localhost:3000"

    def test_resolve_with_multiple_layers(self):
        """Test resolution with collection + environment + multiple variables."""
        resolver = VariableResolver(
            variables={
                "defaultTimeout": "5000",
                "baseUrl": "http://localhost:3000",
                "userId": "123",
                "apiVersion": "v1",
            }
        )

        result = resolver.resolve("{{baseUrl}}/{{apiVersion}}/users/{{userId}}")

        assert result == "http://localhost:3000/v1/users/123"


class TestAdvancedFeatures:
    """Test nested variables and process.env resolution."""

    def test_resolve_nested_variables(self):
        """Test resolving nested variable references like {{urls.{{env}}}}."""
        resolver = VariableResolver(
            variables={
                "env": "local",
                "urls.local": "http://localhost:3000",
                "urls.prod": "https://api.example.com",
            }
        )

        result = resolver.resolve("{{urls.{{env}}}}")

        assert result == "http://localhost:3000"

    def test_resolve_process_env_variable(self):
        """Test resolving {{process.env.VAR}} from system environment."""
        os.environ["TEST_SECRET_TOKEN"] = "secret123"
        resolver = VariableResolver(variables={"authToken": "{{process.env.TEST_SECRET_TOKEN}}"})

        result = resolver.resolve("Bearer {{authToken}}")

        assert result == "Bearer secret123"
        del os.environ["TEST_SECRET_TOKEN"]


class TestErrorHandling:
    """Test error handling for missing or invalid variables."""

    def test_missing_variable_raises_error(self):
        """Test that missing variable raises clear error."""
        resolver = VariableResolver(variables={"userId": "123"})

        with pytest.raises(Exception) as exc_info:
            resolver.resolve("{{baseUrl}}/users/{{userId}}")

        assert "baseUrl" in str(exc_info.value)


class TestIntegration:
    """Integration tests for complete request resolution."""

    def test_resolve_entire_bru_request(self, sample_collection_dir):
        """Test resolving all fields of a BruRequest with precedence."""
        from bruno_mcp.parsers import BruParser

        parser = BruParser()
        request = parser.parse_file(str(sample_collection_dir / "users" / "get-user.bru"))

        resolver = VariableResolver(variables={"userId": "123", "authToken": "abc123"})

        resolved_url = resolver.resolve(request.url)
        resolved_auth_header = resolver.resolve(request.headers.get("Authorization", ""))

        assert resolved_url == "https://api.example.com/users/123"
        assert resolved_auth_header == "Bearer abc123"
