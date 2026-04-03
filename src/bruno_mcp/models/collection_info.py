"""CollectionInfo model for multi-collection support."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class CollectionFormat(str, Enum):
    """Layout detected at a Bruno collection root."""

    BRU = "bru"
    OPENCOLLECTION = "opencollection"


class CollectionInfo(BaseModel):
    """Metadata for a loaded Bruno collection.

    Attributes:
        name: Collection identifier (basename of directory path).
        path: Absolute path to the collection root directory.
        format: Classic .bru layout (bruno.json) or OpenCollection YAML (opencollection.yml).
    """

    name: str
    path: Path
    format: CollectionFormat
