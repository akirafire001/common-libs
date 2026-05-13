import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from common.storage import LocalStorage, StorageResult, create_storage


class TestLocalStorageUpload:
    def test_upload_creates_file(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        storage = LocalStorage(str(tmp_path / "store"))

        result = storage.upload(str(src), "uploads/src.txt")

        assert result.success is True
        assert result.path == "uploads/src.txt"
        assert Path(result.url).exists()

    def test_upload_creates_nested_dirs(self, tmp_path):
        src = tmp_path / "file.txt"
        src.write_text("data")
        storage = LocalStorage(str(tmp_path / "store"))

        result = storage.upload(str(src), "a/b/c/file.txt")

        assert result.success is True
        assert (tmp_path / "store" / "a" / "b" / "c" / "file.txt").exists()

    def test_upload_nonexistent_source_fails(self, tmp_path):
        storage = LocalStorage(str(tmp_path / "store"))
        result = storage.upload("/nonexistent/file.txt", "dest.txt")

        assert result.success is False
        assert result.error is not None


class TestLocalStorageDownload:
    def test_download_copies_file(self, tmp_path):
        store_dir = tmp_path / "store"
        (store_dir / "files").mkdir(parents=True)
        (store_dir / "files" / "data.txt").write_text("contents")
        storage = LocalStorage(str(store_dir))

        dest = tmp_path / "downloaded.txt"
        result = storage.download("files/data.txt", str(dest))

        assert result.success is True
        assert dest.read_text() == "contents"

    def test_download_missing_file_fails(self, tmp_path):
        storage = LocalStorage(str(tmp_path / "store"))
        result = storage.download("missing.txt", str(tmp_path / "out.txt"))

        assert result.success is False
        assert result.error is not None


class TestLocalStorageDelete:
    def test_delete_removes_file(self, tmp_path):
        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "todelete.txt").write_text("bye")
        storage = LocalStorage(str(store_dir))

        result = storage.delete("todelete.txt")

        assert result.success is True
        assert not (store_dir / "todelete.txt").exists()

    def test_delete_missing_file_fails(self, tmp_path):
        storage = LocalStorage(str(tmp_path / "store"))
        result = storage.delete("ghost.txt")

        assert result.success is False


class TestLocalStorageGetUrl:
    def test_get_url_returns_absolute_path(self, tmp_path):
        storage = LocalStorage(str(tmp_path / "store"))
        result = storage.get_url("avatars/user.png")

        assert result.success is True
        assert result.path == "avatars/user.png"
        assert "user.png" in result.url

    def test_get_url_ignores_expires_in(self, tmp_path):
        storage = LocalStorage(str(tmp_path / "store"))
        r1 = storage.get_url("file.txt", expires_in=60)
        r2 = storage.get_url("file.txt", expires_in=3600)
        assert r1.url == r2.url


