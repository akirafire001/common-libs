import pytest
from unittest.mock import MagicMock, patch

import stripe  # noqa: F401 – stripe.error.* はモジュール属性経由でアクセス

from common.payment.subscription import SubscriptionClient, SubscriptionResult


# Stripe が返す dict 形式のレスポンスモック
def _make_sub(sub_id="sub_123", status="active", period_end=9999999999):
    return {
        "id": sub_id,
        "status": status,
        "current_period_end": period_end,
        "items": {"data": [{"id": "si_abc"}]},
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    return SubscriptionClient()


class TestSubscriptionClientCreate:
    def test_create_success(self, client):
        mock_sub = _make_sub()
        with patch("stripe.Subscription.create", return_value=mock_sub):
            result = client.create("cus_123", "price_abc")

        assert result.success is True
        assert result.subscription_id == "sub_123"
        assert result.status == "active"
        assert result.current_period_end == 9999999999
        assert result.error is None

    def test_create_with_trial_days(self, client):
        mock_sub = _make_sub(status="trialing")
        with patch("stripe.Subscription.create", return_value=mock_sub) as mock_create:
            result = client.create("cus_123", "price_abc", trial_days=14)

        assert result.success is True
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["trial_period_days"] == 14

    def test_create_without_trial_omits_param(self, client):
        mock_sub = _make_sub()
        with patch("stripe.Subscription.create", return_value=mock_sub) as mock_create:
            client.create("cus_123", "price_abc", trial_days=0)

        call_kwargs = mock_create.call_args[1]
        assert "trial_period_days" not in call_kwargs

    def test_create_stripe_error(self, client):
        with patch("stripe.Subscription.create",
                   side_effect=stripe.error.StripeError("network error")):
            result = client.create("cus_123", "price_abc")

        assert result.success is False
        assert "network error" in result.error
        assert result.subscription_id is None


class TestSubscriptionClientCancel:
    def test_cancel_success(self, client):
        mock_sub = _make_sub(status="canceled")
        with patch("stripe.Subscription.delete", return_value=mock_sub):
            result = client.cancel("sub_123")

        assert result.success is True
        assert result.subscription_id == "sub_123"
        assert result.status == "canceled"

    def test_cancel_stripe_error(self, client):
        with patch("stripe.Subscription.delete",
                   side_effect=stripe.error.StripeError("not found")):
            result = client.cancel("sub_123")

        assert result.success is False
        assert result.error is not None


class TestSubscriptionClientUpgrade:
    def test_upgrade_success(self, client):
        original_sub = _make_sub()
        upgraded_sub = _make_sub(status="active", period_end=1111111111)

        with patch("stripe.Subscription.retrieve", return_value=original_sub), \
             patch("stripe.Subscription.modify", return_value=upgraded_sub) as mock_modify:
            result = client.upgrade("sub_123", "price_pro")

        assert result.success is True
        assert result.status == "active"

        # proration_behavior が正しく渡されていることを確認
        call_kwargs = mock_modify.call_args[1]
        assert call_kwargs["proration_behavior"] == "always_invoice"
        assert call_kwargs["items"][0]["price"] == "price_pro"
        assert call_kwargs["items"][0]["id"] == "si_abc"

    def test_upgrade_stripe_error(self, client):
        original_sub = _make_sub()
        with patch("stripe.Subscription.retrieve", return_value=original_sub), \
             patch("stripe.Subscription.modify",
                   side_effect=stripe.error.StripeError("card declined")):
            result = client.upgrade("sub_123", "price_pro")

        assert result.success is False
        assert result.error is not None


class TestSubscriptionClientRetrieve:
    def test_retrieve_success(self, client):
        mock_sub = _make_sub()
        with patch("stripe.Subscription.retrieve", return_value=mock_sub):
            result = client.retrieve("sub_123")

        assert result.success is True
        assert result.subscription_id == "sub_123"
        assert result.status == "active"
        assert result.current_period_end == 9999999999

    def test_retrieve_stripe_error(self, client):
        with patch("stripe.Subscription.retrieve",
                   side_effect=stripe.error.StripeError("subscription not found")):
            result = client.retrieve("sub_xyz")

        assert result.success is False
        assert result.error is not None

    def test_result_dataclass_fields(self):
        r = SubscriptionResult(success=True)
        assert r.subscription_id is None
        assert r.status is None
        assert r.current_period_end is None
        assert r.error is None
