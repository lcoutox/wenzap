# Stripe Billing Setup

Self-serve checkout is wired for the **Growth** plan only. Scale and
Enterprise are sales-assisted tiers (`plans.is_public = false` — see
migration `051_add_plan_visibility_fields.py`) and are not sold through
Stripe Checkout; upgrade those workspaces manually or extend the price map
below if that changes.

## Variáveis de Ambiente (Obrigatórias em Prod)

```bash
# Stripe Dashboard → Developers → API Keys
STRIPE_API_KEY=sk_live_...

# Stripe Dashboard → Developers → Webhooks → signing secret
STRIPE_WEBHOOK_SECRET=whsec_live_...

# Stripe Dashboard → Products → each Price's ID (price_...)
STRIPE_PRICE_ID_GROWTH=price_...
STRIPE_PRICE_ID_SCALE=price_...
STRIPE_PRICE_ID_ENTERPRISE=price_...
```

Without `STRIPE_API_KEY`, every `/workspaces/current/billing/*` endpoint
returns `503` (`StripeNotConfiguredError`) — safe no-op in dev/test.

## Setup no Stripe Dashboard

### 1. Create Products & Prices

Prices must match `plans.monthly_price_cents` (see migration
`064_update_plan_prices.py`):

| Plan | Price | Env var |
|------|-------|---------|
| Growth | R$ 247,00/mês | `STRIPE_PRICE_ID_GROWTH` |
| Scale | R$ 587,00/mês | `STRIPE_PRICE_ID_SCALE` (reserved, not sold via checkout yet) |
| Enterprise | R$ 997,00/mês | `STRIPE_PRICE_ID_ENTERPRISE` (reserved) |

### 2. Setup Webhook

**Developers → Webhooks → Add endpoint**:

- **URL**: `https://api.wenzap.com.br/webhooks/stripe`
- **Events**:
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_succeeded`
  - `invoice.payment_failed`

Copy the signing secret into `STRIPE_WEBHOOK_SECRET`.

### 3. Test with Stripe CLI (Dev Only)

```bash
stripe login
stripe listen --forward-to localhost:8000/webhooks/stripe
```

## API Endpoints

All under `/workspaces/current/billing` (resolves the workspace from the
session — never trust a client-supplied workspace id), owner/admin only:

- `POST /workspaces/current/billing/checkout-session` — `{plan_code, coupon_code?}` → `{checkout_url}`
- `GET /workspaces/current/billing/portal-session` — `{portal_url}` (Stripe Customer Portal — handles payment method updates, invoice history, and self-service cancel)
- `POST /workspaces/current/billing/validate-coupon` — `{coupon_code, plan_code}` → discount preview
- `POST /workspaces/current/billing/cancel` — `{reason?}` — schedules cancellation at period end
- `POST /webhooks/stripe` — public, signature-verified

## Testing

### Test Cards (Development)

| Scenario | Card | Exp | CVC |
|----------|------|-----|-----|
| Success | 4242 4242 4242 4242 | 12/26 | 123 |
| Declined | 4000 0000 0000 0002 | 12/26 | 123 |
| Requires Auth | 4000 2500 0000 3155 | 12/26 | 123 |

### Manual Testing Flow

1. Login to Wenzap as workspace owner/admin
2. Navigate to `/dashboard/plan`
3. Click "Assinar Growth" (optionally apply a coupon first)
4. Complete checkout with a test card
5. Verify the workspace's subscription synced:
   ```sql
   SELECT plan_id, status, stripe_subscription_id, stripe_customer_id
   FROM workspace_subscriptions WHERE workspace_id = '<workspace-id>';
   ```

## Verification Checklist

- [ ] `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` set
- [ ] `STRIPE_PRICE_ID_GROWTH` set and matches the Stripe Price amount
- [ ] Webhook endpoint configured and receiving events (check `stripe_events` table)
- [ ] `/dashboard/plan` shows real plans and lets an owner/admin check out
- [ ] Non-owner/admin members see plans read-only (403 on mutation endpoints)
- [ ] Checkout with a test card creates/updates the workspace's subscription
- [ ] "Gerenciar assinatura" opens the Stripe Customer Portal for paying workspaces

## Troubleshooting

### Webhook not receiving events

1. Check `STRIPE_WEBHOOK_SECRET` matches the dashboard
2. Check API logs for 400 responses on `/webhooks/stripe`
3. Test with `stripe listen` locally first

### Checkout not creating subscription

1. Check `STRIPE_API_KEY` and the relevant `STRIPE_PRICE_ID_*` are correct
2. Confirm the workspace owner has a valid email (Stripe customer email source)
3. Check `stripe_sync_log` for the failed action's `error_message`

### Coupon not applying

1. Create the coupon (or a promotion code) in the Stripe Dashboard
2. Check its `redeem_by` / `max_redemptions` aren't exhausted
3. Check `stripe_sync_log` for validation errors

## Next Steps (Phase 2)

- [ ] Email notifications for subscription changes
- [ ] Self-serve checkout for Scale (currently sales-assisted)
- [ ] MRR & churn analytics
- [ ] Admin panel for coupon management
- [ ] Multiple currencies (USD, EUR, etc)
