"""Tests for BruRequest model."""

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
