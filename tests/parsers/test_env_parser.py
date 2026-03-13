"""Tests for environment parser - parses bruno.json and environment .bru files."""

import pytest

from bruno_mcp.parsers import EnvParser


class TestEnvironmentParsing:
    """Test parsing environment .bru files."""

    def test_parse_environment_variables(self, sample_collection_dir):
        """Test parsing vars section from environment .bru file."""
        parser = EnvParser()
        env_path = sample_collection_dir / "environments" / "local.bru"

        environment = parser.parse_environment(str(env_path))

        assert environment["vars"]["baseUrl"] == "http://localhost:3000"
        assert environment["vars"]["apiVersion"] == "v1"
        assert environment["vars"]["userId"] == "123"

    def test_parse_environment_secrets(self, sample_collection_dir):
        """Test parsing vars:secret section with process.env syntax."""
        parser = EnvParser()
        env_path = sample_collection_dir / "environments" / "local.bru"

        environment = parser.parse_environment(str(env_path))

        assert "secrets" in environment
        assert environment["secrets"]["authToken"] == "{{process.env.SECRET_TOKEN}}"

    def test_parse_environment_with_nested_vars(self, sample_collection_dir):
        """Test parsing environment with nested variable references."""
        parser = EnvParser()

        env_path = sample_collection_dir / "environments" / "local.bru"

        environment = parser.parse_environment(str(env_path))
        assert "vars" in environment
        assert isinstance(environment["vars"], dict)


class TestEnvironmentDiscovery:
    """Test discovering and listing environments in a collection."""

    @pytest.fixture
    def empty_collection_dir(self, tmp_path):
        """Collection directory without environments directory."""
        return tmp_path

    def test_list_environments_returns_all_environment_files(self, sample_collection_dir):
        """Test all .bru files discovered and parsed with name and variables."""
        parser = EnvParser()
        environments = parser.list_environments(sample_collection_dir)

        assert len(environments) == 2
        local_env = next(e for e in environments if e.name == "local")
        prod_env = next(e for e in environments if e.name == "production")
        assert local_env.variables["baseUrl"] == "http://localhost:3000"
        assert local_env.variables["apiVersion"] == "v1"
        assert prod_env.variables["baseUrl"] == "https://api.example.com"
        assert prod_env.variables["apiKey"] == "{{process.env.API_KEY}}"

    def test_list_environments_handles_missing_environments_directory(self, empty_collection_dir):
        """Test empty list returned when directory doesn't exist."""
        parser = EnvParser()
        environments = parser.list_environments(empty_collection_dir)

        assert environments == []

    def test_list_environments_includes_secrets_as_template_strings(self, sample_collection_dir):
        """Test secrets included in variables dict as template strings."""
        parser = EnvParser()
        environments = parser.list_environments(sample_collection_dir)

        local_env = next(e for e in environments if e.name == "local")
        assert local_env.variables["authToken"] == "{{process.env.SECRET_TOKEN}}"
        assert local_env.variables["baseUrl"] == "http://localhost:3000"
        assert local_env.variables["apiVersion"] == "v1"
        assert local_env.variables["userId"] == "123"
