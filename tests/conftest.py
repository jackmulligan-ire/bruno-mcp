"""Pytest configuration and fixtures."""

from pathlib import Path

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
def invalid_fixtures_dir(fixtures_dir):
    """Return path to invalid fixtures directory."""
    return fixtures_dir / "invalid"


@pytest.fixture
def collection_root():
    """Return a mock collection root for request ID generation."""
    return Path(__file__).parent / "fixtures" / "sample_collection"
