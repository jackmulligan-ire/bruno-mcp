"""Environment parser for Bruno environment .bru files under a collection."""

import logging
from pathlib import Path

import yaml

from bruno_mcp.models import BruEnvironment, BruParseError, CollectionFormat, CollectionInfo
from bruno_mcp.parsers import BaseBruParser

logger = logging.getLogger(__name__)


class EnvParser(BaseBruParser):
    """Parser for Bruno environment .bru and .yaml files related to environments."""

    def _parse_vars_section(self, lines: list[str]) -> dict:
        """Parse vars or vars:secret section into dictionary."""
        result = {}
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    def _parse_bru_environment(self, filepath: Path) -> BruEnvironment:
        """Parse a single environment .bru file into a BruEnvironment."""
        content = filepath.read_text(encoding="utf-8")

        if not content.strip():
            return BruEnvironment(name=filepath.stem, variables={})

        sections = self._split_into_sections(content)

        variables: dict[str, str] = {}
        if "vars" in sections:
            variables.update(self._parse_vars_section(sections["vars"]))
        if "vars:secret" in sections:
            variables.update(self._parse_vars_section(sections["vars:secret"]))

        return BruEnvironment(name=filepath.stem, variables=variables)

    def _parse_yaml_environment(self, filepath: Path) -> BruEnvironment:
        """Parse an OpenCollection environment YAML file into a BruEnvironment."""
        try:
            raw = filepath.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            raise BruParseError(f"Invalid YAML in environment file: {e}") from e

        if not isinstance(data, dict):
            raise BruParseError("No environment YAML file content found")

        variables: dict[str, str] = {}
        for entry in data.get("variables", []):
            if entry.get("enabled") is False:
                continue
            key = entry.get("name")
            variables[key] = entry.get("value", "")

        name = data.get("name", filepath.stem)

        return BruEnvironment(name=name, variables=variables)

    def list_environments(self, collection_info: CollectionInfo) -> list[BruEnvironment]:
        """List all environments in a collection.

        For classic Bruno collections, scans ``collection_info.path / "environments"``
        for ``*.bru`` files. For OpenCollection, scans the same directory for
        ``*.yml`` environment files.

        Args:
            collection_info: Loaded collection metadata (path and format).

        Returns:
            List of BruEnvironment instances with name and variables.
            Empty list if the env directory is missing or the format has no
            environments.
        """
        env_dir = collection_info.path / "environments"
        if not env_dir.exists():
            return []

        environments: list[BruEnvironment] = []

        if collection_info.format == CollectionFormat.OPENCOLLECTION:
            parse = self._parse_yaml_environment
            env_files = sorted(
                {*env_dir.glob("*.yml"), *env_dir.glob("*.yaml")},
                key=lambda p: str(p),
            )
        else:
            parse = self._parse_bru_environment
            env_files = sorted(env_dir.glob("*.bru"))

        for env_file in env_files:
            try:
                environments.append(parse(env_file))
            except BruParseError as e:
                logger.warning(f"Skipping malformed environment file {env_file}: {e}")
                continue
        return environments
