"""Bruno CLI request executor."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from bruno_mcp.models import BruResponse, CollectionInfo


class CLIExecutor:
    """Executes Bruno requests via Bruno CLI."""

    def _build_command(
        self,
        request_file_path: Path,
        environment_name: Optional[str],
        variable_overrides: Optional[dict[str, str]],
        output_path: Path,
    ) -> list[str]:
        """Build CLI command list for bru run.

        Args:
            request_file_path: Path to .bru file to execute.
            environment_name: Optional environment name to use.
            variable_overrides: Optional dict of variable overrides.
            output_path: Path to temporary file for JSON output.

        Returns:
            Command list for subprocess execution.
        """
        cmd = ["bru", "run", str(request_file_path)]

        if environment_name:
            cmd.extend(["--env", environment_name])

        if variable_overrides:
            for key, value in variable_overrides.items():
                cmd.extend(["--env-var", f"{key}={value}"])

        cmd.extend(["--output", str(output_path), "--format", "json"])

        return cmd

    def _serialize_body(self, body_data) -> str:
        """Convert response body data to string.

        Handles dict/list (JSON serialization), string (as-is), None (empty string),
        and other types (string conversion).

        Args:
            body_data: Body data from CLI response.

        Returns:
            Serialized body string.
        """
        if isinstance(body_data, (dict, list)):
            return json.dumps(body_data)
        elif body_data is None:
            return ""
        else:
            return str(body_data)

    def _normalize_headers(self, headers: dict) -> dict[str, str]:
        """Normalize header dictionary.

        Converts all keys to lowercase and values to strings.

        Args:
            headers: Raw headers from CLI response.

        Returns:
            Normalized headers dictionary.
        """
        normalized = {}
        for key, value in headers.items():
            normalized[key.lower()] = str(value)
        return normalized

    def execute(
        self,
        request_file_path: Path,
        collection: CollectionInfo,
        environment_name: Optional[str] = None,
        variable_overrides: Optional[dict[str, str]] = None,
    ) -> BruResponse:
        """Execute request via Bruno CLI.

        Args:
            request_file_path: Path to request file (relative to collection root).
            collection: Loaded collection whose ``path`` is used as the working directory.
            environment_name: Optional environment name to use.
            variable_overrides: Optional dict of variable overrides.

        Returns:
            BruResponse with status, headers, and body.

        Raises:
            RuntimeError: If CLI execution fails.
            ValueError: If JSON parsing fails.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_output = Path(f.name)

        try:
            cmd = self._build_command(
                request_file_path, environment_name, variable_overrides, temp_output
            )

            result = subprocess.run(
                cmd,
                cwd=str(collection.path),
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Bruno CLI failed: {result.stderr}\nCommand: {' '.join(cmd)}")

            with open(temp_output) as f:
                cli_results = json.loads(f.read())

            if not cli_results or not cli_results[0].get("results"):
                raise ValueError("No results in CLI output")

            response_data = cli_results[0]["results"][0].get("response", {})

            body = self._serialize_body(response_data.get("data", ""))
            headers = self._normalize_headers(response_data.get("headers", {}))

            return BruResponse(
                status=response_data.get("status", 0),
                headers=headers,
                body=body,
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"Bruno CLI failed: {e}") from e
        finally:
            if temp_output.exists():
                temp_output.unlink()
