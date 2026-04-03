"""Collection scanner for discovering Bruno .bru files."""

import re
from pathlib import Path

from bruno_mcp.models import (
    BruParseError,
    BruRequest,
    CollectionFormat,
    CollectionInfo,
    RequestMetadata,
)
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

    def scan_collection_for_format(self, collection_path: Path) -> CollectionFormat:
        """Detect collection layout from root marker files.

        Args:
            collection_path: Path to Bruno collection root directory.

        Returns:
            Bru layout if ``bruno.json`` exists, OpenCollection if ``opencollection.yml`` exists.

        Raises:
            ValueError: If both markers exist, if neither exists, or the path is ambiguous.
        """
        abs_path = collection_path.resolve()
        has_bru = (abs_path / "bruno.json").exists()
        has_oc = (abs_path / "opencollection.yml").exists()

        if has_bru and has_oc:
            raise ValueError(
                "This folder contains both bruno.json and opencollection.yml, which indicate "
                "two different collection formats (classic .bru vs OpenCollection YAML). "
                "Remove one of these files so the collection has a single format. Path: "
                f"{abs_path}"
            )

        elif has_bru:
            return CollectionFormat.BRU
        elif has_oc:
            return CollectionFormat.OPENCOLLECTION
        raise ValueError(f"Not a valid Bruno collection: {abs_path}")

    def scan_collection_for_requests(self, collection_info: CollectionInfo) -> list[RequestMetadata]:
        """Scan collection and build request metadata for the detected format.

        Args:
            collection_info: Loaded collection with path and format.

        Returns:
            List of RequestMetadata (empty for OpenCollection until YAML scanning exists).
        """
        if collection_info.format is CollectionFormat.OPENCOLLECTION:
            return []

        abs_path = collection_info.path.resolve()
        bru_files = list(abs_path.rglob("*.bru"))
        self._enforce_file_limit(bru_files)

        results: list[RequestMetadata] = []

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
