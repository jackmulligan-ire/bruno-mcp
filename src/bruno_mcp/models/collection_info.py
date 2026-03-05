"""CollectionInfo model for multi-collection support."""

from pathlib import Path

from pydantic import BaseModel


class CollectionInfo(BaseModel):
    """Metadata for a loaded Bruno collection.

    Attributes:
        name: Collection identifier (basename of directory path).
        path: Absolute path to the collection root directory.
    """

    name: str
    path: Path
