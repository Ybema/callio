"""Stripe subscription management."""
import stripe
from app.config import settings

stripe.api_key = settings.stripe_secret_key

async def create_customer(email: str, name: str) -> str:
    customer = stripe.Customer.create(email=email, name=name)
    return customer.id

async def create_checkout_session(customer_id: str, price_id: str, success_url: str, cancel_url: str) -> str:
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url

async def create_billing_portal(customer_id: str, return_url: str) -> str:
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url

def handle_webhook(payload: bytes, sig_header: str) -> dict:
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )
