import json
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredLogger:
    """JSON形式で構造化ログを出力するロガー。

    各ログエントリには timestamp, level, service, message と
    呼び出し時に渡した任意の追加フィールドが含まれる。
    """

    def __init__(self, service: str) -> None:
        """
        Args:
            service: ログに付与するサービス名（例: "auth-api"）
        """
        self.service = service

    def _emit(self, level: str, message: str, **fields: Any) -> None:
        """ログエントリをJSON形式でstdoutに書き出す。"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "service": self.service,
            "message": message,
            **fields,
        }
        print(json.dumps(entry, ensure_ascii=False), file=sys.stdout, flush=True)

    def info(self, message: str, **fields: Any) -> None:
        """INFOレベルのログを出力する。"""
        self._emit("INFO", message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        """ERRORレベルのログを出力する。"""
        self._emit("ERROR", message, **fields)

    def warn(self, message: str, **fields: Any) -> None:
        """WARNレベルのログを出力する。"""
        self._emit("WARN", message, **fields)
