"""Tests for Bruno CLI request execution."""

import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from bruno_mcp.executors import CLIExecutor
from bruno_mcp.models import BruResponse


class TestCLICommandConstruction:
    """Test CLI command construction."""

    @pytest.fixture
    def executor(self):
        return CLIExecutor()

    @pytest.fixture
    def request_file(self):
        return Path("users/get-user.bru")

    @pytest.fixture
    def collection_path(self):
        return Path("/collection")

    @pytest.fixture
    def mock_temp_file(self):
        """Mock tempfile.NamedTemporaryFile to prevent actual file system operations.

        CLIExecutor.execute() creates a temporary file for JSON output. This fixture
        mocks that call to avoid real file I/O during tests, even though we don't
        assert on the temp file in these command construction tests.
        """
        with patch("bruno_mcp.executors.cli_executor.tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.json"
            yield mock_temp

    @pytest.fixture
    def mock_subprocess_success(self):
        with patch("bruno_mcp.executors.cli_executor.subprocess.run") as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            yield mock_subprocess

    @pytest.fixture
    def mock_open_file(self):
        """Mock builtins.open to prevent actual file I/O during command construction tests.

        CLIExecutor.execute() reads JSON output from a temporary file. This fixture
        mocks the open() call with default JSON data to prevent real file operations,
        even though these tests focus on command construction rather than file reading.
        """
        with patch(
            "builtins.open",
            new_callable=mock_open,
            read_data='[{"results": [{"response": {"status": 200, "headers": {}, "data": "test"}}]}]',
        ) as mock_file:
            yield mock_file

    def test_execute_builds_basic_command(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Verifies basic CLI command with request file path."""
        executor.execute(request_file, collection_path)

        mock_subprocess_success.assert_called_once()
        call_args = mock_subprocess_success.call_args
        assert call_args[0][0][0] == "bru"
        assert call_args[0][0][1] == "run"
        assert str(request_file) in call_args[0][0]

    def test_execute_includes_environment_flag(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Adds --env flag when environment provided."""
        executor.execute(request_file, collection_path, environment_name="local")

        call_args = mock_subprocess_success.call_args
        cmd = call_args[0][0]
        assert "--env" in cmd
        env_index = cmd.index("--env")
        assert cmd[env_index + 1] == "local"

    def test_execute_includes_multiple_variable_overrides(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Adds multiple --env-var flags correctly."""
        overrides = {"userId": "123", "token": "abc"}

        executor.execute(request_file, collection_path, variable_overrides=overrides)

        call_args = mock_subprocess_success.call_args
        cmd = call_args[0][0]
        assert cmd.count("--env-var") == 2
        assert "--env-var" in cmd
        env_var_indices = [i for i, x in enumerate(cmd) if x == "--env-var"]
        assert "userId=123" in cmd[env_var_indices[0] + 1]
        assert "token=abc" in cmd[env_var_indices[1] + 1]


class TestJSONOutputParsing:
    """Test JSON output parsing from CLI."""

    @pytest.fixture
    def executor(self):
        return CLIExecutor()

    @pytest.fixture
    def request_file(self):
        return Path("users/get-user.bru")

    @pytest.fixture
    def collection_path(self):
        return Path("/collection")

    @pytest.fixture
    def mock_temp_file(self):
        """Mock tempfile.NamedTemporaryFile to prevent actual file system operations.

        CLIExecutor.execute() creates a temporary file for JSON output. This fixture
        mocks that call to avoid real file I/O during tests.
        """
        with patch("bruno_mcp.executors.cli_executor.tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.json"
            yield mock_temp

    @pytest.fixture
    def mock_subprocess_success(self):
        with patch("bruno_mcp.executors.cli_executor.subprocess.run") as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            yield mock_subprocess

    @pytest.fixture
    def mock_open_file(self):
        """Mock builtins.open to prevent actual file I/O during JSON parsing tests.

        CLIExecutor.execute() reads JSON output from a temporary file. This fixture
        mocks the open() call. Tests can configure the read return value with their
        specific JSON data.
        """
        with patch("builtins.open", new_callable=mock_open) as mock_file:
            yield mock_file

    def test_execute_parses_successful_response(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Extracts status, headers, body from JSON."""
        json_data = [
            {
                "results": [
                    {
                        "response": {
                            "status": 200,
                            "headers": {"content-type": "application/json"},
                            "data": {"id": 123, "name": "Test"},
                        }
                    }
                ]
            }
        ]
        mock_open_file.return_value.read.return_value = json.dumps(json_data)

        response = executor.execute(request_file, collection_path)

        assert response.status == 200
        assert "content-type" in response.headers
        assert "id" in response.body

    def test_execute_handles_json_response_body(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Serializes parsed JSON data back to string."""
        json_data = [
            {
                "results": [
                    {"response": {"status": 200, "headers": {}, "data": [{"id": 1}, {"id": 2}]}}
                ]
            }
        ]
        mock_open_file.return_value.read.return_value = json.dumps(json_data)

        response = executor.execute(request_file, collection_path)

        assert isinstance(response.body, str)
        parsed_body = json.loads(response.body)
        assert len(parsed_body) == 2


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def executor(self):
        return CLIExecutor()

    @pytest.fixture
    def request_file(self):
        return Path("users/get-user.bru")

    @pytest.fixture
    def collection_path(self):
        return Path("/collection")

    @pytest.fixture
    def mock_temp_file(self):
        """Mock tempfile.NamedTemporaryFile to prevent actual file system operations."""
        with patch("bruno_mcp.executors.cli_executor.tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.json"
            yield mock_temp

    @pytest.fixture
    def mock_subprocess_success(self):
        with patch("bruno_mcp.executors.cli_executor.subprocess.run") as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            yield mock_subprocess

    @pytest.fixture
    def mock_open_file(self):
        """Mock builtins.open to prevent actual file I/O during error handling tests."""
        with patch("builtins.open", new_callable=mock_open) as mock_file:
            yield mock_file

    @patch("bruno_mcp.executors.cli_executor.subprocess.run")
    def test_execute_raises_on_cli_not_found(
        self, mock_subprocess, executor, request_file, collection_path
    ):
        """Raises RuntimeError when bru command missing."""
        mock_subprocess.side_effect = FileNotFoundError("bru: command not found")

        with pytest.raises(RuntimeError) as exc_info:
            executor.execute(request_file, collection_path)

        assert "Bruno CLI failed" in str(exc_info.value)

    def test_execute_raises_on_non_zero_exit(
        self, mock_subprocess_success, mock_temp_file, executor, request_file, collection_path
    ):
        """Raises RuntimeError with stderr on CLI failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: Collection not found"
        mock_subprocess_success.return_value = mock_result

        with pytest.raises(RuntimeError) as exc_info:
            executor.execute(request_file, collection_path)

        assert "Bruno CLI failed" in str(exc_info.value)
        assert "Error: Collection not found" in str(exc_info.value)

    @patch("builtins.open", new_callable=mock_open, read_data="invalid json")
    def test_execute_raises_on_malformed_json(
        self,
        mock_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Raises ValueError when JSON parsing fails."""
        with pytest.raises((ValueError, json.JSONDecodeError)):
            executor.execute(request_file, collection_path)

    def test_execute_raises_on_empty_results_array(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Raises ValueError when no results in output."""
        mock_open_file.return_value.read.return_value = "[]"

        with pytest.raises(ValueError) as exc_info:
            executor.execute(request_file, collection_path)

        assert "No results" in str(exc_info.value)


class TestTempFileHandling:
    """Test temporary file handling."""

    @pytest.fixture
    def executor(self):
        return CLIExecutor()

    @pytest.fixture
    def request_file(self):
        return Path("users/get-user.bru")

    @pytest.fixture
    def collection_path(self):
        return Path("/collection")

    @pytest.fixture
    def mock_subprocess_success(self):
        """Mock subprocess.run to simulate successful CLI execution."""
        with patch("bruno_mcp.executors.cli_executor.subprocess.run") as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            yield mock_subprocess

    @pytest.fixture
    def mock_open_file(self):
        """Mock builtins.open to return test JSON data without actual file I/O."""
        json_data = [{"results": [{"response": {"status": 200, "headers": {}, "data": "test"}}]}]
        with patch(
            "builtins.open", new_callable=mock_open, read_data=json.dumps(json_data)
        ) as mock_file:
            yield mock_file

    def test_execute_creates_and_reads_temp_file(
        self, mock_open_file, mock_subprocess_success, executor, request_file, collection_path
    ):
        """Creates temp file and reads JSON output."""
        # Track the temp file path that gets created
        temp_file_paths = []

        # Wrap NamedTemporaryFile to capture the created file path
        original_named_temp = tempfile.NamedTemporaryFile

        def capture_temp_file(*args, **kwargs):
            temp_file = original_named_temp(*args, **kwargs)
            temp_file_paths.append(Path(temp_file.name))
            return temp_file

        with patch(
            "bruno_mcp.executors.cli_executor.tempfile.NamedTemporaryFile",
            side_effect=capture_temp_file,
        ):
            executor.execute(request_file, collection_path)

        # Verify temp file was created and used
        assert len(temp_file_paths) == 1
        temp_path = temp_file_paths[0]
        assert temp_path.suffix == ".json"

        # Verify open() was called with the temp file path
        mock_open_file.assert_called_once()
        assert mock_open_file.call_args[0][0] == temp_path

    def test_execute_deletes_temp_file_after_execution(
        self, mock_open_file, mock_subprocess_success, executor, request_file, collection_path
    ):
        """Removes temp file after execution completes."""
        # Track the temp file path that gets created
        temp_file_paths = []

        # Wrap NamedTemporaryFile to capture the created file path
        original_named_temp = tempfile.NamedTemporaryFile

        def capture_temp_file(*args, **kwargs):
            temp_file = original_named_temp(*args, **kwargs)
            temp_file_paths.append(Path(temp_file.name))
            return temp_file

        with patch(
            "bruno_mcp.executors.cli_executor.tempfile.NamedTemporaryFile",
            side_effect=capture_temp_file,
        ):
            executor.execute(request_file, collection_path)

        # Verify temp file was created
        assert len(temp_file_paths) == 1
        temp_path = temp_file_paths[0]

        # Verify the file was actually deleted
        assert not temp_path.exists()


class TestIntegration:
    """Integration tests with full execution flow."""

    @pytest.fixture
    def executor(self):
        return CLIExecutor()

    @pytest.fixture
    def request_file(self):
        return Path("users/get-user.bru")

    @pytest.fixture
    def collection_path(self):
        return Path("/collection")

    @pytest.fixture
    def mock_temp_file(self):
        """Mock tempfile.NamedTemporaryFile to prevent actual file system operations."""
        with patch("bruno_mcp.executors.cli_executor.tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.json"
            yield mock_temp

    @pytest.fixture
    def mock_subprocess_success(self):
        with patch("bruno_mcp.executors.cli_executor.subprocess.run") as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            yield mock_subprocess

    @pytest.fixture
    def mock_open_file(self):
        """Mock builtins.open to prevent actual file I/O during integration tests."""
        with patch("builtins.open", new_callable=mock_open) as mock_file:
            yield mock_file

    def test_execute_full_flow_with_environment(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Complete execution with environment flag."""
        json_data = [
            {
                "results": [
                    {
                        "response": {
                            "status": 200,
                            "headers": {"content-type": "application/json"},
                            "data": {"id": 123},
                        }
                    }
                ]
            }
        ]
        mock_open_file.return_value.read.return_value = json.dumps(json_data)

        response = executor.execute(request_file, collection_path, environment_name="local")

        assert response.status == 200
        call_args = mock_subprocess_success.call_args
        assert "--env" in call_args[0][0]
        assert "local" in call_args[0][0]

    def test_execute_full_flow_with_overrides(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Complete execution with variable overrides."""
        json_data = [{"results": [{"response": {"status": 200, "headers": {}, "data": "test"}}]}]
        mock_open_file.return_value.read.return_value = json.dumps(json_data)
        overrides = {"userId": "456"}

        response = executor.execute(request_file, collection_path, variable_overrides=overrides)

        assert response.status == 200
        call_args = mock_subprocess_success.call_args
        assert "--env-var" in call_args[0][0]
        assert "userId=456" in call_args[0][0]

    def test_execute_full_flow_without_environment(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Complete execution without environment selection."""
        json_data = [{"results": [{"response": {"status": 200, "headers": {}, "data": "test"}}]}]
        mock_open_file.return_value.read.return_value = json.dumps(json_data)

        response = executor.execute(request_file, collection_path)

        assert response.status == 200
        call_args = mock_subprocess_success.call_args
        assert "--env" not in call_args[0][0]


class TestSubprocessInvocation:
    """Test subprocess invocation details."""

    @pytest.fixture
    def executor(self):
        return CLIExecutor()

    @pytest.fixture
    def request_file(self):
        return Path("users/get-user.bru")

    @pytest.fixture
    def collection_path(self):
        return Path("/collection")

    @pytest.fixture
    def mock_temp_file(self):
        """Mock tempfile.NamedTemporaryFile to prevent actual file system operations."""
        with patch("bruno_mcp.executors.cli_executor.tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.json"
            yield mock_temp

    @pytest.fixture
    def mock_subprocess_success(self):
        with patch("bruno_mcp.executors.cli_executor.subprocess.run") as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            yield mock_subprocess

    @pytest.fixture
    def mock_open_file(self):
        """Mock builtins.open to prevent actual file I/O during subprocess invocation tests."""
        with patch(
            "builtins.open",
            new_callable=mock_open,
            read_data='[{"results": [{"response": {"status": 200, "headers": {}, "data": "test"}}]}]',
        ) as mock_file:
            yield mock_file

    def test_execute_calls_subprocess_with_correct_args(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Verifies subprocess.run called with correct command."""
        executor.execute(request_file, collection_path)

        mock_subprocess_success.assert_called_once()
        call_args = mock_subprocess_success.call_args
        assert call_args[0][0][0] == "bru"
        assert call_args[0][0][1] == "run"
        assert "--output" in call_args[0][0]
        assert "--format" in call_args[0][0]

    def test_execute_sets_cwd_to_collection_path(
        self,
        mock_open_file,
        mock_subprocess_success,
        mock_temp_file,
        executor,
        request_file,
        collection_path,
    ):
        """Sets working directory to collection root."""
        executor.execute(request_file, collection_path)

        call_args = mock_subprocess_success.call_args
        assert call_args[1]["cwd"] == str(collection_path)
