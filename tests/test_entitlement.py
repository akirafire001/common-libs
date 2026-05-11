import pytest
from flask import Flask, g, jsonify

import common.entitlement.plans as plans_module
from common.entitlement import PLAN_LEVELS, has_plan, require_plan, set_plan_loader


@pytest.fixture(autouse=True)
def reset_plan_loader():
    """各テスト後に plan_loader をデフォルトに戻す。"""
    original = plans_module._plan_loader
    yield
    plans_module._plan_loader = original


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/open")
    def open_route():
        return jsonify({"ok": True})

    @app.route("/pro")
    @require_plan("pro")
    def pro_route():
        return jsonify({"ok": True})

    @app.route("/enterprise")
    @require_plan("enterprise")
    def enterprise_route():
        return jsonify({"ok": True})

    @app.route("/starter")
    @require_plan("starter")
    def starter_route():
        return jsonify({"ok": True})

    return app


class TestPlanLevels:
    def test_all_plans_defined(self):
        assert set(PLAN_LEVELS.keys()) == {"free", "starter", "pro", "enterprise"}

    def test_hierarchy_order(self):
        assert PLAN_LEVELS["free"] < PLAN_LEVELS["starter"]
        assert PLAN_LEVELS["starter"] < PLAN_LEVELS["pro"]
        assert PLAN_LEVELS["pro"] < PLAN_LEVELS["enterprise"]

    def test_free_is_zero(self):
        assert PLAN_LEVELS["free"] == 0


class TestRequirePlanUnknownPlan:
    def test_unknown_plan_raises_at_decoration_time(self):
        """存在しないプラン名はデコレート時に ValueError を送出する。
        リクエスト時に誤って通過させてはいけない。
        """
        with pytest.raises(ValueError, match="Unknown plan"):
            @require_plan("superadmin")
            def dummy():
                pass

    def test_typo_plan_raises(self):
        with pytest.raises(ValueError):
            @require_plan("Pro")  # 大文字ミス
            def dummy():
                pass


class TestRequirePlan:
    def test_exact_plan_allowed(self, app):
        set_plan_loader(lambda: "pro")
        with app.test_client() as c:
            resp = c.get("/pro")
        assert resp.status_code == 200

    def test_higher_plan_allowed(self, app):
        set_plan_loader(lambda: "enterprise")
        with app.test_client() as c:
            resp = c.get("/pro")
        assert resp.status_code == 200

    def test_lower_plan_denied(self, app):
        set_plan_loader(lambda: "free")
        with app.test_client() as c:
            resp = c.get("/pro")
        assert resp.status_code == 403

    def test_403_response_body(self, app):
        set_plan_loader(lambda: "free")
        with app.test_client() as c:
            resp = c.get("/pro")
        data = resp.get_json()
        assert data["error"] == "plan_required"
        assert data["required_plan"] == "pro"
        assert data["current_plan"] == "free"
        assert "pro" in data["message"]

    def test_starter_denied_on_enterprise(self, app):
        set_plan_loader(lambda: "starter")
        with app.test_client() as c:
            resp = c.get("/enterprise")
        assert resp.status_code == 403

    def test_free_allowed_on_open_route(self, app):
        set_plan_loader(lambda: "free")
        with app.test_client() as c:
            resp = c.get("/open")
        assert resp.status_code == 200

    def test_free_allowed_on_starter_route(self, app):
        set_plan_loader(lambda: "starter")
        with app.test_client() as c:
            resp = c.get("/starter")
        assert resp.status_code == 200


class TestHasPlan:
    def test_exact_plan_returns_true(self, app):
        set_plan_loader(lambda: "pro")
        with app.test_request_context("/"):
            assert has_plan("pro") is True

    def test_higher_plan_returns_true(self, app):
        set_plan_loader(lambda: "enterprise")
        with app.test_request_context("/"):
            assert has_plan("pro") is True

    def test_lower_plan_returns_false(self, app):
        set_plan_loader(lambda: "free")
        with app.test_request_context("/"):
            assert has_plan("pro") is False

    def test_free_plan_returns_true_for_free(self, app):
        set_plan_loader(lambda: "free")
        with app.test_request_context("/"):
            assert has_plan("free") is True


class TestSetPlanLoader:
    def test_custom_loader_is_used(self, app):
        set_plan_loader(lambda: "enterprise")
        with app.test_client() as c:
            resp = c.get("/enterprise")
        assert resp.status_code == 200

    def test_default_loader_reads_g(self, app):
        # デフォルトローダーは g.user_plan を参照する
        plans_module._plan_loader = plans_module._get_user_plan

        with app.test_request_context("/"):
            g.user_plan = "pro"
            assert plans_module._plan_loader() == "pro"

    def test_default_loader_falls_back_to_free(self, app):
        plans_module._plan_loader = plans_module._get_user_plan

        with app.test_request_context("/"):
            # g.user_plan が未設定 → "free" を返す
            assert plans_module._plan_loader() == "free"
