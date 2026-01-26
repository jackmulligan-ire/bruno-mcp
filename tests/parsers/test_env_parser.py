"""Tests for environment parser - parses bruno.json and environment .bru files."""


from bruno_mcp.parsers import EnvParser


class TestCollectionParsing:
    """Test parsing bruno.json collection files."""

    def test_parse_collection_file(self, sample_collection_dir):
        """Test parsing bruno.json with metadata and variables."""
        parser = EnvParser()
        bruno_json_path = sample_collection_dir / "bruno.json"

        collection = parser.parse_collection(str(bruno_json_path))

        assert collection["name"] == "Sample API Collection"
        assert collection["version"] == "1"
        assert collection["type"] == "collection"
        assert collection["vars"]["defaultTimeout"] == "5000"
        assert collection["vars"]["baseUrl"] == "https://api.example.com"


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


class TestCombinedLoading:
    """Test loading both collection and environment together."""

    def test_load_both_collection_and_environment(self, sample_collection_dir):
        """Test loading bruno.json and environment .bru together."""
        parser = EnvParser()

        variables = parser.load_environment(
            collection_path=str(sample_collection_dir / "bruno.json"),
            environment_path=str(sample_collection_dir / "environments" / "local.bru"),
        )

        assert "defaultTimeout" in variables
        assert "baseUrl" in variables
        assert "userId" in variables

    def test_environment_overrides_collection(self, sample_collection_dir):
        """Test that environment variables override collection variables."""
        parser = EnvParser()

        variables = parser.load_environment(
            collection_path=str(sample_collection_dir / "bruno.json"),
            environment_path=str(sample_collection_dir / "environments" / "local.bru"),
        )

        assert variables["baseUrl"] == "http://localhost:3000"
