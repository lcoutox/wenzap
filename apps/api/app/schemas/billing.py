from pydantic import BaseModel


class CheckoutSessionRequest(BaseModel):
    plan_code: str
    coupon_code: str | None = None


class CheckoutSessionOut(BaseModel):
    checkout_url: str


class PortalSessionOut(BaseModel):
    portal_url: str


class ValidateCouponRequest(BaseModel):
    coupon_code: str
    plan_code: str


class ValidateCouponOut(BaseModel):
    valid: bool
    code: str | None = None
    discount_type: str | None = None
    discount_value: float | None = None
    original_price_cents: int | None = None
    discounted_price_cents: int | None = None
    expires_at: str | None = None
    error: str | None = None


class CancelSubscriptionRequest(BaseModel):
    reason: str | None = None
