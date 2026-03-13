from __future__ import annotations

import os
import subprocess
from pathlib import Path

from bruno_mcp.executors import CLIExecutor
from bruno_mcp.models import CollectionInfo, RequestMetadata
from bruno_mcp.parsers import BruParser, EnvParser
from bruno_mcp.scanners import CollectionScanner
from fastmcp import FastMCP


class MCPServer:
    """MCP server for Bruno API collections.

    Provides Model Context Protocol (MCP) resources and tools for discovering
    and executing Bruno API requests. Supports multiple collections with an
    active collection that tools and resources operate on.
    """

    def __init__(
        self,
        collections: list[CollectionInfo],
        collection_metadata: dict[str, list[RequestMetadata]],
        executor: CLIExecutor,
        mcp: FastMCP,
        env_parser: EnvParser,
    ):
        """Initialize MCP server with dependencies.

        Args:
            collections: List of loaded collection info.
            collection_metadata: Metadata keyed by collection name.
            executor: CLI executor for HTTP requests.
            mcp: FastMCP instance for MCP protocol handling.
            env_parser: Parser for environment files.
        """
        if not collections:
            raise ValueError("At least one collection is required")
        self._collections = collections
        self._collection_metadata = collection_metadata
        self._executor = executor
        self._mcp = mcp
        self._env_parser = env_parser
        self._active_collection_name = collections[0].name
        self._register_resources()
        self._register_tools()

    def _active_collection_path(self) -> Path:
        """Path of the currently active collection."""
        collection = next(
            (c for c in self._collections if c.name == self._active_collection_name),
            None,
        )
        if collection is None:
            raise ValueError(f"Collection not found: {self._active_collection_name}")
        return collection.path

    def _active_collection_metadata(self) -> list[RequestMetadata]:
        """Request metadata for the currently active collection."""
        return self._collection_metadata.get(self._active_collection_name, [])

    @property
    def mcp(self) -> FastMCP:
        """FastMCP instance for running the server."""
        return self._mcp

    @staticmethod
    def _validate_cli() -> None:
        """Validate that Bruno CLI is available.

        Raises:
            RuntimeError: If CLI validation fails or CLI is not found.
        """
        try:
            result = subprocess.run(
                ["bru", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "Bruno CLI validation failed. Please ensure 'bru' is installed and available in PATH."
                )
        except FileNotFoundError:
            raise RuntimeError(
                "Bruno CLI not found. Please install Bruno CLI and ensure 'bru' is available in PATH."
            )

    @classmethod
    def _load_directory_collections(
        cls,
        path_str: str,
        scanner: CollectionScanner,
        collections: list[CollectionInfo],
        collection_metadata: dict[str, list[RequestMetadata]],
    ) -> None:
        base_path = Path(path_str[:-2].rstrip("/")).resolve()
        if not base_path.is_dir():
            raise ValueError(f"Directory does not exist: {base_path}")
        found_any = False
        for child in sorted(base_path.iterdir()):
            if child.is_dir() and (child / "bruno.json").exists():
                try:
                    metadata = scanner.scan_collection(child)
                except ValueError as e:
                    raise ValueError(str(e)) from e
                qualified_name = f"{base_path.name}/{child.name}"
                collections.append(CollectionInfo(name=qualified_name, path=child))
                collection_metadata[qualified_name] = metadata
                found_any = True
        if not found_any:
            raise ValueError(f"No collections found in {base_path}")

    @classmethod
    def create(cls) -> "MCPServer":
        """Create MCPServer instance from environment configuration.

        Reads BRUNO_COLLECTION_PATH from environment (supports multiple paths
        separated by os.pathsep), scans each collection, validates CLI availability,
        and initializes server with CLIExecutor.

        Returns:
            Configured MCPServer instance.

        Raises:
            ValueError: If BRUNO_COLLECTION_PATH is not set or a path is invalid.
            RuntimeError: If Bruno CLI is not available.
        """
        collection_paths_env = os.environ.get("BRUNO_COLLECTION_PATH")
        if not collection_paths_env:
            raise ValueError("BRUNO_COLLECTION_PATH not set")

        cls._validate_cli()

        paths = [p.strip() for p in collection_paths_env.split(os.pathsep) if p.strip()]
        if not paths:
            raise ValueError("BRUNO_COLLECTION_PATH contains no valid paths")

        bru_parser = BruParser()
        scanner = CollectionScanner(bru_parser)
        collections: list[CollectionInfo] = []
        collection_metadata: dict[str, list[RequestMetadata]] = {}

        for path_str in paths:
            if path_str.endswith("/*"):
                cls._load_directory_collections(path_str, scanner, collections, collection_metadata)
            else:
                abs_path = Path(path_str).resolve()
                try:
                    metadata = scanner.scan_collection(abs_path)
                except ValueError as e:
                    raise ValueError(str(e)) from e

                name = abs_path.name
                collections.append(CollectionInfo(name=name, path=abs_path))
                collection_metadata[name] = metadata

        names = [c.name for c in collections]
        if len(names) != len(set(names)):
            seen: set[str] = set()
            for n in names:
                if n in seen:
                    raise ValueError(f"Duplicate collection name: {n}")
                seen.add(n)

        return cls(
            collections=collections,
            collection_metadata=collection_metadata,
            executor=CLIExecutor(),
            mcp=FastMCP("bruno-mcp"),
            env_parser=EnvParser(),
        )

    def _register_resources(self):
        """Register MCP resources with the FastMCP instance."""

        @self._mcp.resource("bruno://collection_metadata")
        def collection_metadata():
            return [request.model_dump() for request in self._active_collection_metadata()]

        @self._mcp.resource("bruno://environments")
        def environments():
            envs = self._env_parser.list_environments(self._active_collection_path())
            return [environment.model_dump() for environment in envs]

        @self._mcp.resource("bruno://collections")
        def collections():
            return [
                {"name": collection.name, "path": str(collection.path)}
                for collection in self._collections
            ]

    def _register_tools(self):
        """Register MCP tools with the FastMCP instance."""

        @self._mcp.tool()
        def run_request_by_id(
            request_id: str,
            environment_name: str | None = None,
            variable_overrides: dict[str, str] | None = None,
        ):
            """Execute a Bruno request by ID.

            Args:
                request_id: Identifier of the request to execute.
                environment_name: Optional environment name to load variables from.
                variable_overrides: Optional dictionary of variable overrides.

            Returns:
                Dictionary containing the HTTP response (status, headers, body).

            Raises:
                ValueError: If request_id is not found in the collection.
            """
            metadata = next(
                (m for m in self._active_collection_metadata() if m.id == request_id),
                None,
            )
            if not metadata:
                raise ValueError(f"Request not found: {request_id}")

            request_file_path = Path(metadata.file_path)
            response = self._executor.execute(
                request_file_path,
                self._active_collection_path(),
                environment_name,
                variable_overrides,
            )
            return response.model_dump()

        @self._mcp.tool()
        def list_requests():
            """List all available Bruno requests in the active collection.

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
            return [request.model_dump() for request in self._active_collection_metadata()]

        @self._mcp.tool()
        def list_environments():
            """List all available environments in the active collection.

            Scans the collection's environments directory for .bru files
            and returns a list of environment dictionaries with name and variables.

            Returns:
                List of dictionaries with "name" (str) and "variables" (dict[str, str]) keys.
                Returns empty list if no environments found.
            """
            envs = self._env_parser.list_environments(self._active_collection_path())
            return [environment.model_dump() for environment in envs]

        @self._mcp.tool()
        def list_collections():
            """List all loaded Bruno collections.

            Returns a list of collections with name and path. Use set_active_collection
            to switch which collection tools operate on.

            Returns:
                List of dictionaries with "name" (str) and "path" (str) keys.
            """
            return [
                {"name": collection.name, "path": str(collection.path)}
                for collection in self._collections
            ]

        @self._mcp.tool()
        def set_active_collection(collection_name: str):
            """Set the active collection for tools and resources.

            Args:
                collection_name: Name of the collection to activate (basename of path).

            Returns:
                The name of the newly active collection, so the caller (e.g. an MCP agent)
                can confirm which collection is now active.

            Raises:
                ValueError: If collection_name is not found.
            """
            if not any(collection.name == collection_name for collection in self._collections):
                raise ValueError(f"Collection not found: {collection_name}")
            self._active_collection_name = collection_name
            return collection_name
