import os
from collections.abc import Callable
from typing import Any

import stripe
from flask import Blueprint, jsonify, request

EventType = str
HandlerFunc = Callable[[dict[str, Any]], None]


class StripeWebhookBlueprint:
    """Stripe Webhook イベントを受け取る Flask Blueprint ファクトリ。

    使用例:
        from common.payment.webhook import StripeWebhookBlueprint

        webhook = StripeWebhookBlueprint()

        @webhook.on("invoice.payment_failed")
        def handle_payment_failed(event_data):
            sub_id = event_data["subscription"]
            ...

        app.register_blueprint(webhook.blueprint)
    """

    def __init__(
        self,
        endpoint: str = "/webhook/stripe",
        webhook_secret_env: str = "STRIPE_WEBHOOK_SECRET",
    ) -> None:
        self._secret_env = webhook_secret_env
        self._handlers: dict[EventType, list[HandlerFunc]] = {}
        self.blueprint = Blueprint("stripe_webhook", __name__)
        self.blueprint.add_url_rule(
            endpoint, view_func=self._handle_request, methods=["POST"]
        )

    def on(self, event_type: EventType) -> Callable[[HandlerFunc], HandlerFunc]:
        """イベントハンドラを登録するデコレータ。

        @webhook.on("invoice.payment_failed")
        def handler(event_data: dict): ...
        """
        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._handlers.setdefault(event_type, []).append(func)
            return func
        return decorator

    def _handle_request(self) -> Any:
        payload = request.get_data()
        sig_header = request.headers.get("Stripe-Signature", "")
        secret = os.environ.get(self._secret_env, "")

        # シークレット未設定のまま本番リクエストを受け付けないようにする
        if not secret:
            import logging
            logging.getLogger(__name__).error(
                "Stripe webhook secret is not set (env: %s). "
                "All webhook requests will be rejected.",
                self._secret_env,
            )
            return jsonify({"error": "Webhook not configured"}), 500

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, secret)
        except ValueError:
            return jsonify({"error": "Invalid payload"}), 400
        except stripe.error.SignatureVerificationError:
            return jsonify({"error": "Invalid signature"}), 400

        handlers = self._handlers.get(event["type"], [])
        for handler in handlers:
            handler(event["data"]["object"])

        return jsonify({"received": True}), 200
