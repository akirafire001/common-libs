import pytest
from flask import Flask

from common.errors import (
    AppError,
    AuthorizationError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
    init_error_handlers,
)


class TestAppError:
    def test_inherits_from_exception(self):
        assert issubclass(AppError, Exception)

    def test_default_codes(self):
        e = AppError("oops")
        assert e.status_code == 500
        assert e.error_code == "internal_error"

    def test_message_stored(self):
        e = AppError("something failed")
        assert e.message == "something failed"
        assert str(e) == "something failed"

    def test_to_dict_no_details(self):
        e = AppError("oops")
        d = e.to_dict()
        assert d == {"error": "internal_error", "message": "oops"}

    def test_to_dict_with_details(self):
        e = ValidationError("bad input", {"field": "email"})
        d = e.to_dict()
        assert d["error"] == "validation_error"
        assert d["message"] == "bad input"
        assert d["details"] == {"field": "email"}

    def test_empty_details_not_in_dict(self):
        e = AppError("oops", {})
        d = e.to_dict()
        assert "details" not in d

    def test_none_details_defaults_to_empty(self):
        e = AppError("oops", None)
        assert e.details == {}


class TestErrorSubclasses:
    @pytest.mark.parametrize("cls,code,status", [
        (NotFoundError,       "not_found",             404),
        (ValidationError,     "validation_error",      422),
        (AuthorizationError,  "forbidden",              403),
        (ConflictError,       "conflict",               409),
        (ExternalServiceError,"external_service_error", 502),
    ])
    def test_codes(self, cls, code, status):
        e = cls("msg")
        assert e.error_code == code
        assert e.status_code == status

    def test_subclasses_are_app_errors(self):
        for cls in [NotFoundError, ValidationError, AuthorizationError,
                    ConflictError, ExternalServiceError]:
            assert issubclass(cls, AppError)


class TestInitErrorHandlers:
    @pytest.fixture
    def app(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        init_error_handlers(app)

        @app.route("/not-found")
        def raise_not_found():
            raise NotFoundError("User not found.", {"id": "42"})

        @app.route("/validation")
        def raise_validation():
            raise ValidationError("Email required.")

        @app.route("/external")
        def raise_external():
            raise ExternalServiceError("Stripe timeout.")

        @app.route("/get-only", methods=["GET"])
        def get_only():
            return "ok"

        return app

    def test_app_error_returns_json_with_status(self, app):
        with app.test_client() as c:
            resp = c.get("/not-found")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "not_found"
        assert data["message"] == "User not found."
        assert data["details"] == {"id": "42"}

    def test_validation_error(self, app):
        with app.test_client() as c:
            resp = c.get("/validation")
        assert resp.status_code == 422
        assert resp.get_json()["error"] == "validation_error"

    def test_external_service_error(self, app):
        with app.test_client() as c:
            resp = c.get("/external")
        assert resp.status_code == 502
        assert resp.get_json()["error"] == "external_service_error"

    def test_404_returns_json(self, app):
        with app.test_client() as c:
            resp = c.get("/no-such-route")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "not_found"
        assert "Resource not found" in data["message"]

    def test_405_returns_json(self, app):
        with app.test_client() as c:
            resp = c.post("/get-only")
        assert resp.status_code == 405
        data = resp.get_json()
        assert data["error"] == "method_not_allowed"
