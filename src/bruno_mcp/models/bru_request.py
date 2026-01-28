"""BruRequest data model for Bruno .bru files."""

import json
from pathlib import Path
from typing import Any, Optional

from bruno_mcp.models.base_request import BaseRequest


class BruRequest(BaseRequest):
    """Pydantic model representing a parsed .bru file."""

    filepath: str
    meta: dict  # {name, type, seq}
    method: str  # GET, POST, etc.
    params: dict  # Query parameters
    headers: dict
    body: Optional[dict] = None  # {type: "json|form|multipart", content: "..."}
    auth: Optional[dict] = None  # {type: "bearer|basic", token: "..."}

    def get_name(self) -> str:
        """Get the display name of the request from meta section.

        Returns:
            Request name from meta, or 'Unnamed Request' if not found.
        """
        name = self.meta.get("name", "Unnamed Request")
        return str(name) if name else "Unnamed Request"

    def get_request_id(self) -> str:
        """Generate request ID from filepath.

        The request ID is the relative path from collection root without the .bru extension.
        For example: "users/create-user.bru" -> "users/create-user"

        Returns:
            Request identifier string.
        """
        path = Path(self.filepath)
        # path.stem is already a str, but explicit for type safety
        return path.stem

    def with_overrides(
        self,
        body: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> "BruRequest":
        """Return a new BruRequest with body and/or query_params overridden.

        Args:
            body: Optional dictionary to override the request body.
            query_params: Optional dictionary to override query parameters.

        Returns:
            New BruRequest instance with overrides applied.
        """
        updates = {}
        if query_params is not None:
            updates["params"] = {**self.params, **query_params}
        if body is not None:
            updates["body"] = {"type": "json", "content": json.dumps(body)}

        return self.model_copy(update=updates)
