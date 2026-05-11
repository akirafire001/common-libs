import pytest
from unittest.mock import MagicMock, patch, call

import stripe  # noqa: F401

from flask import Flask
from common.payment.webhook import StripeWebhookBlueprint


def _make_app(webhook: StripeWebhookBlueprint) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(webhook.blueprint)
    return app


def _post(client, payload=b'{"id":"evt_1"}', sig="test_sig"):
    return client.post(
        "/webhook/stripe",
        data=payload,
        headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
    )


class TestStripeWebhookBlueprint:
    def test_valid_event_returns_200(self, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        webhook = StripeWebhookBlueprint()
        app = _make_app(webhook)

        mock_event = {"type": "invoice.payment_succeeded", "data": {"object": {}}}
        with app.test_client() as c:
            with patch("stripe.Webhook.construct_event", return_value=mock_event):
                resp = _post(c)

        assert resp.status_code == 200
        assert resp.get_json() == {"received": True}

    def test_invalid_payload_returns_400(self, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        webhook = StripeWebhookBlueprint()
        app = _make_app(webhook)

        with app.test_client() as c:
            with patch("stripe.Webhook.construct_event", side_effect=ValueError("bad json")):
                resp = _post(c)

        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Invalid payload"

    def test_invalid_signature_returns_400(self, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        webhook = StripeWebhookBlueprint()
        app = _make_app(webhook)

        with app.test_client() as c:
            with patch(
                "stripe.Webhook.construct_event",
                side_effect=stripe.error.SignatureVerificationError("bad sig", "hdr"),
            ):
                resp = _post(c)

        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Invalid signature"

    def test_registered_handler_is_called(self, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        webhook = StripeWebhookBlueprint()

        received = []

        @webhook.on("invoice.payment_failed")
        def handle_failed(data):
            received.append(data)

        app = _make_app(webhook)
        event_data = {"subscription": "sub_abc", "amount_due": 5000}
        mock_event = {"type": "invoice.payment_failed", "data": {"object": event_data}}

        with app.test_client() as c:
            with patch("stripe.Webhook.construct_event", return_value=mock_event):
                _post(c)

        assert len(received) == 1
        assert received[0] == event_data

    def test_multiple_handlers_all_called(self, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        webhook = StripeWebhookBlueprint()

        calls = []

        @webhook.on("customer.subscription.deleted")
        def handler_a(data):
            calls.append("a")

        @webhook.on("customer.subscription.deleted")
        def handler_b(data):
            calls.append("b")

        app = _make_app(webhook)
        mock_event = {
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_123"}},
        }

        with app.test_client() as c:
            with patch("stripe.Webhook.construct_event", return_value=mock_event):
                _post(c)

        assert calls == ["a", "b"]

    def test_unknown_event_type_returns_200_without_handler(self, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        webhook = StripeWebhookBlueprint()
        app = _make_app(webhook)

        mock_event = {"type": "charge.refunded", "data": {"object": {}}}

        with app.test_client() as c:
            with patch("stripe.Webhook.construct_event", return_value=mock_event):
                resp = _post(c)

        assert resp.status_code == 200

    def test_custom_endpoint(self, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        webhook = StripeWebhookBlueprint(endpoint="/api/hooks/stripe")
        app = _make_app(webhook)

        mock_event = {"type": "ping", "data": {"object": {}}}

        with app.test_client() as c:
            with patch("stripe.Webhook.construct_event", return_value=mock_event):
                resp = c.post(
                    "/api/hooks/stripe",
                    data=b"{}",
                    headers={"Stripe-Signature": "sig"},
                )

        assert resp.status_code == 200

    def test_on_decorator_returns_original_function(self, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        webhook = StripeWebhookBlueprint()

        @webhook.on("test.event")
        def my_handler(data):
            return "handled"

        # デコレータは元の関数をそのまま返す
        assert my_handler({"x": 1}) == "handled"

    def test_missing_secret_returns_500(self, monkeypatch):
        """Webhook シークレットが未設定のとき 500 を返し、リクエストを通過させない。"""
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        webhook = StripeWebhookBlueprint()
        app = _make_app(webhook)

        with app.test_client() as c:
            resp = _post(c)

        assert resp.status_code == 500
        assert resp.get_json()["error"] == "Webhook not configured"
