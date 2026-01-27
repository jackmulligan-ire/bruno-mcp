"""Base request model with shared URL path parameter extraction."""

import re
from pydantic import BaseModel


class BaseRequest(BaseModel):
    """Base class for request models with URL path parameter extraction.

    Provides common functionality for extracting path parameters from URLs
    that contain {{variable}} placeholders.
    """

    url: str

    def extract_path_parameters(self) -> set[str]:
        """Extract all {{variable}} placeholders from this request's URL.

        Excludes {{process.env.*}} patterns as those are resolved from
        system environment, not user-provided parameters.

        Returns:
            Set of variable names (without braces).
            Example: "https://api.com/{{groupId}}/users/{{userId}}" -> {"groupId", "userId"}
        """
        if not self.url or "{{" not in self.url:
            return set()

        pattern = r"\{\{([^{}]+)\}\}"
        matches = re.findall(pattern, self.url)

        path_params = {
            match.strip() for match in matches if not match.strip().startswith("process.env.")
        }

        return path_params
