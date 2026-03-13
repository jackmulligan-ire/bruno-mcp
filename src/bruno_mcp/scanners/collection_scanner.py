"""Collection scanner for discovering Bruno .bru files."""

import re
from pathlib import Path

from bruno_mcp.models import BruParseError, BruRequest, RequestMetadata
from bruno_mcp.parsers import BruParser


class CollectionScanner:
    """Scans a Bruno collection directory for .bru files."""

    MAX_FILE_SIZE = 10 * 1024 * 1024
    MAX_FILES = 1000

    def __init__(self, parser: BruParser):
        """Initialize scanner with a BruParser instance.

        Args:
            parser: BruParser instance for parsing .bru files.
        """
        self.parser = parser

    def _validate_collection_path(self, path: Path) -> None:
        """Validate that path contains bruno.json.

        Args:
            path: Path to validate.

        Raises:
            ValueError: If bruno.json is not found.
        """
        if not (path / "bruno.json").exists():
            raise ValueError(f"Not a valid Bruno collection: {path}")

    def _enforce_file_limit(self, files: list) -> None:
        """Check that file count doesn't exceed maximum.

        Args:
            files: List of files to check.

        Raises:
            ValueError: If file count exceeds MAX_FILES.
        """
        if len(files) > self.MAX_FILES:
            raise ValueError(f"Collection too large: {len(files)} files")

    def _extract_variable_names_from_request(self, request: BruRequest) -> list[str]:
        """Extract {{variable}} names from all variable-bearing fields of a BruRequest.

        Excludes {{process.env.*}} patterns as those are resolved from the
        system environment, not passed by the caller.
        """
        pattern = r"\{\{([^{}]+)\}\}"
        names: set[str] = set()
        texts = [request.url]
        texts.extend(request.headers.values())
        texts.extend(request.params.values())
        if request.body and "content" in request.body:
            texts.append(request.body["content"])
        for text in texts:
            if isinstance(text, str) and "{{" in text:
                for match in re.findall(pattern, text):
                    var_name = match.strip()
                    if not var_name.startswith("process.env."):
                        names.add(var_name)
        return sorted(names)

    def scan_collection(self, collection_path: Path) -> list[RequestMetadata]:
        """Scan collection directory and extract metadata from all .bru files.

        Args:
            collection_path: Path to Bruno collection root directory.

        Returns:
            List of RequestMetadata for all valid .bru files.

        Raises:
            ValueError: If directory is not a valid Bruno collection or exceeds limits.
        """
        abs_path = collection_path.resolve()

        self._validate_collection_path(abs_path)

        bru_files = list(abs_path.rglob("*.bru"))
        self._enforce_file_limit(bru_files)

        results = []

        for file_path in bru_files:
            if file_path.stat().st_size > self.MAX_FILE_SIZE:
                continue

            try:
                request = self.parser.parse_file(str(file_path))
                relative_path = file_path.relative_to(abs_path)
                request_id = str(relative_path.with_suffix("")).replace("\\", "/")

                variable_names = self._extract_variable_names_from_request(request)

                metadata = RequestMetadata(
                    id=request_id,
                    name=request.get_name(),
                    method=request.method,
                    url=request.url,
                    file_path=str(relative_path).replace("\\", "/"),
                    variable_names=variable_names,
                )
                results.append(metadata)
            except BruParseError as e:
                print(f"Skipping malformed file {file_path}: {e}")
                continue

        return results
