"""Tests for BruParser - Bruno .bru file parser."""
import pytest

from bruno_mcp.parsers import BruParser


class TestBruParserGETRequests:
    """Test parsing GET requests."""

    def test_parse_simple_get_request(self, sample_collection_dir):
        """Test parsing a basic GET request with query params and headers."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "get-user.bru"

        request = parser.parse_file(str(filepath))

        assert request.method == "GET"
        assert request.url == "https://api.example.com/users/{{userId}}"
        assert request.meta["name"] == "Get User"

    def test_parse_get_with_query_params(self, sample_collection_dir):
        """Test parsing query parameters."""
        parser = BruParser()
        filepath = sample_collection_dir / "posts" / "list-posts.bru"

        request = parser.parse_file(str(filepath))

        assert request.params["page"] == "1"
        assert request.params["per_page"] == "20"

    def test_parse_get_with_headers(self, sample_collection_dir):
        """Test parsing headers."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "get-user.bru"

        request = parser.parse_file(str(filepath))

        assert request.headers["Authorization"] == "Bearer {{authToken}}"
        assert request.headers["Accept"] == "application/json"

    def test_parse_get_without_body(self, sample_collection_dir):
        """Test parsing GET request without body."""
        parser = BruParser()
        filepath = sample_collection_dir / "posts" / "simple-get.bru"

        request = parser.parse_file(str(filepath))

        assert request.method == "GET"
        assert request.body is None


class TestBruParserPOSTRequests:
    """Test parsing POST requests with bodies."""

    def test_parse_post_with_json_body(self, sample_collection_dir):
        """Test parsing POST request with JSON body."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "create-user.bru"

        request = parser.parse_file(str(filepath))

        assert request.method == "POST"
        assert request.body["type"] == "json"
        assert '"name": "John Doe"' in request.body["content"]

    def test_parse_post_with_form_urlencoded(self, sample_collection_dir):
        """Test parsing POST with form-urlencoded body."""
        parser = BruParser()
        filepath = sample_collection_dir / "posts" / "form-data.bru"

        request = parser.parse_file(str(filepath))

        assert request.body["type"] == "form-urlencoded"
        assert "username" in request.body["content"]


class TestBruParserOtherMethods:
    """Test parsing PUT and DELETE requests."""

    def test_parse_put_request(self, sample_collection_dir):
        """Test parsing PUT request."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "update-user.bru"

        request = parser.parse_file(str(filepath))

        assert request.method == "PUT"
        assert request.body["type"] == "json"
        assert '"name": "Updated Name"' in request.body["content"]

    def test_parse_delete_request(self, sample_collection_dir):
        """Test parsing DELETE request."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "delete-user.bru"

        request = parser.parse_file(str(filepath))

        assert request.method == "DELETE"
        assert request.body is None


class TestBruParserMetadata:
    """Test parsing meta sections."""

    def test_parse_meta_section(self, sample_collection_dir):
        """Test parsing meta section with name, type, seq."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "create-user.bru"

        request = parser.parse_file(str(filepath))

        assert request.meta["name"] == "Create User"
        assert request.meta["seq"] == 2
        assert isinstance(request.meta["seq"], int)


class TestBruParserAuth:
    """Test parsing authentication sections."""

    def test_parse_bearer_auth(self, sample_collection_dir):
        """Test parsing bearer token authentication."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "update-user.bru"

        request = parser.parse_file(str(filepath))

        assert request.auth["type"] == "bearer"
        assert request.auth["token"] == "{{authToken}}"


class TestBruParserURLs:
    """Test URL parsing."""

    def test_parse_url_with_variables(self, sample_collection_dir):
        """Test URLs containing template variables."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "get-user.bru"

        request = parser.parse_file(str(filepath))

        assert "{{userId}}" in request.url

    def test_parse_url_with_protocol(self, sample_collection_dir):
        """Test full URL with protocol."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "create-user.bru"

        request = parser.parse_file(str(filepath))

        assert request.url.startswith("https://")


class TestBruParserErrorHandling:
    """Test error handling for malformed .bru files."""

    def test_parse_file_with_missing_closing_brace(self, invalid_fixtures_dir):
        """Test that parser raises error for unmatched braces."""
        parser = BruParser()
        filepath = invalid_fixtures_dir / "malformed-braces.bru"

        with pytest.raises(Exception):
            parser.parse_file(str(filepath))

    def test_parse_nonexistent_file(self):
        """Test that parser raises error for missing file."""
        parser = BruParser()

        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/path/to/file.bru")
