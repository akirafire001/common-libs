from typing import Any

from flask import Flask, jsonify


class AppError(Exception):
    """COMMON-LIBS 全例外の基底クラス。"""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class ValidationError(AppError):
    status_code = 422
    error_code = "validation_error"


class AuthorizationError(AppError):
    status_code = 403
    error_code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    error_code = "conflict"


class ExternalServiceError(AppError):
    """Stripe / S3 などの外部サービス呼び出し失敗。"""

    status_code = 502
    error_code = "external_service_error"


def init_error_handlers(app: Flask) -> None:
    """Flask アプリに共通エラーハンドラを登録する。

    app = Flask(__name__)
    init_error_handlers(app)
    """

    @app.errorhandler(AppError)
    def handle_app_error(e: AppError):
        return jsonify(e.to_dict()), e.status_code

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({"error": "not_found", "message": "Resource not found."}), 404

    @app.errorhandler(405)
    def handle_405(e):
        return jsonify({"error": "method_not_allowed", "message": "Method not allowed."}), 405

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({"error": "internal_error", "message": "An unexpected error occurred."}), 500
