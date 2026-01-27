"""HTTP request executor for Bruno requests."""

import json
import httpx

from bruno_mcp.models import BruRequest, BruResponse
from bruno_mcp.resolvers import VariableResolver


class RequestExecutor:
    """Executes HTTP requests from Bruno .bru files."""

    def execute(self, request: BruRequest, resolver: VariableResolver) -> BruResponse:
        """Execute a BruRequest with variable resolution.

        Args:
            request: Parsed Bruno request to execute.
            resolver: Variable resolver for {{variable}} placeholders.

        Returns:
            BruResponse with status, headers, and body.

        Raises:
            ValueError: If required path parameters are missing.
            httpx.HTTPError: For network/connection errors.
        """
        required_params = request.extract_path_parameters()
        if required_params:
            missing = resolver.validate_required_variables(request.url)
            if missing:
                missing_list = ", ".join(sorted(missing))
                required_list = ", ".join(sorted(required_params))
                raise ValueError(
                    f"Missing required path parameters: {missing_list}. "
                    f"Required: {required_list}"
                )

        resolved_url = resolver.resolve(request.url)

        resolved_headers = {key: resolver.resolve(value) for key, value in request.headers.items()}

        resolved_params = {key: resolver.resolve(value) for key, value in request.params.items()}

        json_body = (
            json.loads(resolver.resolve(request.body["content"]))
            if request.body and request.body.get("type") == "json"
            else None
        )

        with httpx.Client() as client:
            response = client.request(
                method=request.method,
                url=resolved_url,
                params=resolved_params,
                headers=resolved_headers,
                json=json_body,
            )

        return BruResponse(
            status=response.status_code, headers=dict(response.headers), body=response.text
        )
