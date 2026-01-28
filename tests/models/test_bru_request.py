"""Tests for BruRequest model."""

import json

from bruno_mcp.models import BruRequest


class TestBruRequest:
    """Test the BruRequest Pydantic model."""

    def test_get_name_returns_meta_name(self):
        """Test get_name() returns name from meta."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={"name": "My Request", "type": "http", "seq": 1},
            method="GET",
            url="https://api.example.com/test",
            params={},
            headers={},
        )

        name = request.get_name()

        assert name == "My Request"

    def test_get_name_returns_default_when_missing(self):
        """Test get_name() returns default when name not in meta."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={"type": "http", "seq": 1},
            method="GET",
            url="https://api.example.com/test",
            params={},
            headers={},
        )

        name = request.get_name()

        assert name == "Unnamed Request"


class TestExtractPathParameters:
    """Test extract_path_parameters() method on BruRequest."""

    def test_extract_path_parameters_single(self):
        """Extracts single {{variable}} from URL."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={},
            method="GET",
            url="https://api.example.com/users/{{userId}}",
            params={},
            headers={},
        )

        params = request.extract_path_parameters()

        assert params == {"userId"}

    def test_extract_path_parameters_multiple(self):
        """Extracts multiple {{variable}} placeholders from URL."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={},
            method="GET",
            url="https://api.example.com/{{groupId}}/users/{{userId}}",
            params={},
            headers={},
        )

        params = request.extract_path_parameters()

        assert params == {"groupId", "userId"}

    def test_extract_path_parameters_ignores_process_env(self):
        """Does not extract {{process.env.VAR}} patterns."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={},
            method="GET",
            url="https://api.example.com/users/{{userId}}?token={{process.env.API_TOKEN}}",
            params={},
            headers={},
        )

        params = request.extract_path_parameters()

        assert params == {"userId"}
        assert "process.env.API_TOKEN" not in params

    def test_extract_path_parameters_no_variables(self):
        """Returns empty set when URL has no variables."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={},
            method="GET",
            url="https://api.example.com/users/123",
            params={},
            headers={},
        )

        params = request.extract_path_parameters()

        assert params == set()

    def test_extract_path_parameters_mixed_patterns(self):
        """Correctly extracts regular vars while ignoring process.env patterns."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={},
            method="GET",
            url="https://{{baseUrl}}/{{groupId}}/users/{{userId}}?key={{process.env.API_KEY}}",
            params={},
            headers={},
        )

        params = request.extract_path_parameters()

        assert params == {"baseUrl", "groupId", "userId"}
        assert "process.env.API_KEY" not in params


class TestWithOverrides:
    """Test with_overrides() method on BruRequest."""

    def test_with_overrides_query_params_only(self):
        """Test overriding query_params when body is None."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={"name": "Test Request"},
            method="GET",
            url="https://api.example.com/posts",
            params={"page": "1", "per_page": "20"},
            headers={},
        )

        new_request = request.with_overrides(query_params={"page": "2"})

        assert new_request.params == {"page": "2", "per_page": "20"}

    def test_with_overrides_query_params_merges_with_existing(self):
        """Test that query_params merge with existing params (not replace)."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={},
            method="GET",
            url="https://api.example.com/posts",
            params={"page": "1", "sort": "asc"},
            headers={},
        )

        new_request = request.with_overrides(query_params={"page": "2"})

        assert new_request.params == {"page": "2", "sort": "asc"}

    def test_with_overrides_body_only(self):
        """Test overriding body when query_params is None."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={},
            method="POST",
            url="https://api.example.com/users",
            params={},
            headers={},
            body={"type": "json", "content": '{"old": "data"}'},
        )

        new_request = request.with_overrides(body={"new": "data"})

        assert new_request.body["type"] == "json"
        body_content = json.loads(new_request.body["content"])
        assert body_content == {"new": "data"}

    def test_with_overrides_preserves_other_fields(self):
        """Test that other fields are preserved when applying overrides."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={"name": "Test Request", "type": "http", "seq": 1},
            method="POST",
            url="https://api.example.com/users",
            params={"page": "1"},
            headers={"Authorization": "Bearer token"},
            body={"type": "json", "content": '{"key": "value"}'},
            auth={"type": "bearer", "token": "abc123"},
        )

        new_request = request.with_overrides(body={"new": "data"})

        assert new_request.filepath == request.filepath
        assert new_request.meta == request.meta
        assert new_request.method == request.method
        assert new_request.url == request.url
        assert new_request.headers == request.headers
        assert new_request.auth == request.auth
        assert new_request.params == request.params
        assert new_request.body != request.body
