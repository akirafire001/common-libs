import os
from dataclasses import dataclass

import stripe


@dataclass
class PaymentResult:
    """決済処理の結果を表すデータクラス。"""
    success: bool
    payment_intent_id: str | None
    error: str | None


class StripeClient:
    """Stripe APIを使った決済処理クライアント。

    環境変数 STRIPE_SECRET_KEY にAPIキーを設定して使用する。
    """

    def __init__(self, api_key: str | None = None) -> None:
        """
        Args:
            api_key: StripeのAPIキー。省略時は環境変数 STRIPE_SECRET_KEY を使用。
        """
        stripe.api_key = api_key or os.environ.get("STRIPE_SECRET_KEY", "")

    def charge(
        self,
        amount: int,
        currency: str,
        payment_method_id: str,
    ) -> PaymentResult:
        """PaymentIntentを作成して決済を実行する。

        Args:
            amount: 決済金額（最小通貨単位、例: 円なら 1000 = ¥1,000）
            currency: 通貨コード（例: "jpy", "usd"）
            payment_method_id: StripeのPaymentMethod ID

        Returns:
            PaymentResult（成功時は payment_intent_id 入り、失敗時は error 入り）
        """
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                payment_method=payment_method_id,
                confirm=True,
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            )
            return PaymentResult(
                success=True,
                payment_intent_id=intent.id,
                error=None,
            )
        except stripe.error.CardError as e:
            # カード拒否など、カード固有のエラー
            return PaymentResult(
                success=False,
                payment_intent_id=None,
                error=f"CardError: {e.user_message}",
            )
        except stripe.error.StripeError as e:
            # その他のStripe APIエラー
            return PaymentResult(
                success=False,
                payment_intent_id=None,
                error=f"StripeError: {e}",
            )
