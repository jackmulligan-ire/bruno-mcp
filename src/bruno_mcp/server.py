from pathlib import Path
import os

from bruno_mcp.executors import RequestExecutor
from bruno_mcp.parsers import BruParser, EnvParser
from bruno_mcp.resolvers import VariableResolver
from bruno_mcp.scanners import CollectionScanner
from fastmcp import FastMCP


class MCPServer:
    """MCP server for Bruno API collections.

    Provides Model Context Protocol (MCP) resources and tools for discovering
    and executing Bruno API requests. Scans a Bruno collection directory for
    .bru files and exposes them as MCP resources and executable tools.
    """

    def __init__(
        self,
        collection_path: Path,
        bru_parser: BruParser,
        env_parser: EnvParser,
        executor: RequestExecutor,
        resolver_cls: type[VariableResolver],
        scanner: CollectionScanner,
        mcp: FastMCP,
    ):
        """Initialize MCP server with dependencies.

        Args:
            collection_path: Path to Bruno collection directory.
            bru_parser: Parser for .bru request files.
            env_parser: Parser for environment and collection variables.
            executor: Executor for HTTP requests.
            resolver_cls: Variable resolver class for resolving {{variables}}.
            scanner: Scanner for discovering .bru files in collection.
            mcp: FastMCP instance for MCP protocol handling.
        """
        self._collection_path = collection_path
        self._bru_parser = bru_parser
        self._env_parser = env_parser
        self._scanner = scanner
        self._executor = executor
        self._resolver_cls = resolver_cls
        self._mcp = mcp
        self._collection_metadata = self._scanner.scan_collection(self._collection_path)
        self._register_resources()
        self._register_tools()

    @property
    def mcp(self) -> FastMCP:
        """FastMCP instance for running the server."""
        return self._mcp

    @classmethod
    def create(cls) -> "MCPServer":
        """Create MCPServer instance from environment configuration.

        Reads BRUNO_COLLECTION_PATH from environment and initializes
        all dependencies with default implementations.

        Returns:
            Configured MCPServer instance.

        Raises:
            ValueError: If BRUNO_COLLECTION_PATH environment variable is not set.
        """
        collection_path = os.environ.get("BRUNO_COLLECTION_PATH")
        if not collection_path:
            raise ValueError("BRUNO_COLLECTION_PATH not set")
        bru_parser = BruParser()
        return cls(
            collection_path=Path(collection_path),
            bru_parser=bru_parser,
            env_parser=EnvParser(),
            executor=RequestExecutor(),
            resolver_cls=VariableResolver,
            scanner=CollectionScanner(bru_parser),
            mcp=FastMCP("bruno-mcp"),
        )

    def _register_resources(self):
        """Register MCP resources with the FastMCP instance.

        Registers the collection_tree resource that provides metadata
        for all requests in the Bruno collection.
        """

        @self._mcp.resource("bruno://collection")
        def collection_tree():
            return [request.model_dump() for request in self._collection_metadata]

    def _register_tools(self):
        """Register MCP tools with the FastMCP instance.

        Registers tools for listing available requests and executing
        them by ID.
        """

        @self._mcp.tool()
        def run_request_by_id(request_id: str, environment_name: str | None = None):
            """Execute a Bruno request by ID.

            Args:
                request_id: Identifier of the request to execute.
                environment_name: Optional environment name to load variables from.

            Returns:
                Dictionary containing the HTTP response (status, headers, body).

            Raises:
                ValueError: If request_id is not found in the collection.
            """
            # Load the request
            metadata = next((m for m in self._collection_metadata if m.id == request_id), None)
            if not metadata:
                raise ValueError(f"Request not found: {request_id}")

            # Load the variables
            env_path = (
                str(self._collection_path / "environments" / f"{environment_name}.bru")
                if environment_name
                else None
            )
            variables = self._env_parser.load_environment(
                collection_path=str(self._collection_path / "bruno.json"), environment_path=env_path
            )

            # Construct full path and parse
            full_path = self._collection_path / metadata.file_path
            request = self._bru_parser.parse_file(str(full_path))

            # Execute the request
            response = self._executor.execute(request, self._resolver_cls(variables))
            # Return the response
            return response.model_dump()

        @self._mcp.tool()
        def list_requests():
            """List all available Bruno requests in the collection.

            Returns a list of all discovered requests with their metadata including
            ID, name, HTTP method, URL (with variable placeholders), and file path.
            This allows MCP clients to discover available endpoints before execution.

            Returns:
                List of dictionaries containing request metadata. Each dictionary includes:
                    - id: Unique identifier (relative path without .bru extension)
                    - name: Human-readable request name
                    - method: HTTP method (GET, POST, PUT, DELETE, etc.)
                    - url: Request URL (may contain {{variable}} placeholders)
                    - file_path: Relative path to the .bru file
            """
            return [request.model_dump() for request in self._collection_metadata]
