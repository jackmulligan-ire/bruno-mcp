"""Tests for RequestMetadata model."""

from bruno_mcp.models import RequestMetadata


class TestExtractPathParameters:
    """Test extract_path_parameters() method on RequestMetadata."""

    def test_extract_path_parameters_single(self):
        """Extracts single {{variable}} from URL."""
        metadata = RequestMetadata(
            id="users/get-user",
            name="Get User",
            method="GET",
            url="https://api.example.com/users/{{userId}}",
            file_path="users/get-user.bru",
        )

        params = metadata.extract_path_parameters()

        assert params == {"userId"}

    def test_extract_path_parameters_multiple(self):
        """Extracts multiple {{variable}} placeholders from URL."""
        metadata = RequestMetadata(
            id="groups/users",
            name="Get User in Group",
            method="GET",
            url="https://api.example.com/{{groupId}}/users/{{userId}}",
            file_path="groups/users.bru",
        )

        params = metadata.extract_path_parameters()

        assert params == {"groupId", "userId"}

    def test_extract_path_parameters_ignores_process_env(self):
        """Does not extract {{process.env.VAR}} patterns."""
        metadata = RequestMetadata(
            id="users/get-user",
            name="Get User",
            method="GET",
            url="https://api.example.com/users/{{userId}}?token={{process.env.API_TOKEN}}",
            file_path="users/get-user.bru",
        )

        params = metadata.extract_path_parameters()

        assert params == {"userId"}
        assert "process.env.API_TOKEN" not in params

    def test_extract_path_parameters_no_variables(self):
        """Returns empty set when URL has no variables."""
        metadata = RequestMetadata(
            id="users/list",
            name="List Users",
            method="GET",
            url="https://api.example.com/users",
            file_path="users/list.bru",
        )

        params = metadata.extract_path_parameters()

        assert params == set()

    def test_extract_path_parameters_mixed_patterns(self):
        """Correctly extracts regular vars while ignoring process.env patterns."""
        metadata = RequestMetadata(
            id="groups/users",
            name="Get User",
            method="GET",
            url="https://{{baseUrl}}/{{groupId}}/users/{{userId}}?key={{process.env.API_KEY}}",
            file_path="groups/users.bru",
        )

        params = metadata.extract_path_parameters()

        assert params == {"baseUrl", "groupId", "userId"}
        assert "process.env.API_KEY" not in params
