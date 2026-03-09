from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User, PlanTier
from app.routers.auth import get_current_user
from app.services import stripe_service
from app.config import settings
import logging

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)

PRICE_MAP = {"pro": settings.stripe_price_pro_monthly, "team": settings.stripe_price_team_monthly}

@router.post("/checkout/{plan}")
async def create_checkout(plan: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if plan not in PRICE_MAP:
        raise HTTPException(status_code=400, detail="Invalid plan")
    if not user.stripe_customer_id:
        customer_id = await stripe_service.create_customer(user.email, user.full_name or "")
        user.stripe_customer_id = customer_id
        await db.commit()
    url = await stripe_service.create_checkout_session(
        customer_id=user.stripe_customer_id,
        price_id=PRICE_MAP[plan],
        success_url="https://fundwatch.sustainovate.com/dashboard?upgraded=1",
        cancel_url="https://fundwatch.sustainovate.com/pricing",
    )
    return {"url": url}

@router.post("/portal")
async def billing_portal(user: User = Depends(get_current_user)):
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account")
    url = await stripe_service.create_billing_portal(
        customer_id=user.stripe_customer_id,
        return_url="https://fundwatch.sustainovate.com/dashboard",
    )
    return {"url": url}

@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.handle_webhook(payload, sig)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook")

    if event["type"] == "customer.subscription.updated":
        sub = event["data"]["object"]
        customer_id = sub["customer"]
        plan_name = sub["items"]["data"][0]["price"]["lookup_key"] or "pro"
        result = await db.execute(__import__('sqlalchemy').select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user:
            user.plan = PlanTier(plan_name) if plan_name in PlanTier.__members__ else PlanTier.pro
            user.stripe_subscription_id = sub["id"]
            await db.commit()

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        result = await db.execute(__import__('sqlalchemy').select(User).where(User.stripe_customer_id == sub["customer"]))
        user = result.scalar_one_or_none()
        if user:
            user.plan = PlanTier.free
            user.stripe_subscription_id = None
            await db.commit()

    return {"ok": True}
