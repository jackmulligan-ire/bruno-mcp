"""Tests for YamlParser - OpenCollection YAML request files."""

import pytest

from bruno_mcp.models import BruParseError
from bruno_mcp.parsers import YamlParser


class TestYamlParserParseFile:
    """Test parsing OpenCollection YAML request files."""

    def test_parse_file_returns_yaml_request_with_correct_http_fields(
        self, opencollection_collection
    ):
        parser = YamlParser()
        filepath = opencollection_collection / "users" / "get-user.yml"

        request = parser.parse_file(str(filepath))

        assert request.info["name"] == "Get User"
        assert request.method == "GET"
        assert request.url == "https://api.example.com/users/{{userId}}"
        assert request.headers == [
            {"name": "Authorization", "value": "Bearer {{authToken}}"},
        ]
        assert request.params == [
            {"name": "limit", "value": "10", "type": "query"},
        ]

    def test_parse_file_returns_yaml_request_with_body(self, opencollection_collection):
        parser = YamlParser()
        filepath = opencollection_collection / "users" / "create-user.yml"

        request = parser.parse_file(str(filepath))

        assert request.info["name"] == "Create User"
        assert request.method == "POST"
        assert request.url == "https://api.example.com/users"
        assert request.body["type"] == "json"
        assert "{{displayName}}" in request.body["data"]

    def test_parse_file_raises_for_missing_file(self, opencollection_collection):
        parser = YamlParser()
        missing = opencollection_collection / "does-not-exist.yml"

        with pytest.raises(FileNotFoundError):
            parser.parse_file(str(missing))

    def test_parse_file_raises_bru_parse_error_for_malformed_yaml(
        self, invalid_fixtures_dir
    ):
        parser = YamlParser()
        path = invalid_fixtures_dir / "malformed.yml"

        with pytest.raises(BruParseError):
            parser.parse_file(str(path))

    def test_parse_file_raises_when_info_name_missing(self, invalid_fixtures_dir):
        parser = YamlParser()
        path = invalid_fixtures_dir / "missing-request-name.yml"

        with pytest.raises(BruParseError, match="info.name"):
            parser.parse_file(str(path))
