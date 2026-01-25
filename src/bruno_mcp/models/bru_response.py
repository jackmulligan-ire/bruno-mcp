"""BruResponse data model for HTTP responses."""
from pydantic import BaseModel


class BruResponse(BaseModel):
    """Response from executing a Bruno request."""

    status: int
    headers: dict[str, str]
    body: str
