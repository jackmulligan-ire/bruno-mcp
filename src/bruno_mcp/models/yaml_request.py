"""YamlRequest data model for OpenCollection YAML request files."""

from typing import Any, Optional

from pydantic import Field

from bruno_mcp.models.base_request import BaseRequest


class YamlRequest(BaseRequest):
    """Pydantic model representing a parsed OpenCollection YAML request file."""

    filepath: str
    info: dict[str, Any]
    method: str
    headers: list[dict[str, Any]] = Field(default_factory=list)
    params: list[dict[str, Any]] = Field(default_factory=list)
    body: Optional[dict[str, Any]] = None
    auth: Optional[dict[str, Any] | str] = None
