"""
tests/integration/test_external_services.py

NEXUS AI Trading System - External Services Integration Tests

This test suite verifies the integration with external services and APIs:
- Market Data Providers (Yahoo Finance, Alpha Vantage, Polygon)
- News and Sentiment APIs (NewsAPI, GDELT)
- Payment Gateways (Stripe, PayPal, Coinbase Commerce)
- Email Service (SendGrid, AWS SES)
- Webhook Delivery (incoming and outgoing)
- Cloud Storage (AWS S3, GCS)

All tests use mocked external API calls to ensure deterministic and fast
execution. The mocks simulate success and error scenarios.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import json
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, PropertyMock
from typing import Dict, Any, List, Optional
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.services.market_data import MarketDataService
from backend.services.sentiment import SentimentService
from backend.services.payment import PaymentService, PaymentProvider
from backend.services.email import EmailService
from backend.services.notification import NotificationService
from backend.services.storage import StorageService
from backend.services.webhook import WebhookService
from backend.models.user import User
from backend.models.subscription import SubscriptionPlan
from backend.models.payment_transaction import PaymentTransaction

from tests.integration.conftest import (
    db_session,
    client,
    test_user,
    test_user_token,
    auth_headers,
)


# ----- Fixtures -----

@pytest.fixture
def market_data_service() -> MarketDataService:
    """Return MarketDataService instance."""
    return MarketDataService()


@pytest.fixture
def sentiment_service() -> SentimentService:
    """Return SentimentService instance."""
    return SentimentService()


@pytest.fixture
def payment_service() -> PaymentService:
    """Return PaymentService instance."""
    return PaymentService()


@pytest.fixture
def email_service() -> EmailService:
    """Return EmailService instance."""
    return EmailService()


@pytest.fixture
def notification_service(db_session: Session) -> NotificationService:
    """Return NotificationService instance."""
    return NotificationService(db_session)


@pytest.fixture
def storage_service() -> StorageService:
    """Return StorageService instance."""
    return StorageService()


@pytest.fixture
def webhook_service() -> WebhookService:
    """Return WebhookService instance."""
    return WebhookService()


# ----- Market Data Service Tests -----

class TestMarketDataService:
    """Test market data integration."""

    def test_get_quote_success(self, market_data_service: MarketDataService):
        """Test successful quote fetch."""
        with patch('backend.services.market_data.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "symbol": "AAPL",
                "price": 150.25,
                "change": 1.25,
                "change_percent": 0.84,
                "volume": 5000000,
                "timestamp": datetime.utcnow().isoformat(),
            }
            mock_get.return_value = mock_response

            result = market_data_service.get_quote("AAPL")
            assert result["symbol"] == "AAPL"
            assert result["price"] == 150.25
            assert result["change"] == 1.25
            mock_get.assert_called_once()

    def test_get_quote_failure(self, market_data_service: MarketDataService):
        """Test quote fetch failure."""
        with patch('backend.services.market_data.requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            result = market_data_service.get_quote("AAPL")
            assert result is None

    def test_get_historical_data(self, market_data_service: MarketDataService):
        """Test fetching historical data."""
        with patch('backend.services.market_data.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [
                    {"timestamp": "2026-01-01", "open": 150, "close": 151},
                    {"timestamp": "2026-01-02", "open": 151, "close": 152},
                ]
            }
            mock_get.return_value = mock_response

            result = market_data_service.get_historical_data("AAPL", "1d", 30)
            assert len(result) == 2
            assert result[0]["close"] == 151

    def test_get_order_book(self, market_data_service: MarketDataService):
        """Test fetching order book."""
        with patch('backend.services.market_data.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "bids": [[150.0, 100], [149.5, 200]],
                "asks": [[151.0, 50], [151.5, 150]],
            }
            mock_get.return_value = mock_response

            result = market_data_service.get_order_book("AAPL")
            assert "bids" in result
            assert "asks" in result
            assert len(result["bids"]) == 2

    def test_get_historical_data_retry(self, market_data_service: MarketDataService):
        """Test retry logic for historical data (temporary failure)."""
        with patch('backend.services.market_data.requests.get') as mock_get:
            # Fail first call, succeed second
            mock_get.side_effect = [
                Exception("Timeout"),
                MagicMock(status_code=200, json=lambda: {"data": []}),
            ]
            result = market_data_service.get_historical_data("AAPL", "1d", 30, retries=2)
            assert result == []
            assert mock_get.call_count == 2


# ----- Sentiment Service Tests -----

class TestSentimentService:
    """Test sentiment analysis integration."""

    def test_get_sentiment_success(self, sentiment_service: SentimentService):
        """Test successful sentiment analysis."""
        with patch('backend.services.sentiment.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "sentiment": "positive",
                "score": 0.85,
                "articles_analyzed": 10,
                "timestamp": datetime.utcnow().isoformat(),
            }
            mock_get.return_value = mock_response

            result = sentiment_service.analyze("AAPL")
            assert result["sentiment"] == "positive"
            assert result["score"] == 0.85

    def test_get_sentiment_failure(self, sentiment_service: SentimentService):
        """Test sentiment analysis failure."""
        with patch('backend.services.sentiment.requests.get') as mock_get:
            mock_get.side_effect = Exception("API unavailable")
            result = sentiment_service.analyze("AAPL")
            # Should return neutral with fallback
            assert result["sentiment"] == "neutral"
            assert result["score"] == 0.0

    def test_sentiment_cache(self, sentiment_service: SentimentService):
        """Test that sentiment results are cached."""
        with patch('backend.services.sentiment.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"sentiment": "positive", "score": 0.8}
            mock_get.return_value = mock_response

            # First call fetches
            result1 = sentiment_service.analyze("AAPL")
            # Second call should use cache (no extra request)
            result2 = sentiment_service.analyze("AAPL")
            assert result1 == result2
            assert mock_get.call_count == 1

    def test_batch_sentiment(self, sentiment_service: SentimentService):
        """Test batch sentiment analysis."""
        with patch('backend.services.sentiment.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"symbol": "AAPL", "sentiment": "positive", "score": 0.8},
                {"symbol": "MSFT", "sentiment": "neutral", "score": 0.1},
            ]
            mock_post.return_value = mock_response

            result = sentiment_service.batch_analyze(["AAPL", "MSFT"])
            assert len(result) == 2
            assert result[0]["symbol"] == "AAPL"
            assert result[1]["symbol"] == "MSFT"


# ----- Payment Service Tests -----

class TestPaymentService:
    """Test payment gateway integration."""

    def test_create_payment_intent_stripe(self, payment_service: PaymentService):
        """Test Stripe payment intent creation."""
        with patch('backend.services.payment.stripe.PaymentIntent.create') as mock_create:
            mock_create.return_value = MagicMock(
                id="pi_test_123",
                client_secret="secret_test_123",
                amount=4999,
                currency="usd",
                status="requires_payment_method",
            )
            result = payment_service.create_payment_intent(
                amount=49.99,
                currency="usd",
                payment_method="stripe",
                metadata={"user_id": "test-user", "plan_id": "plan_123"},
            )
            assert result["id"] == "pi_test_123"
            assert result["client_secret"] == "secret_test_123"
            assert result["amount"] == 4999
            mock_create.assert_called_once()

    def test_create_payment_intent_paypal(self, payment_service: PaymentService):
        """Test PayPal order creation."""
        with patch('backend.services.payment.paypalrestsdk.Order.create') as mock_create:
            mock_order = MagicMock()
            mock_order.id = "PAY-123"
            mock_order.status = "CREATED"
            mock_order.links = [{"rel": "approval_url", "href": "https://paypal.com/approve"}]
            mock_create.return_value = mock_order

            result = payment_service.create_payment_intent(
                amount=49.99,
                currency="usd",
                payment_method="paypal",
                metadata={"user_id": "test-user"},
            )
            assert result["id"] == "PAY-123"
            assert result["status"] == "CREATED"
            assert "approval_url" in result

    def test_confirm_payment_stripe(self, payment_service: PaymentService):
        """Test Stripe payment confirmation."""
        with patch('backend.services.payment.stripe.PaymentIntent.confirm') as mock_confirm:
            mock_confirm.return_value = MagicMock(
                id="pi_test_123",
                status="succeeded",
                charges={"data": [{"id": "ch_123"}]},
            )
            result = payment_service.confirm_payment("pi_test_123", payment_method="stripe")
            assert result["status"] == "succeeded"
            assert "charge_id" in result

    def test_webhook_handling_stripe(self, payment_service: PaymentService, db_session: Session):
        """Test Stripe webhook handling."""
        payload = {
            "id": "evt_test_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_123",
                    "amount": 4999,
                    "currency": "usd",
                    "metadata": {"user_id": "test-user", "plan_id": "plan_123"},
                }
            },
        }
        # Mock the service that processes webhook
        with patch('backend.services.payment.stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = payload
            result = payment_service.handle_webhook(
                payload=json.dumps(payload),
                signature="test_signature",
                provider="stripe",
            )
            assert result["success"] is True

    def test_paypal_webhook(self, payment_service: PaymentService):
        """Test PayPal webhook handling."""
        payload = {
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "id": "PAY-123",
                "amount": {"value": "49.99", "currency_code": "USD"},
                "custom_id": "user-test-user-plan-123",
            },
        }
        with patch('backend.services.payment.paypalrestsdk.WebhookEvent.verify') as mock_verify:
            mock_verify.return_value = True
            result = payment_service.handle_webhook(
                payload=json.dumps(payload),
                signature="test_signature",
                provider="paypal",
            )
            assert result["success"] is True


# ----- Email Service Tests -----

class TestEmailService:
    """Test email service integration."""

    def test_send_email(self, email_service: EmailService):
        """Test sending an email via SendGrid."""
        with patch('backend.services.email.sendgrid.SendGridAPIClient.send') as mock_send:
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_send.return_value = mock_response

            result = email_service.send_email(
                to="test@example.com",
                subject="Test Email",
                body="This is a test email.",
                html_body="<p>This is a test email.</p>",
            )
            assert result is True
            mock_send.assert_called_once()

    def test_send_email_failure(self, email_service: EmailService):
        """Test email send failure."""
        with patch('backend.services.email.sendgrid.SendGridAPIClient.send') as mock_send:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_send.return_value = mock_response

            result = email_service.send_email(
                to="test@example.com",
                subject="Test Email",
                body="Test body",
            )
            assert result is False

    def test_send_welcome_email(self, email_service: EmailService, test_user: User):
        """Test sending a welcome email."""
        with patch('backend.services.email.EmailService.send_email') as mock_send:
            mock_send.return_value = True
            result = email_service.send_welcome_email(test_user)
            assert result is True
            mock_send.assert_called_once()

    def test_send_password_reset_email(self, email_service: EmailService, test_user: User):
        """Test sending a password reset email."""
        with patch('backend.services.email.EmailService.send_email') as mock_send:
            mock_send.return_value = True
            token = "reset-token-123"
            result = email_service.send_password_reset_email(test_user, token)
            assert result is True
            mock_send.assert_called_once()

    def test_send_notification_email(self, email_service: EmailService, test_user: User):
        """Test sending a notification email."""
        with patch('backend.services.email.EmailService.send_email') as mock_send:
            mock_send.return_value = True
            result = email_service.send_notification_email(
                test_user,
                subject="Trade Alert",
                message="Your position was closed.",
            )
            assert result is True
            mock_send.assert_called_once()


# ----- Notification Service Tests -----

class TestNotificationService:
    """Test notification service integration (email, push, SMS)."""

    def test_send_push_notification(self, notification_service: NotificationService, test_user: User):
        """Test sending push notification via Firebase Cloud Messaging."""
        with patch('backend.services.notification.fcm.FCM.send') as mock_send:
            mock_send.return_value = True
            result = notification_service.send_push_notification(
                user=test_user,
                title="Price Alert",
                body="AAPL reached $150",
                data={"symbol": "AAPL"},
            )
            assert result is True
            mock_send.assert_called_once()

    def test_send_sms_via_twilio(self, notification_service: NotificationService):
        """Test sending SMS via Twilio."""
        with patch('backend.services.notification.twilio.rest.Client.messages.create') as mock_create:
            mock_message = MagicMock()
            mock_message.sid = "SM123"
            mock_create.return_value = mock_message
            result = notification_service.send_sms(
                to="+1234567890",
                body="Test SMS",
            )
            assert result["sid"] == "SM123"
            mock_create.assert_called_once()

    def test_send_sms_failure(self, notification_service: NotificationService):
        """Test SMS send failure."""
        with patch('backend.services.notification.twilio.rest.Client.messages.create') as mock_create:
            mock_create.side_effect = Exception("Twilio error")
            result = notification_service.send_sms(
                to="+1234567890",
                body="Test SMS",
            )
            assert result is None

    def test_deliver_notification_all_channels(self, notification_service: NotificationService, test_user: User):
        """Test delivering notification via all configured channels."""
        with patch.multiple(
            notification_service,
            send_push_notification=MagicMock(return_value=True),
            send_email=MagicMock(return_value=True),
            send_sms=MagicMock(return_value=True),
        ):
            result = notification_service.deliver_notification(
                user=test_user,
                notification_type="trade_executed",
                message="Order filled",
                channels=["push", "email", "sms"],
            )
            assert result is True
            notification_service.send_push_notification.assert_called_once()
            notification_service.send_email.assert_called_once()
            notification_service.send_sms.assert_called_once()


# ----- Storage Service Tests -----

class TestStorageService:
    """Test cloud storage integration."""

    def test_upload_file_s3(self, storage_service: StorageService):
        """Test uploading a file to AWS S3."""
        with patch('backend.services.storage.boto3.client.upload_file') as mock_upload:
            mock_upload.return_value = True
            result = storage_service.upload_file(
                local_path="/tmp/test.txt",
                bucket="nexus-storage",
                key="uploads/test.txt",
            )
            assert result is True
            mock_upload.assert_called_once()

    def test_upload_file_gcs(self, storage_service: StorageService):
        """Test uploading a file to Google Cloud Storage."""
        with patch('backend.services.storage.storage.Client.bucket.blob.upload_from_filename') as mock_upload:
            mock_upload.return_value = None
            result = storage_service.upload_file(
                local_path="/tmp/test.txt",
                bucket="nexus-storage",
                key="uploads/test.txt",
                provider="gcs",
            )
            assert result is True

    def test_download_file(self, storage_service: StorageService):
        """Test downloading a file from storage."""
        with patch('backend.services.storage.boto3.client.download_file') as mock_download:
            mock_download.return_value = True
            result = storage_service.download_file(
                bucket="nexus-storage",
                key="uploads/test.txt",
                local_path="/tmp/downloaded.txt",
            )
            assert result is True

    def test_delete_file(self, storage_service: StorageService):
        """Test deleting a file from storage."""
        with patch('backend.services.storage.boto3.client.delete_object') as mock_delete:
            mock_delete.return_value = True
            result = storage_service.delete_file(
                bucket="nexus-storage",
                key="uploads/test.txt",
            )
            assert result is True

    def test_generate_presigned_url(self, storage_service: StorageService):
        """Test generating a presigned URL."""
        with patch('backend.services.storage.boto3.client.generate_presigned_url') as mock_generate:
            mock_generate.return_value = "https://s3.amazonaws.com/nexus-storage/uploads/test.txt?signature=xxx"
            result = storage_service.get_presigned_url(
                bucket="nexus-storage",
                key="uploads/test.txt",
                expiration=3600,
            )
            assert "https://" in result
            mock_generate.assert_called_once()


# ----- Webhook Service Tests -----

class TestWebhookService:
    """Test webhook delivery integration."""

    def test_deliver_webhook_success(self, webhook_service: WebhookService):
        """Test successful webhook delivery."""
        with patch('backend.services.webhook.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_post.return_value = mock_response

            payload = {"event": "trade_filled", "data": {"symbol": "AAPL"}}
            result = webhook_service.deliver_webhook(
                url="https://webhook.site/123",
                payload=payload,
                headers={"X-Custom": "Test"},
            )
            assert result["success"] is True
            assert result["status_code"] == 200

    def test_deliver_webhook_retry(self, webhook_service: WebhookService):
        """Test webhook delivery with retry on failure."""
        with patch('backend.services.webhook.requests.post') as mock_post:
            # Fail first two, succeed third
            mock_post.side_effect = [
                Exception("Connection error"),
                Exception("Timeout"),
                MagicMock(status_code=200, text="OK"),
            ]
            result = webhook_service.deliver_webhook(
                url="https://webhook.site/123",
                payload={"test": "data"},
                retries=3,
            )
            assert result["success"] is True
            assert mock_post.call_count == 3

    def test_deliver_webhook_all_fail(self, webhook_service: WebhookService):
        """Test webhook delivery all retries fail."""
        with patch('backend.services.webhook.requests.post') as mock_post:
            mock_post.side_effect = Exception("Network unreachable")
            result = webhook_service.deliver_webhook(
                url="https://webhook.site/123",
                payload={"test": "data"},
                retries=3,
            )
            assert result["success"] is False
            assert "error" in result
            assert mock_post.call_count == 3

    def test_webhook_signature(self, webhook_service: WebhookService):
        """Test generating and verifying webhook signatures."""
        secret = "test-secret"
        payload = {"event": "test"}
        signature = webhook_service.generate_signature(payload, secret)
        assert len(signature) > 0
        # Verify correct signature
        assert webhook_service.verify_signature(payload, signature, secret) is True
        # Verify incorrect signature
        assert webhook_service.verify_signature(payload, "wrong", secret) is False

    def test_queue_webhook_delivery(self, webhook_service: WebhookService):
        """Test queuing webhook delivery (Celery task)."""
        with patch('backend.services.webhook.deliver_webhook_task.delay') as mock_delay:
            mock_delay.return_value = MagicMock(id="task-123")
            webhook_service.queue_webhook_delivery(
                url="https://webhook.site/123",
                payload={"event": "test"},
            )
            mock_delay.assert_called_once()

    def test_webhook_endpoint_api(self, client: TestClient, auth_headers: Dict):
        """Test the webhook receiver endpoint (incoming)."""
        payload = {"event": "price_alert", "symbol": "AAPL", "price": 150.0}
        # This endpoint may require a specific API key or be public
        response = client.post(
            "/api/v1/webhooks/receive",
            json=payload,
            headers={"X-Webhook-Secret": "test-secret"},
        )
        # Depending on implementation, may return 200 or 204
        assert response.status_code in [200, 202, 204]


# ----- API Endpoint Integration Tests (with mocked external services) -----

class TestAPIWithExternalServices:
    """Test API endpoints that rely on external services."""

    def test_market_quote_endpoint(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/market/quote/{symbol}."""
        with patch('backend.services.market_data.MarketDataService.get_quote') as mock_quote:
            mock_quote.return_value = {
                "symbol": "AAPL",
                "price": 150.25,
                "change": 1.25,
                "change_percent": 0.84,
                "volume": 5000000,
                "timestamp": datetime.utcnow().isoformat(),
            }
            response = client.get("/api/v1/market/quote/AAPL", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "AAPL"
            assert data["price"] == 150.25

    def test_sentiment_endpoint(self, client: TestClient, auth_headers: Dict):
        """Test GET /api/v1/market/sentiment/{symbol}."""
        with patch('backend.services.sentiment.SentimentService.analyze') as mock_analyze:
            mock_analyze.return_value = {
                "sentiment": "positive",
                "score": 0.85,
                "articles_analyzed": 10,
            }
            response = client.get("/api/v1/market/sentiment/AAPL", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["sentiment"] == "positive"

    def test_create_subscription_with_payment(self, client: TestClient, auth_headers: Dict, db_session: Session):
        """Test subscribing with Stripe payment."""
        # Create a plan first
        plan = SubscriptionPlan(
            name="Pro",
            description="Professional",
            price_monthly=49.99,
            price_yearly=499.99,
            features={},
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)

        with patch('backend.services.payment.PaymentService.create_payment_intent') as mock_intent:
            mock_intent.return_value = {
                "id": "pi_test_123",
                "client_secret": "secret_test_123",
                "status": "requires_payment_method",
            }
            payload = {
                "plan_id": plan.id,
                "payment_method": "stripe",
            }
            response = client.post("/api/v1/subscriptions/subscribe", json=payload, headers=auth_headers)
            assert response.status_code == 201
            data = response.json()
            assert data["plan_id"] == plan.id
            assert data["status"] == "pending"
            assert "payment_intent" in data

    def test_stripe_webhook_endpoint(self, client: TestClient):
        """Test POST /api/v1/webhooks/stripe."""
        payload = {
            "id": "evt_test_123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test_123", "amount": 4999}},
        }
        with patch('backend.services.payment.stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = payload
            response = client.post(
                "/api/v1/webhooks/stripe",
                json=payload,
                headers={"Stripe-Signature": "test_signature"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["received"] is True

    def test_email_send_endpoint(self, client: TestClient, auth_headers: Dict):
        """Test POST /api/v1/notifications/send-email (admin only)."""
        with patch('backend.services.email.EmailService.send_email') as mock_send:
            mock_send.return_value = True
            payload = {
                "to": "test@example.com",
                "subject": "Test",
                "body": "Test email",
            }
            response = client.post("/api/v1/notifications/send-email", json=payload, headers=auth_headers)
            # May require admin privileges; could return 403
            assert response.status_code in [200, 403]


# ----- Error Handling and Fallbacks -----

class TestExternalServiceFallbacks:
    """Test graceful degradation when external services fail."""

    def test_market_data_fallback_cache(self, market_data_service: MarketDataService):
        """Test that market data falls back to cache on failure."""
        # Pre-populate cache
        market_data_service._cache["AAPL"] = {"price": 150.0, "timestamp": datetime.utcnow()}
        with patch('backend.services.market_data.requests.get') as mock_get:
            mock_get.side_effect = Exception("API down")
            result = market_data_service.get_quote("AAPL")
            # Should return cached data
            assert result["price"] == 150.0

    def test_sentiment_fallback_neutral(self, sentiment_service: SentimentService):
        """Test that sentiment falls back to neutral on failure."""
        with patch('backend.services.sentiment.requests.get') as mock_get:
            mock_get.side_effect = Exception("API down")
            result = sentiment_service.analyze("AAPL")
            assert result["sentiment"] == "neutral"
            assert result["score"] == 0.0

    def test_payment_fallback_offline(self, payment_service: PaymentService):
        """Test that payment fails gracefully when provider is unavailable."""
        with patch('backend.services.payment.stripe.PaymentIntent.create') as mock_create:
            mock_create.side_effect = Exception("Stripe unavailable")
            result = payment_service.create_payment_intent(49.99, "usd", "stripe")
            assert result["status"] == "failed"
            assert "error" in result

    def test_webhook_fallback_queue(self, webhook_service: WebhookService):
        """Test that webhook delivery falls back to queue on failure."""
        with patch('backend.services.webhook.requests.post') as mock_post:
            mock_post.side_effect = Exception("Network error")
            with patch('backend.services.webhook.WebhookService.queue_webhook_delivery') as mock_queue:
                mock_queue.return_value = {"task_id": "task-123"}
                result = webhook_service.deliver_webhook(
                    url="https://webhook.site/123",
                    payload={"test": "data"},
                    queue_on_failure=True,
                )
                # Should queue for retry
                mock_queue.assert_called_once()

