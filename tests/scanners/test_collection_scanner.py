"""Tests for CollectionScanner."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from bruno_mcp.models import BruParseError, BruRequest, CollectionInfo, RequestMetadata
from bruno_mcp.parsers import BruParser, YamlParser
from bruno_mcp.scanners.collection_scanner import CollectionFormat, CollectionScanner


@pytest.fixture
def bru_parser():
    return BruParser()


@pytest.fixture
def yaml_parser():
    return YamlParser()


def bru_collection_info(path: Path) -> CollectionInfo:
    resolved = path.resolve()
    return CollectionInfo(name=resolved.name, path=resolved, format=CollectionFormat.BRU)


def yaml_collection_info(path: Path) -> CollectionInfo:
    resolved = path.resolve()
    return CollectionInfo(name=resolved.name, path=resolved, format=CollectionFormat.OPENCOLLECTION)


class TestCollectionScannerBruRequests:
    """Test collection scanning of BRU request files."""

    def test_scan_finds_all_bru_files(self, bru_parser, yaml_parser, sample_collection_dir):
        scanner = CollectionScanner(bru_parser, yaml_parser)
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

    def test_scan_extracts_request_metadata(self, bru_parser, yaml_parser, sample_collection_dir):
        scanner = CollectionScanner(bru_parser, yaml_parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        get_user = next(r for r in results if r.id == "users/get-user")
        assert get_user.name == "Get User"
        assert get_user.method == "GET"
        assert get_user.url == "https://api.example.com/users/{{userId}}"
        assert get_user.file_path == "users/get-user.bru"

    def test_scan_generates_correct_request_ids(
        self, bru_parser, yaml_parser, sample_collection_dir
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        ids = [r.id for r in results]
        assert "users/get-user" in ids
        assert "users/create-user" in ids
        assert "posts/create-post" in ids
        assert "posts/list-posts" in ids

    def test_scan_handles_nested_directories(
        self, bru_parser, yaml_parser, sample_collection_dir
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        user_requests = [r for r in results if r.id.startswith("users/")]
        post_requests = [r for r in results if r.id.startswith("posts/")]
        assert "users/get-user" in [r.id for r in user_requests]
        assert "users/create-user" in [r.id for r in user_requests]
        assert "posts/create-post" in [r.id for r in post_requests]
        assert "posts/list-posts" in [r.id for r in post_requests]

    @patch("bruno_mcp.scanners.collection_scanner.Path.rglob")
    def test_scan_invalid_bru_file(self, mock_rglob, bru_parser, yaml_parser, sample_collection_dir):
        valid_file = Mock(spec=Path)
        valid_file.stat.return_value = Mock(st_size=1024)
        valid_file.relative_to.return_value = Path("valid.bru")
        valid_file.with_suffix.return_value = Path("valid")
        invalid_file = Mock(spec=Path)
        invalid_file.stat.return_value = Mock(st_size=1024)
        mock_rglob.return_value = [valid_file, invalid_file]
        mock_bru_parser = Mock(spec=BruParser)
        mock_bru_parser.parse_file.side_effect = [
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

        scanner = CollectionScanner(mock_bru_parser, yaml_parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        assert len(results) == 1
        assert results[0].name == "Valid Request"

    @patch("bruno_mcp.scanners.collection_scanner.Path.exists")
    def test_scan_rejects_directory_without_bruno_json(
        self, mock_exists, bru_parser, yaml_parser, sample_collection_dir
    ):
        mock_exists.return_value = False
        scanner = CollectionScanner(bru_parser, yaml_parser)

        with pytest.raises(ValueError, match="Not a valid Bruno collection"):
            scanner.scan_collection_for_format(sample_collection_dir)

    @patch("bruno_mcp.scanners.collection_scanner.Path.rglob")
    def test_scan_enforces_max_file_limit(
        self, mock_rglob, bru_parser, yaml_parser, sample_collection_dir
    ):
        fake_files = [Path(f"request_{i}.bru") for i in range(1001)]
        mock_rglob.return_value = fake_files
        scanner = CollectionScanner(bru_parser, yaml_parser)

        with pytest.raises(ValueError, match="Collection too large"):
            scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

    @patch("bruno_mcp.scanners.collection_scanner.Path.rglob")
    def test_scan_skips_oversized_files(
        self, mock_rglob, bru_parser, yaml_parser, sample_collection_dir
    ):
        normal_file = Mock(spec=Path)
        normal_file.stat.return_value = Mock(st_size=1024)
        normal_file.relative_to.return_value = Path("normal.bru")
        normal_file.with_suffix.return_value = Path("normal")
        huge_file = Mock(spec=Path)
        huge_file.stat.return_value = Mock(st_size=11 * 1024 * 1024)
        mock_rglob.return_value = [normal_file, huge_file]
        mock_bru_parser = Mock(spec=BruParser)
        mock_bru_parser.parse_file.return_value = BruRequest(
            filepath="normal.bru",
            meta={"name": "Normal Request"},
            method="GET",
            url="https://example.com",
            headers={},
            params={},
            body=None,
            auth=None,
        )

        scanner = CollectionScanner(mock_bru_parser, yaml_parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        assert len(results) == 1
        assert results[0].name == "Normal Request"

    def test_collection_scanner_extracts_variable_names_from_request(
        self, bru_parser, yaml_parser, sample_collection_dir
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        get_user = next(r for r in results if r.id == "users/get-user")
        assert set(get_user.variable_names) == {"userId", "authToken"}
        body_var_request = next(r for r in results if r.id == "posts/request-with-body-var")
        assert "postId" in body_var_request.variable_names

    def test_collection_scanner_excludes_process_env_from_variable_names(
        self, bru_parser, yaml_parser, sample_collection_dir
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)

        results = scanner.scan_collection_for_requests(bru_collection_info(sample_collection_dir))

        process_env_request = next(r for r in results if r.id == "posts/request-with-process-env")
        assert "resourceId" in process_env_request.variable_names
        assert "process.env.API_KEY" not in process_env_request.variable_names
        assert "API_KEY" not in process_env_request.variable_names


class TestCollectionScannerYamlRequests:
    """Test collection scanning of OpenCollection YAML request files."""
    def test_scan_extracts_request_metadata_for_yaml_collection(
        self, bru_parser, yaml_parser, opencollection_collection
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)
        info = yaml_collection_info(opencollection_collection)

        results = scanner.scan_collection_for_requests(info)

        ids = {r.id for r in results}
        assert "users/get-user" in ids
        assert "users/create-user" in ids
        assert "users/folder" not in ids
        assert not any(r.id.startswith("environments/") for r in results)
        get_user = next(r for r in results if r.id == "users/get-user")
        assert get_user.name == "Get User"
        assert get_user.method == "GET"
        assert get_user.url == "https://api.example.com/users/{{userId}}"
        assert get_user.file_path == "users/get-user.yml"

    def test_scan_extracts_variable_names_from_yaml_requests(
        self, bru_parser, yaml_parser, opencollection_collection
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)
        info = yaml_collection_info(opencollection_collection)

        results = scanner.scan_collection_for_requests(info)

        get_user = next(r for r in results if r.id == "users/get-user")
        assert set(get_user.variable_names) == {"userId", "authToken"}
        create_user = next(r for r in results if r.id == "users/create-user")
        assert "displayName" in create_user.variable_names

    def test_scan_picks_up_full_yaml_extension_name_request_files(
        self, bru_parser, yaml_parser, opencollection_collection
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)
        info = yaml_collection_info(opencollection_collection)

        results = scanner.scan_collection_for_requests(info)

        ping = next(r for r in results if r.id == "users/get-ping")
        assert ping.name == "Get Ping"
        assert ping.file_path == "users/get-ping.yaml"


class TestScanCollectionForFormat:
    """Tests for collection root detection."""

    def test_scan_for_format_returns_bru_for_bru_collection(
        self, bru_parser, yaml_parser, sample_collection_dir
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)

        assert scanner.scan_collection_for_format(sample_collection_dir) == CollectionFormat.BRU

    def test_scan_for_format_returns_opencollection(
        self, bru_parser, yaml_parser, opencollection_root: Path
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)
        root = opencollection_root.resolve()

        assert scanner.scan_collection_for_format(root) == CollectionFormat.OPENCOLLECTION

    def test_scan_for_format_returns_opencollection_when_both_markers_present(
        self, bru_parser, yaml_parser, mixed_collection_markers: Path
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)
        root = mixed_collection_markers.resolve()

        assert scanner.scan_collection_for_format(root) == CollectionFormat.OPENCOLLECTION

    def test_scan_for_requests_returns_empty_for_empty_opencollection_root(
        self, bru_parser, yaml_parser, opencollection_root: Path
    ):
        scanner = CollectionScanner(bru_parser, yaml_parser)
        root = opencollection_root.resolve()

        assert scanner.scan_collection_for_requests(yaml_collection_info(root)) == []


class TestRequestMetadata:
    """Test RequestMetadata model."""

    def test_request_metadata_model(self):
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
