"""Variable resolver for Bruno template variables."""
import os
import re
from typing import Any


class VariableResolutionError(Exception):
    """Raised when a variable cannot be resolved."""
    pass


class VariableResolver:
    """Resolves {{variable}} placeholders in strings."""

    def __init__(self, variables: dict[str, Any]):
        """Initialize resolver with variable dictionary.

        Args:
            variables: Dictionary of variable names to values.
        """
        self.variables = variables

    def _resolve_process_env(self, text: str) -> str:
        """Resolve {{process.env.VAR}} patterns from system environment."""
        pattern = r'\{\{process\.env\.([^}]+)\}\}'
        
        def replacer(match):
            env_var = match.group(1)
            value = os.environ.get(env_var)
            if value is None:
                raise VariableResolutionError(
                    f"Environment variable not found: {env_var}"
                )
            return value
        
        return re.sub(pattern, replacer, text)

    def _resolve_single_pass(self, text: str, variables: dict) -> str:
        """Perform one pass of variable resolution."""
        pattern = r'\{\{([^{}]+)\}\}'
        
        def replacer(match):
            var_name = match.group(1).strip()
            
            if var_name.startswith('process.env.'):
                return match.group(0)
            
            if var_name not in variables:
                raise VariableResolutionError(
                    f"Variable not found: {var_name}"
                )
            
            return str(variables[var_name])
        
        return re.sub(pattern, replacer, text)

    def resolve(self, text: str, max_nesting_depth: int = 5) -> str:
        """Resolve all {{variable}} placeholders in text.

        Supports:
        - Simple variables: {{userId}}
        - Process env: {{process.env.TOKEN}}
        - Nested variables: {{urls.{{env}}}}

        Args:
            text: String containing {{variable}} placeholders.
            max_nesting_depth: Maximum depth for nested variable resolution.
                              Simple variables resolve in 1 pass, nested need multiple.

        Returns:
            String with all variables resolved.

        Raises:
            VariableResolutionError: If a variable cannot be resolved.
        """
        # Early return: skip processing if no variables present (performance optimization)
        if not text or '{{' not in text:
            return text

        resolved_text = text
        resolved_vars = dict(self.variables)

        for var_name, var_value in list(resolved_vars.items()):
            if isinstance(var_value, str) and '{{process.env.' in var_value:
                resolved_vars[var_name] = self._resolve_process_env(var_value)

        for _ in range(max_nesting_depth):
            previous = resolved_text
            resolved_text = self._resolve_single_pass(resolved_text, resolved_vars)
            
            if resolved_text == previous:
                break

        if '{{' in resolved_text and '}}' in resolved_text:
            match = re.search(r'\{\{([^}]+)\}\}', resolved_text)
            if match:
                raise VariableResolutionError(
                    f"Unresolved variable after {max_nesting_depth} passes: {match.group(1)}"
                )

        return resolved_text
