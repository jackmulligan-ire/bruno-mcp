"""Tests for BruRequest model."""
import pytest

from bruno_mcp.models import BruRequest


class TestBruRequest:
    """Test the BruRequest Pydantic model."""

    def test_get_name_returns_meta_name(self):
        """Test get_name() returns name from meta."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={"name": "My Request", "type": "http", "seq": 1},
            method="GET",
            url="https://api.example.com/test",
            params={},
            headers={}
        )

        name = request.get_name()

        assert name == "My Request"

    def test_get_name_returns_default_when_missing(self):
        """Test get_name() returns default when name not in meta."""
        request = BruRequest(
            filepath="/path/to/request.bru",
            meta={"type": "http", "seq": 1},
            method="GET",
            url="https://api.example.com/test",
            params={},
            headers={}
        )

        name = request.get_name()

        assert name == "Unnamed Request"
