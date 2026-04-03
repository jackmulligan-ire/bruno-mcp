"""Tests for BaseBruParser section splitting."""

import pytest

from bruno_mcp.models import BruParseError
from bruno_mcp.parsers import BaseBruParser


class TestBaseBruParserSplitIntoSections:
    """Exercise _split_into_sections on the shared Bru file base parser."""

    @pytest.fixture
    def base_bru_parser(self):
        return BaseBruParser()

    def test_split_maps_braced_sections_to_line_lists(self, base_bru_parser):
        content = """
                  meta {
                    name: Example
                    seq: 1
                  }

                  vars {
                    baseUrl: http://localhost
                    token: {{secret}}
                  }
                  """

        sections = base_bru_parser._split_into_sections(content)

        assert set(sections.keys()) == {"meta", "vars"}
        assert sections["meta"] == ["name: Example", "seq: 1"]
        assert sections["vars"] == ["baseUrl: http://localhost", "token: {{secret}}"]

    def test_split_raises_when_braces_unmatched(self, base_bru_parser):
        content = """meta {
                      name: Broken
                  """

        with pytest.raises(BruParseError, match="Unmatched braces"):
            base_bru_parser._split_into_sections(content)

    def test_split_omits_empty_lines_from_section_bodies(self, base_bru_parser):
        content = """vars {
                    host: example.com

                    port: 8080
                  }"""

        sections = base_bru_parser._split_into_sections(content)

        assert sections["vars"] == ["host: example.com", "port: 8080"]
