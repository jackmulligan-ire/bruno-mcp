"""RequestExample data model for the example_call field in RequestMetadata."""

from typing import Optional

from pydantic import BaseModel


class RequestExample(BaseModel):
    """An example run_request_by_id invocation for a given request.

    Shows a caller the minimal set of parameters needed to execute the request,
    with placeholder values for any variables that must be supplied.

    Attributes:
        request_id: The ID to pass to run_request_by_id.
        environment_name: The first available environment name, or None when
            the collection has no environments.
        variable_overrides: Variables defined in at least one environment that
            the request uses, each with a "<var-name>" placeholder value.
            Omitted when there are no overridable variables.
    """

    request_id: str
    environment_name: Optional[str] = None
    variable_overrides: Optional[dict[str, str]] = None
