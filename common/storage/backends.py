import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StorageResult:
    """ストレージ操作の結果を表すデータクラス。"""

    success: bool
    path: str | None = None   # S3 key またはローカルパス
    url: str | None = None    # 公開 URL（S3 presigned URL またはローカルファイルパス）
    error: str | None = None


class StorageBackend(ABC):
    """ストレージバックエンドの抽象基底クラス。"""

    @abstractmethod
    def upload(self, local_path: str, destination: str) -> StorageResult: ...

    @abstractmethod
    def download(self, source: str, local_path: str) -> StorageResult: ...

    @abstractmethod
    def delete(self, path: str) -> StorageResult: ...

    @abstractmethod
    def get_url(self, path: str, expires_in: int = 3600) -> StorageResult: ...


class LocalStorage(StorageBackend):
    """ローカルファイルシステムへの保存。開発・テスト用途。"""

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _safe_resolve(self, path: str) -> Path | None:
        """path がベースディレクトリ外を指していないか検証する。

        ../../etc/passwd のようなパストラバーサルを防ぐ。
        ベース外を指す場合は None を返す。
        """
        resolved = (self._base / path).resolve()
        if not resolved.is_relative_to(self._base):
            return None
        return resolved

    def upload(self, local_path: str, destination: str) -> StorageResult:
        dest = self._safe_resolve(destination)
        if dest is None:
            return StorageResult(success=False, error=f"Invalid path: '{destination}'")
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_path, dest)
            return StorageResult(success=True, path=destination, url=str(dest))
        except OSError as e:
            return StorageResult(success=False, error=str(e))

    def download(self, source: str, local_path: str) -> StorageResult:
        src = self._safe_resolve(source)
        if src is None:
            return StorageResult(success=False, error=f"Invalid path: '{source}'")
        # local_path は呼び出し元が信頼できるパスを渡す責任を持つ。
        # 未検証のユーザー入力をそのまま渡してはならない。
        try:
            shutil.copy2(src, local_path)
            return StorageResult(success=True, path=local_path)
        except OSError as e:
            return StorageResult(success=False, error=str(e))

    def delete(self, path: str) -> StorageResult:
        target = self._safe_resolve(path)
        if target is None:
            return StorageResult(success=False, error=f"Invalid path: '{path}'")
        try:
            target.unlink()
            return StorageResult(success=True, path=path)
        except OSError as e:
            return StorageResult(success=False, error=str(e))

    def get_url(self, path: str, expires_in: int = 3600) -> StorageResult:
        resolved = self._safe_resolve(path)
        if resolved is None:
            return StorageResult(success=False, error=f"Invalid path: '{path}'")
        return StorageResult(success=True, path=path, url=str(resolved))


class S3Storage(StorageBackend):
    """AWS S3 へのストレージ。本番用途。"""

    def __init__(self, bucket: str | None = None, region: str | None = None) -> None:
        import boto3
        self._bucket = bucket or os.environ["AWS_S3_BUCKET"]
        self._region = region or os.environ.get("AWS_REGION", "ap-northeast-1")
        self._client = boto3.client("s3", region_name=self._region)

    @staticmethod
    def _validate_key(key: str) -> bool:
        """S3 キーの基本安全チェック。

        以下を拒否する:
        - ディレクトリトラバーサル成分 (..)
        - ヌルバイト
        - 先頭スラッシュ（絶対パス的な指定）
        これにより、他ツールがキーをパスとして解釈した際のトラバーサルを防ぐ。
        """
        if not key:
            return False
        if "\x00" in key:
            return False
        if key.startswith("/"):
            return False
        parts = key.replace("\\", "/").split("/")
        if ".." in parts:
            return False
        return True

    def upload(self, local_path: str, destination: str) -> StorageResult:
        if not self._validate_key(destination):
            return StorageResult(success=False, error=f"Invalid S3 key: '{destination}'")
        try:
            self._client.upload_file(local_path, self._bucket, destination)
            return StorageResult(success=True, path=destination)
        except Exception as e:
            return StorageResult(success=False, error=str(e))

    def download(self, source: str, local_path: str) -> StorageResult:
        if not self._validate_key(source):
            return StorageResult(success=False, error=f"Invalid S3 key: '{source}'")
        try:
            self._client.download_file(self._bucket, source, local_path)
            return StorageResult(success=True, path=local_path)
        except Exception as e:
            return StorageResult(success=False, error=str(e))

    def delete(self, path: str) -> StorageResult:
        if not self._validate_key(path):
            return StorageResult(success=False, error=f"Invalid S3 key: '{path}'")
        try:
            self._client.delete_object(Bucket=self._bucket, Key=path)
            return StorageResult(success=True, path=path)
        except Exception as e:
            return StorageResult(success=False, error=str(e))

    def get_url(self, path: str, expires_in: int = 3600) -> StorageResult:
        if not self._validate_key(path):
            return StorageResult(success=False, error=f"Invalid S3 key: '{path}'")
        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": path},
                ExpiresIn=expires_in,
            )
            return StorageResult(success=True, path=path, url=url)
        except Exception as e:
            return StorageResult(success=False, error=str(e))


def create_storage(backend: str | None = None, **kwargs) -> StorageBackend:
    """環境変数またはパラメータからストレージバックエンドを生成するファクトリ。

    STORAGE_BACKEND=s3    → S3Storage
    STORAGE_BACKEND=local → LocalStorage（デフォルト）
    """
    backend = backend or os.environ.get("STORAGE_BACKEND", "local")
    if backend == "s3":
        return S3Storage(**kwargs)
    base_dir = kwargs.get("base_dir", os.environ.get("LOCAL_STORAGE_DIR", "/tmp/uploads"))
    return LocalStorage(base_dir=base_dir)
