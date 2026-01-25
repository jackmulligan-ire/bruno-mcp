"""Base parser with common functionality for Bruno file parsing."""
from bruno_mcp.models import BruParseError


class BaseParser:
    """Base parser with shared parsing logic for .bru files."""

    def _split_into_sections(self, content: str) -> dict[str, list[str]]:
        """Split file content into named sections.

        Args:
            content: Raw file content as string.

        Returns:
            Dictionary mapping section names to their content lines.

        Raises:
            BruParseError: If braces are unmatched.
        """
        sections = {}
        lines = content.split('\n')
        current_section = None
        current_lines = []
        brace_count = 0

        for line in lines:
            stripped = line.strip()

            if stripped.endswith('{') and not current_section:
                section_name = stripped[:-1].strip()
                if section_name:
                    current_section = section_name
                    brace_count = 1
                    current_lines = []
                    continue

            if current_section:
                opening_braces = line.count('{')
                closing_braces = line.count('}')
                brace_count += opening_braces - closing_braces
                
                if brace_count == 0:
                    sections[current_section] = current_lines
                    current_section = None
                    current_lines = []
                    continue

                if stripped:
                    current_lines.append(line.strip())

        if brace_count != 0:
            raise BruParseError("Unmatched braces in file")

        return sections
