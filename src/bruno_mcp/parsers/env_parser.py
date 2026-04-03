"""Environment parser for Bruno environment .bru files under a collection."""

import logging
from pathlib import Path

from bruno_mcp.models import BruEnvironment, BruParseError, CollectionFormat, CollectionInfo
from bruno_mcp.parsers import BaseBruParser

logger = logging.getLogger(__name__)


class EnvParser(BaseBruParser):
    """Parser for Bruno environment .bru files related to environments."""

    def _parse_vars_section(self, lines: list[str]) -> dict:
        """Parse vars or vars:secret section into dictionary."""
        result = {}
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result

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

    def list_environments(self, collection_info: CollectionInfo) -> list[BruEnvironment]:
        """List all environments in a collection.

        For classic Bruno collections, scans ``collection_info.path / "environments"``
        for ``*.bru`` files. OpenCollection roots return an empty list until YAML
        environment support is implemented.

        Args:
            collection_info: Loaded collection metadata (path and format).

        Returns:
            List of BruEnvironment instances with name and variables.
            Empty list if the format has no .bru environments yet or the env dir
            is missing.
        """
        if collection_info.format == CollectionFormat.OPENCOLLECTION:
            return []

        env_dir = collection_info.path / "environments"
        if not env_dir.exists():
            return []

        environments = []
        for env_file in env_dir.glob("*.bru"):
            try:
                parsed = self.parse_environment(str(env_file))
                variables = {}
                if "vars" in parsed:
                    variables.update(parsed["vars"])
                if "secrets" in parsed:
                    variables.update(parsed["secrets"])
                environments.append(BruEnvironment(name=env_file.stem, variables=variables))
            except BruParseError as e:
                logger.warning(f"Skipping malformed environment file {env_file}: {e}")
                continue

        return environments
