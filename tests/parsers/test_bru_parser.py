"""Tests for BruParser - Bruno .bru file parser."""

import json
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


class TestBruParserBodyParsing:
    """Test body parsing with complex structures and nested braces."""

    def test_parse_json_body_is_valid_json(self, sample_collection_dir):
        """Test that parsed JSON body content is valid JSON."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "create-user.bru"

        request = parser.parse_file(str(filepath))

        assert request.body is not None
        assert request.body["type"] == "json"
        parsed_json = json.loads(request.body["content"])
        assert parsed_json["name"] == "John Doe"
        assert parsed_json["email"] == "john@example.com"

    def test_parse_json_body_preserves_all_braces(self, sample_collection_dir):
        """Test that all opening and closing braces are preserved in body content."""
        parser = BruParser()
        filepath = sample_collection_dir / "users" / "create-user.bru"

        request = parser.parse_file(str(filepath))

        body_content = request.body["content"]

        opening_braces = body_content.count("{")
        closing_braces = body_content.count("}")

        assert opening_braces == closing_braces
        assert opening_braces >= 1

    def test_parse_json_with_nested_objects(self, sample_collection_dir):
        """Test parsing JSON with deeply nested objects (3+ levels)."""
        parser = BruParser()
        filepath = sample_collection_dir / "posts" / "nested-data.bru"

        request = parser.parse_file(str(filepath))

        assert request.body is not None
        parsed_json = json.loads(request.body["content"])

        assert parsed_json["user"]["name"] == "Alice Smith"
        assert parsed_json["user"]["address"]["city"] == "Portland"
        assert parsed_json["user"]["address"]["coordinates"]["lat"] == 45.5152
        assert parsed_json["user"]["preferences"]["notifications"]["email"] is True

    def test_parse_json_with_array_values(self, sample_collection_dir):
        """Test parsing JSON containing arrays with multiple elements."""
        parser = BruParser()
        filepath = sample_collection_dir / "posts" / "nested-data.bru"

        request = parser.parse_file(str(filepath))

        parsed_json = json.loads(request.body["content"])

        assert isinstance(parsed_json["tags"], list)
        assert len(parsed_json["tags"]) == 3
        assert parsed_json["tags"][0] == "premium"
        assert parsed_json["tags"][2] == "active"

    def test_parse_json_mixed_nesting(self, sample_collection_dir):
        """Test parsing JSON with mixed nesting (objects in objects, arrays, etc)."""
        parser = BruParser()
        filepath = sample_collection_dir / "posts" / "nested-data.bru"

        request = parser.parse_file(str(filepath))

        parsed_json = json.loads(request.body["content"])

        assert "user" in parsed_json
        assert "address" in parsed_json["user"]
        assert "coordinates" in parsed_json["user"]["address"]
        assert parsed_json["metadata"]["created"] == "2024-01-15"
