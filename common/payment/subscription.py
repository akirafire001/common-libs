import os
from dataclasses import dataclass
from typing import Any

import stripe


@dataclass
class SubscriptionResult:
    """サブスクリプション操作の結果を表すデータクラス。"""

    success: bool
    subscription_id: str | None = None
    status: str | None = None           # "active", "canceled", "past_due" 等
    current_period_end: int | None = None  # UNIX timestamp
    error: str | None = None


class SubscriptionClient:
    """Stripe Subscription API ラッパー。

    既存の StripeClient（PaymentIntent 向け）と同様に
    stripe.api_key をコンストラクタで設定する。
    """

    def __init__(self, api_key: str | None = None) -> None:
        stripe.api_key = api_key or os.environ.get("STRIPE_SECRET_KEY", "")

    def create(
        self,
        customer_id: str,
        price_id: str,
        trial_days: int = 0,
    ) -> SubscriptionResult:
        """プランを新規契約する。"""
        try:
            params: dict[str, Any] = {
                "customer": customer_id,
                "items": [{"price": price_id}],
            }
            if trial_days > 0:
                params["trial_period_days"] = trial_days
            sub = stripe.Subscription.create(**params)
            return SubscriptionResult(
                success=True,
                subscription_id=sub["id"],
                status=sub["status"],
                current_period_end=sub["current_period_end"],
            )
        except stripe.error.StripeError as e:
            return SubscriptionResult(success=False, error=str(e))

    def cancel(self, subscription_id: str) -> SubscriptionResult:
        """サブスクリプションを即時解約する。"""
        try:
            sub = stripe.Subscription.delete(subscription_id)
            return SubscriptionResult(
                success=True,
                subscription_id=sub["id"],
                status=sub["status"],
            )
        except stripe.error.StripeError as e:
            return SubscriptionResult(success=False, error=str(e))

    def upgrade(self, subscription_id: str, new_price_id: str) -> SubscriptionResult:
        """プランをアップグレード（または変更）する。

        既存の Subscription Item を新しい price_id に差し替える。
        proration_behavior='always_invoice' で即時差分請求。
        """
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            item_id = sub["items"]["data"][0]["id"]
            updated = stripe.Subscription.modify(
                subscription_id,
                items=[{"id": item_id, "price": new_price_id}],
                proration_behavior="always_invoice",
            )
            return SubscriptionResult(
                success=True,
                subscription_id=updated["id"],
                status=updated["status"],
                current_period_end=updated["current_period_end"],
            )
        except stripe.error.StripeError as e:
            return SubscriptionResult(success=False, error=str(e))

    def retrieve(self, subscription_id: str) -> SubscriptionResult:
        """サブスクリプション情報を取得する。"""
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            return SubscriptionResult(
                success=True,
                subscription_id=sub["id"],
                status=sub["status"],
                current_period_end=sub["current_period_end"],
            )
        except stripe.error.StripeError as e:
            return SubscriptionResult(success=False, error=str(e))