class TestLocalStoragePathTraversal:
    """パストラバーサル攻撃への耐性を検証する。"""

    def test_upload_traversal_rejected(self, tmp_path):
        storage = LocalStorage(str(tmp_path / "store"))
        result = storage.upload(str(tmp_path / "src.txt"), "../../etc/passwd")
        assert result.success is False
        assert "Invalid path" in result.error

    def test_download_traversal_rejected(self, tmp_path):
        storage = LocalStorage(str(tmp_path / "store"))
        result = storage.download("../../sensitive.txt", str(tmp_path / "out.txt"))
        assert result.success is False
        assert "Invalid path" in result.error

    def test_delete_traversal_rejected(self, tmp_path):
        storage = LocalStorage(str(tmp_path / "store"))
        result = storage.delete("../../important.txt")
        assert result.success is False
        assert "Invalid path" in result.error

    def test_get_url_traversal_rejected(self, tmp_path):
        storage = LocalStorage(str(tmp_path / "store"))
        result = storage.get_url("../secret.txt")
        assert result.success is False
        assert "Invalid path" in result.error

    def test_normal_nested_path_allowed(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("ok")
        storage = LocalStorage(str(tmp_path / "store"))
        result = storage.upload(str(src), "a/b/c.txt")
        assert result.success is True


class TestS3Storage:
    @pytest.fixture
    def mock_boto3(self):
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_module.client.return_value = mock_client
        return mock_module, mock_client

    def _make_s3(self, mock_boto3_module):
        with patch.dict(sys.modules, {"boto3": mock_boto3_module}):
            from common.storage.backends import S3Storage
            return S3Storage(bucket="test-bucket", region="ap-northeast-1")

    def test_upload_calls_boto3(self, mock_boto3):
        mock_module, mock_client = mock_boto3
        storage = self._make_s3(mock_module)

        result = storage.upload("/tmp/file.txt", "uploads/file.txt")

        assert result.success is True
        assert result.path == "uploads/file.txt"
        mock_client.upload_file.assert_called_once_with(
            "/tmp/file.txt", "test-bucket", "uploads/file.txt"
        )

    def test_upload_boto3_error(self, mock_boto3):
        mock_module, mock_client = mock_boto3
        mock_client.upload_file.side_effect = Exception("S3 unreachable")
        storage = self._make_s3(mock_module)

        result = storage.upload("/tmp/file.txt", "uploads/file.txt")

        assert result.success is False
        assert "S3 unreachable" in result.error

    def test_download_calls_boto3(self, mock_boto3):
        mock_module, mock_client = mock_boto3
        storage = self._make_s3(mock_module)

        result = storage.download("uploads/file.txt", "/tmp/out.txt")

        assert result.success is True
        mock_client.download_file.assert_called_once_with(
            "test-bucket", "uploads/file.txt", "/tmp/out.txt"
        )

    def test_delete_calls_boto3(self, mock_boto3):
        mock_module, mock_client = mock_boto3
        storage = self._make_s3(mock_module)

        result = storage.delete("uploads/file.txt")

        assert result.success is True
        mock_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="uploads/file.txt"
        )

    def test_get_url_returns_presigned_url(self, mock_boto3):
        mock_module, mock_client = mock_boto3
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/file?sig=abc"
        storage = self._make_s3(mock_module)

        result = storage.get_url("uploads/file.txt", expires_in=300)

        assert result.success is True
        assert result.url == "https://s3.example.com/file?sig=abc"
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "uploads/file.txt"},
            ExpiresIn=300,
        )

    def test_get_url_error(self, mock_boto3):
        mock_module, mock_client = mock_boto3
        mock_client.generate_presigned_url.side_effect = Exception("permission denied")
        storage = self._make_s3(mock_module)

        result = storage.get_url("file.txt")

        assert result.success is False
        assert "permission denied" in result.error


class TestS3KeyValidation:
    """S3 キーインジェクション対策を検証する。"""

    @pytest.fixture
    def s3(self):
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_module.client.return_value = mock_client
        with patch.dict(sys.modules, {"boto3": mock_module}):
            from common.storage.backends import S3Storage
            storage = S3Storage(bucket="test-bucket", region="ap-northeast-1")
        storage._client = mock_client
        return storage

    @pytest.mark.parametrize("bad_key", [
        "../secret.txt",
        "a/../../etc/passwd",
        "/absolute/path.txt",
        "null\x00byte.txt",
        "",
    ])
    def test_upload_invalid_key_rejected(self, s3, bad_key):
        result = s3.upload("/tmp/file.txt", bad_key)
        assert result.success is False
        assert "Invalid S3 key" in result.error

    @pytest.mark.parametrize("bad_key", [
        "../secret.txt",
        "../../admin/config",
        "/root/.ssh/authorized_keys",
    ])
    def test_download_invalid_key_rejected(self, s3, bad_key):
        result = s3.download(bad_key, "/tmp/out.txt")
        assert result.success is False

    def test_valid_nested_key_allowed(self, s3):
        s3._client.upload_file.return_value = None
        result = s3.upload("/tmp/file.txt", "uploads/2024/01/file.txt")
        assert result.success is True

    def test_delete_invalid_key_rejected(self, s3):
        result = s3.delete("../important.txt")
        assert result.success is False

    def test_get_url_invalid_key_rejected(self, s3):
        result = s3.get_url("../../admin.json")
        assert result.success is False


class TestCreateStorageFactory:
    def test_default_returns_local_storage(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path))
        storage = create_storage()
        assert isinstance(storage, LocalStorage)

    def test_explicit_local_returns_local_storage(self, tmp_path):
        storage = create_storage("local", base_dir=str(tmp_path))
        assert isinstance(storage, LocalStorage)

    def test_s3_returns_s3_storage(self):
        from common.storage.backends import S3Storage
        mock_boto3 = MagicMock()
        with patch.dict(sys.modules, {"boto3": mock_boto3}):
            storage = create_storage("s3", bucket="my-bucket")
        assert isinstance(storage, S3Storage)

    def test_storage_result_dataclass(self):
        r = StorageResult(success=True)
        assert r.path is None
        assert r.url is None
        assert r.error is None
