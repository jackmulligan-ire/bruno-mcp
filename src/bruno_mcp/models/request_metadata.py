"""RequestMetadata data model for Bruno collection scanning.

This model represents lightweight metadata about a .bru file, used for
discovery and listing purposes. Unlike BruRequest, which contains the full
parsed request data (headers, params, body, auth), RequestMetadata only
contains essential identifying information needed to locate and reference
a request within a collection.
"""
from pydantic import BaseModel


class RequestMetadata(BaseModel):
    """Lightweight metadata for a Bruno request file.

    Used for collection scanning and discovery. Contains only essential
    identifying information, not the full request details.

    Attributes:
        id: Request identifier (relative path without .bru extension).
            Example: "users/get-user"
        name: Display name from meta section.
        method: HTTP method (GET, POST, etc.).
        url: Request URL (may contain unresolved variables).
        file_path: Relative path to .bru file from collection root.
            Example: "users/get-user.bru"
    """

    id: str
    name: str
    method: str
    url: str
    file_path: str
