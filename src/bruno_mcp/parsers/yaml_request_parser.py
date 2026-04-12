"""Parser for OpenCollection YAML request files."""

from pathlib import Path
from typing import Any

import yaml

from bruno_mcp.models import BruParseError, YamlRequest


class YamlParser:
    """Parse OpenCollection YAML request definitions into YamlRequest."""

    @staticmethod
    def _coerce_kv_list(value: Any) -> list[dict[str, Any]]:
        """Normalise headers/params to a list of dicts."""
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _validate_request_document(self, yaml_document: Any, filepath: str) -> None:
        """Validate loaded YAML; raise BruParseError if invalid."""
        if yaml_document is None or not isinstance(yaml_document, dict):
            raise BruParseError(f"Invalid YAML document: {filepath}")

        if "info" not in yaml_document or "http" not in yaml_document:
            raise BruParseError(f"Missing required sections in {filepath}")

        info = yaml_document["info"]
        http = yaml_document["http"]
        if not isinstance(info, dict) or not isinstance(http, dict):
            raise BruParseError(f"Invalid info or http section in {filepath}")

        name = info.get("name")
        if name is None or not str(name).strip():
            raise BruParseError(f"Missing or empty info.name in {filepath}")

        if "method" not in http or "url" not in http:
            raise BruParseError(f"Missing required http fields in {filepath}")

        body = http.get("body")
        if body is not None and not isinstance(body, dict):
            raise BruParseError(f"Invalid http.body in {filepath}")

        auth = http.get("auth")
        if auth is not None and not isinstance(auth, dict):
            raise BruParseError(f"Invalid http.auth in {filepath}")

    def parse_file(self, filepath: str) -> YamlRequest:
        path = Path(filepath)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            with path.open(encoding="utf-8") as f:
                yaml_document = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise BruParseError(f"Malformed YAML: {e}") from e

        self._validate_request_document(yaml_document, filepath)

        http = yaml_document["http"]
        return YamlRequest(
            filepath=str(path),
            info=yaml_document["info"],
            method=str(http["method"]).strip().upper(),
            url=str(http["url"]).strip(),
            headers=self._coerce_kv_list(http.get("headers")),
            params=self._coerce_kv_list(http.get("params")),
            body=http.get("body"),
            auth=http.get("auth"),
        )
