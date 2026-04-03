"""Pytest configuration and fixtures."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from dotenv import load_dotenv

load_dotenv(".env.test")


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_collection_dir(fixtures_dir):
    """Return path to sample collection directory."""
    return fixtures_dir / "sample_collection"


@pytest.fixture
def opencollection_root(fixtures_dir):
    """Return path to minimal OpenCollection root (opencollection.yml only)."""
    return fixtures_dir / "opencollection_root"


@pytest.fixture
def mixed_collection_markers(fixtures_dir):
    """Return path to a directory with both bruno.json and opencollection.yml (invalid root)."""
    return fixtures_dir / "mixed_collection_markers"


@pytest.fixture
def invalid_fixtures_dir(fixtures_dir):
    """Return path to invalid fixtures directory."""
    return fixtures_dir / "invalid"


@pytest.fixture
def collection_root():
    """Return a mock collection root for request ID generation."""
    return Path(__file__).parent / "fixtures" / "sample_collection"


@pytest.fixture
def mock_mcp():
    """Mock FastMCP instance for MCP server tests."""
    return Mock()


@pytest.fixture
def mock_executor():
    """Mock executor for MCP server tests."""
    return Mock()
