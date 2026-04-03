"""Bruno .bru file parser.

This module provides functionality to parse Bruno API client .bru files
into structured Python objects.
"""

from pathlib import Path
from typing import Optional

from bruno_mcp.models import BruRequest, BruParseError
from bruno_mcp.parsers import BaseBruParser


class BruParser(BaseBruParser):
    """Parser for Bruno .bru files.

    This parser uses a line-by-line state machine approach to parse the
    block-based structure of .bru files.
    """

    HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}

    def _parse_meta(self, lines: list[str]) -> dict:
        """Parse meta section into dictionary.

        Args:
            lines: Lines from the meta section.

        Returns:
            Dictionary with name, type, seq keys.
        """
        meta = {}
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                if key == "seq":
                    meta[key] = int(value)
                else:
                    meta[key] = value

        return meta

    def _parse_method_and_url(self, sections: dict) -> tuple[str, str]:
        """Extract HTTP method and URL from sections.

        Args:
            sections: Dictionary of all parsed sections.

        Returns:
            Tuple of (method, url).

        Raises:
            BruParseError: If no HTTP method found.
        """
        method_section = next((s for s in sections if s in self.HTTP_METHODS), None)

        if not method_section:
            raise BruParseError("No HTTP method found")

        for line in sections[method_section]:
            if line.startswith("url:"):
                url = line.split("url:", 1)[1].strip()
                return method_section.upper(), url

        raise BruParseError("No URL found in method section")

    def _parse_key_value_section(self, lines: list[str]) -> dict:
        """Parse sections with key: value format (headers, params, etc.).

        Args:
            lines: Lines from a key-value section.

        Returns:
            Dictionary of parsed key-value pairs.
        """
        result = {}
        for line in lines:
            if ":" in line:
                # Split on first colon only (values may contain colons)
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()

        return result

    def _parse_params(self, lines: list[str]) -> dict:
        """Parse query parameters section.

        Args:
            lines: Lines from params:query section.

        Returns:
            Dictionary of query parameters.
        """
        return self._parse_key_value_section(lines)

    def _parse_headers(self, lines: list[str]) -> dict:
        """Parse headers section.

        Args:
            lines: Lines from headers section.

        Returns:
            Dictionary of headers.
        """
        return self._parse_key_value_section(lines)

    def _parse_body(self, sections: dict) -> Optional[dict]:
        """Parse body section if present.

        Args:
            sections: Dictionary of all parsed sections.

        Returns:
            Dictionary with 'type' and 'content' keys, or None if no body.
        """
        body_section = next((s for s in sections if s.startswith("body:")), None)

        if not body_section:
            return None

        body_type = body_section.split(":", 1)[1]
        content = "\n".join(sections[body_section])

        return {"type": body_type, "content": content}

    def _parse_auth(self, sections: dict) -> Optional[dict]:
        """Parse authentication section if present.

        Args:
            sections: Dictionary of all parsed sections.

        Returns:
            Dictionary with auth type and credentials, or None if no auth.
        """
        auth_section = next((s for s in sections if s.startswith("auth:")), None)

        if not auth_section:
            return None

        auth_type = auth_section.split(":", 1)[1]
        auth_dict = self._parse_key_value_section(sections[auth_section])
        auth_dict["type"] = auth_type

        return auth_dict

    def parse_file(self, filepath: str) -> BruRequest:
        """Parse a .bru file and return structured BruRequest model.

        Args:
            filepath: Absolute path to the .bru file to parse.

        Returns:
            BruRequest object containing parsed data.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            BruParseError: If the file is malformed or cannot be parsed.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            raise BruParseError("File is empty")

        sections = self._split_into_sections(content)

        meta = self._parse_meta(sections.get("meta", []))
        method, url = self._parse_method_and_url(sections)
        params = self._parse_params(sections.get("params:query", []))
        headers = self._parse_headers(sections.get("headers", []))
        body = self._parse_body(sections)
        auth = self._parse_auth(sections)

        return BruRequest(
            filepath=filepath,
            meta=meta,
            method=method,
            url=url,
            params=params,
            headers=headers,
            body=body,
            auth=auth,
        )
