"""Collection scanner for discovering Bruno .bru and OpenCollection YAML requests."""

import re
from pathlib import Path

from bruno_mcp.models import (
    BruParseError,
    BruRequest,
    CollectionFormat,
    CollectionInfo,
    RequestMetadata,
    YamlRequest,
)
from bruno_mcp.parsers import BruParser, YamlParser


class CollectionScanner:
    """Scans a Bruno collection directory for request files (.bru or OpenCollection .yml/.yaml)."""

    MAX_FILE_SIZE = 10 * 1024 * 1024
    MAX_FILES = 1000

    def __init__(self, bru_parser: BruParser, yaml_parser: YamlParser):
        """Initialize scanner with parsers for both collection formats.

        Args:
            bru_parser: Parser for classic Bruno .bru files.
            yaml_parser: Parser for OpenCollection YAML request files.
        """
        self.bru_parser = bru_parser
        self.yaml_parser = yaml_parser

    def _enforce_file_limit(self, files: list) -> None:
        """Check that file count doesn't exceed maximum.

        Args:
            files: List of files to check.

        Raises:
            ValueError: If file count exceeds MAX_FILES.
        """
        if len(files) > self.MAX_FILES:
            raise ValueError(f"Collection too large: {len(files)} files")

    def _extract_variable_names_from_bru_request(self, request: BruRequest) -> list[str]:
        """Extract {{variable}} names from URL, headers, params, and body content.

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

    def _extract_variable_names_from_yaml_request(self, request: YamlRequest) -> list[str]:
        """Extract {{variable}} names from YAML HTTP fields (lists of name/value objects).

        Skips disabled headers and params. Uses body ``data`` when it is a string.
        Same process.env exclusion as the BRU path.
        """
        pattern = r"\{\{([^{}]+)\}\}"
        names: set[str] = set()
        texts: list[str] = [request.url]

        for entry in request.headers:
            if entry.get("disabled"):
                continue
            value = entry.get("value")
            if isinstance(value, str):
                texts.append(value)

        for entry in request.params:
            if entry.get("disabled"):
                continue
            value = entry.get("value")
            if isinstance(value, str):
                texts.append(value)

        if request.body:
            data = request.body.get("data")
            if isinstance(data, str):
                texts.append(data)

        for text in texts:
            if "{{" in text:
                for match in re.findall(pattern, text):
                    var_name = match.strip()
                    if not var_name.startswith("process.env."):
                        names.add(var_name)
        return sorted(names)

    def _scan_bru_collection(self, abs_path: Path) -> list[RequestMetadata]:
        bru_files = list(abs_path.rglob("*.bru"))
        self._enforce_file_limit(bru_files)

        results: list[RequestMetadata] = []

        for file_path in bru_files:
            if file_path.stat().st_size > self.MAX_FILE_SIZE:
                continue

            try:
                request = self.bru_parser.parse_file(str(file_path))
                relative_path = file_path.relative_to(abs_path)
                request_id = str(relative_path.with_suffix("")).replace("\\", "/")

                variable_names = self._extract_variable_names_from_bru_request(request)

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

    def _scan_yaml_collection(self, abs_path: Path) -> list[RequestMetadata]:
        yaml_candidates = sorted(
            {*abs_path.rglob("*.yml"), *abs_path.rglob("*.yaml")},
            key=lambda p: str(p),
        )
        yml_files = [
            f
            for f in yaml_candidates
            if f.name != "opencollection.yml"
            and f.relative_to(abs_path).parts[0] != "environments"
        ]
        self._enforce_file_limit(yml_files)

        results: list[RequestMetadata] = []

        for file_path in yml_files:
            if file_path.stat().st_size > self.MAX_FILE_SIZE:
                continue

            try:
                request = self.yaml_parser.parse_file(str(file_path))
                if request.info.get("type") != "http":
                    continue

                relative_path = file_path.relative_to(abs_path)
                request_id = str(relative_path.with_suffix("")).replace("\\", "/")

                variable_names = self._extract_variable_names_from_yaml_request(request)

                metadata = RequestMetadata(
                    id=request_id,
                    name=str(request.info["name"]),
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
            List of RequestMetadata for .bru or YAML HTTP requests.
        """
        abs_path = collection_info.path.resolve()
        if collection_info.format is CollectionFormat.OPENCOLLECTION:
            return self._scan_yaml_collection(abs_path)
        return self._scan_bru_collection(abs_path)
