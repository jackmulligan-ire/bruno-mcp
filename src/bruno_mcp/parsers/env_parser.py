"""Environment parser for Bruno collection and environment files."""

import json
from pathlib import Path
from typing import Optional

from bruno_mcp.models import BruParseError
from bruno_mcp.parsers.base_parser import BaseParser


class EnvParser(BaseParser):
    """Parser for Bruno collection (bruno.json) and environment (.bru) files."""

    def _parse_vars_section(self, lines: list[str]) -> dict:
        """Parse vars or vars:secret section into dictionary."""
        result = {}
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    def parse_collection(self, filepath: str) -> dict:
        """Parse bruno.json collection file.

        Args:
            filepath: Path to bruno.json file.

        Returns:
            Dictionary with collection metadata and variables.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            BruParseError: If the file is malformed.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Collection file not found: {filepath}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            raise BruParseError(f"Invalid JSON in collection file: {e}")

    def parse_environment(self, filepath: str) -> dict:
        """Parse environment .bru file.

        Args:
            filepath: Path to environment .bru file.

        Returns:
            Dictionary with 'vars' and optionally 'secrets' keys.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            BruParseError: If the file is malformed.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Environment file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            return {"vars": {}}

        sections = self._split_into_sections(content)

        result = {}

        if "vars" in sections:
            result["vars"] = self._parse_vars_section(sections["vars"])

        if "vars:secret" in sections:
            result["secrets"] = self._parse_vars_section(sections["vars:secret"])

        return result

    def load_environment(
        self, collection_path: Optional[str] = None, environment_path: Optional[str] = None
    ) -> dict:
        """Load and merge variables from collection and environment files.

        Environment variables override collection variables.

        Args:
            collection_path: Path to bruno.json file.
            environment_path: Path to environment .bru file.

        Returns:
            Merged dictionary of all variables.
        """
        variables = {}

        if collection_path:
            collection = self.parse_collection(collection_path)
            if "vars" in collection:
                variables.update(collection["vars"])

        if environment_path:
            environment = self.parse_environment(environment_path)
            if "vars" in environment:
                variables.update(environment["vars"])
            if "secrets" in environment:
                variables.update(environment["secrets"])

        return variables
