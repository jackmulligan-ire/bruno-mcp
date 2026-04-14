"""RequestMetadata data model for Bruno collection scanning.

This model represents lightweight metadata about a .bru file, used for
discovery and listing purposes. Unlike BruRequest, which contains the full
parsed request data (headers, params, body, auth), RequestMetadata only
contains essential identifying information needed to locate and reference
a request within a collection.
"""

from typing import Optional

from pydantic import Field

from bruno_mcp.models.base_request import BaseRequest
from bruno_mcp.models.request_example import RequestExample


class RequestMetadata(BaseRequest):
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
        variable_names: {{variable}} names used by the request, extracted at
            scan time. Used to generate example_call; not surfaced in output.
        example_call: Ready-to-use run_request_by_id invocation for this
            request. Populated after environments are loaded.
    """

    id: str
    name: str
    method: str
    file_path: str
    variable_names: list[str] = Field(default=[], exclude=True)
    example_call: Optional[RequestExample] = None
