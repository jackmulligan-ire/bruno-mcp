"""Tests for CollectionScanner."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from bruno_mcp.models import BruParseError, BruRequest, CollectionInfo, RequestMetadata
from bruno_mcp.parsers import BruParser
from bruno_mcp.scanners.collection_scanner import CollectionFormat, CollectionScanner


def bru_collection_info(path: Path) -> CollectionInfo:
    resolved = path.resolve()
    return CollectionInfo(name=resolved.name, path=resolved, format=CollectionFormat.BRU)


class TestCollectionScanner:
    """Test collection scanning and metadata extraction."""

    def test_scan_finds_all_bru_files(self, sample_collection_dir):
        """Test scanner finds all .bru files in collection."""
        parser = BruParser()
        scanner = CollectionScanner(parser)
        expected_ids = [
            "users/get-user",
            "users/create-user",
            "users/update-user",
            "users/delete-user",
            "users/request-with-undefined-var",
            "posts/create-post",
            "posts/list-posts",
            "posts/form-data",
            "posts/form-upload",
            "posts/nested-data",
            "posts/simple-get",
            "posts/request-with-body-var",
            "posts/request-with-process-env",
        ]

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        result_ids = [r.id for r in results]
        for expected_id in expected_ids:
            assert expected_id in result_ids

    def test_scan_extracts_request_metadata(self, sample_collection_dir):
        """Test scanner extracts correct metadata fields."""
        parser = BruParser()
        scanner = CollectionScanner(parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        get_user = next(r for r in results if r.id == "users/get-user")
        assert get_user.name == "Get User"
        assert get_user.method == "GET"
        assert get_user.url == "https://api.example.com/users/{{userId}}"
        assert get_user.file_path == "users/get-user.bru"

    def test_scan_generates_correct_request_ids(self, sample_collection_dir):
        """Test scanner generates IDs from relative paths."""
        parser = BruParser()
        scanner = CollectionScanner(parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        ids = [r.id for r in results]
        assert "users/get-user" in ids
        assert "users/create-user" in ids
        assert "posts/create-post" in ids
        assert "posts/list-posts" in ids

    def test_scan_handles_nested_directories(self, sample_collection_dir):
        """Test scanner traverses nested directory structure."""
        parser = BruParser()
        scanner = CollectionScanner(parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        user_requests = [r for r in results if r.id.startswith("users/")]
        post_requests = [r for r in results if r.id.startswith("posts/")]
        assert "users/get-user" in [r.id for r in user_requests]
        assert "users/create-user" in [r.id for r in user_requests]
        assert "posts/create-post" in [r.id for r in post_requests]
        assert "posts/list-posts" in [r.id for r in post_requests]

    @patch("bruno_mcp.scanners.collection_scanner.Path.rglob")
    def test_scan_invalid_bru_file(self, mock_rglob, sample_collection_dir):
        """Test scanner skips malformed .bru files without crashing."""
        valid_file = Mock(spec=Path)
        valid_file.stat.return_value = Mock(st_size=1024)
        valid_file.relative_to.return_value = Path("valid.bru")
        valid_file.with_suffix.return_value = Path("valid")
        invalid_file = Mock(spec=Path)
        invalid_file.stat.return_value = Mock(st_size=1024)
        mock_rglob.return_value = [valid_file, invalid_file]

        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.side_effect = [
            BruRequest(
                filepath="valid.bru",
                meta={"name": "Valid Request"},
                method="GET",
                url="https://example.com",
                headers={},
                params={},
                body=None,
                auth=None,
            ),
            BruParseError("Malformed file"),
        ]

        scanner = CollectionScanner(mock_parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        assert len(results) == 1
        assert results[0].name == "Valid Request"

    @patch("bruno_mcp.scanners.collection_scanner.Path.exists")
    def test_scan_rejects_directory_without_bruno_json(self, mock_exists, sample_collection_dir):
        """Test scanner raises error for non-collection directories."""
        mock_exists.return_value = False
        parser = BruParser()
        scanner = CollectionScanner(parser)

        with pytest.raises(ValueError, match="Not a valid Bruno collection"):
            scanner.scan_collection_for_format(sample_collection_dir)

    @patch("bruno_mcp.scanners.collection_scanner.Path.rglob")
    def test_scan_enforces_max_file_limit(self, mock_rglob, sample_collection_dir):
        """Test scanner raises error if collection exceeds file limit."""
        fake_files = [Path(f"request_{i}.bru") for i in range(1001)]
        mock_rglob.return_value = fake_files
        parser = BruParser()
        scanner = CollectionScanner(parser)

        with pytest.raises(ValueError, match="Collection too large"):
            scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

    @patch("bruno_mcp.scanners.collection_scanner.Path.rglob")
    def test_scan_skips_oversized_files(self, mock_rglob, sample_collection_dir):
        """Test scanner skips files larger than MAX_FILE_SIZE."""
        normal_file = Mock(spec=Path)
        normal_file.stat.return_value = Mock(st_size=1024)
        normal_file.relative_to.return_value = Path("normal.bru")
        normal_file.with_suffix.return_value = Path("normal")
        huge_file = Mock(spec=Path)
        huge_file.stat.return_value = Mock(st_size=11 * 1024 * 1024)
        mock_rglob.return_value = [normal_file, huge_file]

        mock_parser = Mock(spec=BruParser)
        mock_parser.parse_file.return_value = BruRequest(
            filepath="normal.bru",
            meta={"name": "Normal Request"},
            method="GET",
            url="https://example.com",
            headers={},
            params={},
            body=None,
            auth=None,
        )

        scanner = CollectionScanner(mock_parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        assert len(results) == 1
        assert results[0].name == "Normal Request"

    def test_collection_scanner_extracts_variable_names_from_request(self, sample_collection_dir):
        """RequestMetadata stores variable names extracted from URL, headers, body, and params."""
        parser = BruParser()
        scanner = CollectionScanner(parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        get_user = next(r for r in results if r.id == "users/get-user")
        assert set(get_user.variable_names) == {"userId", "authToken"}
        body_var_request = next(r for r in results if r.id == "posts/request-with-body-var")
        assert "postId" in body_var_request.variable_names

    def test_collection_scanner_excludes_process_env_from_variable_names(
        self, sample_collection_dir
    ):
        """{{process.env.VAR}} references are never included in variable_names."""
        parser = BruParser()
        scanner = CollectionScanner(parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        process_env_request = next(r for r in results if r.id == "posts/request-with-process-env")
        assert "resourceId" in process_env_request.variable_names
        assert "process.env.API_KEY" not in process_env_request.variable_names
        assert "API_KEY" not in process_env_request.variable_names


class TestScanCollectionForFormat:
    """Tests for collection root detection and OpenCollection placeholder scan."""

    def test_scan_for_format_returns_bru_for_bru_collection(self, sample_collection_dir):
        parser = BruParser()
        scanner = CollectionScanner(parser)

        assert scanner.scan_collection_for_format(sample_collection_dir) == CollectionFormat.BRU

    def test_scan_for_format_returns_opencollection(self, opencollection_root: Path):
        parser = BruParser()
        scanner = CollectionScanner(parser)
        root = opencollection_root.resolve()

        assert scanner.scan_collection_for_format(root) == CollectionFormat.OPENCOLLECTION

    def test_scan_for_format_raises_when_both_markers_present(
        self, mixed_collection_markers: Path
    ):
        parser = BruParser()
        scanner = CollectionScanner(parser)
        root = mixed_collection_markers.resolve()

        with pytest.raises(ValueError) as exc_info:
            scanner.scan_collection_for_format(root)

        message = str(exc_info.value)
        assert "bruno.json" in message
        assert "opencollection.yml" in message
        assert str(root) in message

    def test_scan_for_requests_returns_empty_for_opencollection(
        self, opencollection_root: Path
    ):
        parser = BruParser()
        scanner = CollectionScanner(parser)
        root = opencollection_root.resolve()
        info = CollectionInfo(
            name=root.name,
            path=root,
            format=CollectionFormat.OPENCOLLECTION,
        )

        assert scanner.scan_collection_for_requests(info) == []


class TestRequestMetadata:
    """Test RequestMetadata model."""

    def test_request_metadata_model(self):
        """Test RequestMetadata can be instantiated with required fields."""
        metadata = RequestMetadata(
            id="users/get-user",
            name="Get User",
            method="GET",
            url="https://api.example.com/users/{{userId}}",
            file_path="users/get-user.bru",
        )

        assert metadata.id == "users/get-user"
        assert metadata.name == "Get User"
        assert metadata.method == "GET"
        assert metadata.url == "https://api.example.com/users/{{userId}}"
        assert metadata.file_path == "users/get-user.bru"
