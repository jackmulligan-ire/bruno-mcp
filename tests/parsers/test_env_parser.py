"""Tests for environment parser — listing environments under a collection."""

import pytest

from bruno_mcp.models import CollectionFormat, CollectionInfo
from bruno_mcp.parsers import EnvParser


@pytest.fixture
def env_parser():
    return EnvParser()


class TestEnvParserBruEnvironments:
    """Test discovering and listing environments in a BRU collection."""

    @pytest.fixture
    def empty_collection_dir(self, tmp_path):
        """Collection directory without environments directory."""
        return tmp_path

    def test_list_environments_returns_all_environment_files(self, env_parser, sample_collection_dir):
        collection = CollectionInfo(
            name=sample_collection_dir.name,
            path=sample_collection_dir,
            format=CollectionFormat.BRU,
        )

        environments = env_parser.list_environments(collection)

        assert len(environments) == 2
        local_env = next(e for e in environments if e.name == "local")
        prod_env = next(e for e in environments if e.name == "production")
        assert local_env.variables["baseUrl"] == "http://localhost:3000"
        assert local_env.variables["apiVersion"] == "v1"
        assert prod_env.variables["baseUrl"] == "https://api.example.com"
        assert prod_env.variables["apiKey"] == "{{process.env.API_KEY}}"

    def test_list_environments_handles_missing_environments_directory(self, env_parser, empty_collection_dir):
        collection = CollectionInfo(
            name=empty_collection_dir.name,
            path=empty_collection_dir,
            format=CollectionFormat.BRU,
        )

        environments = env_parser.list_environments(collection)

        assert environments == []

    def test_list_environments_includes_secrets_as_template_strings(self, env_parser, sample_collection_dir):
        collection = CollectionInfo(
            name=sample_collection_dir.name,
            path=sample_collection_dir,
            format=CollectionFormat.BRU,
        )

        environments = env_parser.list_environments(collection)

        local_env = next(e for e in environments if e.name == "local")
        assert local_env.variables["authToken"] == "{{process.env.SECRET_TOKEN}}"
        assert local_env.variables["baseUrl"] == "http://localhost:3000"
        assert local_env.variables["apiVersion"] == "v1"
        assert local_env.variables["userId"] == "123"


class TestEnvParserYamlEnvironments:
    """Test listing OpenCollection YAML environments."""

    def test_list_environments_returns_yaml_environments(self, env_parser, opencollection_collection):
        """OpenCollection fixture has environments/local.yml, production.yml, and staging.yaml with variables.

        list_environments is called with CollectionInfo for that path and OPENCOLLECTION format.

        Three BruEnvironment values are returned: local has baseUrl and secret authToken; production has baseUrl only and excludes disabled_var from production.yml; staging mirrors local from the .yaml file.
        """
        collection = CollectionInfo(
            name=opencollection_collection.name,
            path=opencollection_collection,
            format=CollectionFormat.OPENCOLLECTION,
        )

        environments = env_parser.list_environments(collection)

        assert len(environments) == 3
        local_env = next(e for e in environments if e.name == "local")
        prod_env = next(e for e in environments if e.name == "production")
        assert local_env.variables["baseUrl"] == "http://localhost:3000"
        assert local_env.variables["authToken"] == "{{process.env.SECRET_TOKEN}}"
        assert prod_env.variables["baseUrl"] == "https://api.example.com"
        assert "disabled_var" not in prod_env.variables

    def test_list_environments_returns_empty_when_no_environments_dir(self, env_parser, tmp_path):
        """A temporary directory has no environments/ subdirectory.

        list_environments is called with OPENCOLLECTION format pointing at that directory.

        An empty list is returned.
        """
        collection = CollectionInfo(
            name=tmp_path.name,
            path=tmp_path,
            format=CollectionFormat.OPENCOLLECTION,
        )

        environments = env_parser.list_environments(collection)

        assert environments == []

    def test_list_environments_supports_full_yaml_extension_name(self, env_parser, opencollection_collection):
        collection = CollectionInfo(
            name=opencollection_collection.name,
            path=opencollection_collection,
            format=CollectionFormat.OPENCOLLECTION,
        )

        environments = env_parser.list_environments(collection)

        staging_env = next(e for e in environments if e.name == "staging")
        assert staging_env.variables["baseUrl"] == "http://localhost:3000"
        assert staging_env.variables["authToken"] == "{{process.env.SECRET_TOKEN}}"
