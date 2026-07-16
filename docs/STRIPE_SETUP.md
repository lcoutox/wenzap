# Stripe Billing Setup

## Variáveis de Ambiente (Obrigatórias em Prod)

Adicione ao `.env` ou variáveis do sistema:

```bash
# Get from Stripe Dashboard → Developers → API Keys
STRIPE_API_KEY=sk_live_... (produção) ou sk_test_... (desenvolvimento)

# Get from Stripe Dashboard → Developers → Webhooks
# Endpoint: POST https://api.wenzap.com.br/webhooks/stripe
STRIPE_WEBHOOK_SECRET=whsec_live_... ou whsec_test_...
```

## Setup no Stripe Dashboard

### 1. Create Products & Prices

**Product: Wenzap Growth**
- Price ID: `price_growth_monthly_brl`
- Amount: R$ 247.00
- Currency: BRL
- Billing: Monthly

**Product: Wenzap Scale**
- Price ID: `price_scale_monthly_brl`
- Amount: R$ 587.00
- Currency: BRL
- Billing: Monthly

**Product: Wenzap Enterprise**
- Price ID: `price_enterprise_monthly_brl`
- Amount: R$ 997.00
- Currency: BRL
- Billing: Monthly

### 2. Setup Webhook

Go to **Developers → Webhooks** and add new webhook endpoint:

- **Endpoint URL**: `https://api.wenzap.com.br/webhooks/stripe`
- **Events to send**:
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_succeeded`
  - `invoice.payment_failed`

Copy the **Signing Secret** (whsec_...) to `STRIPE_WEBHOOK_SECRET`.

### 3. Test with Stripe CLI (Dev Only)

```bash
# Install Stripe CLI (https://stripe.com/docs/stripe-cli)
stripe login
stripe listen --forward-to localhost:8000/webhooks/stripe
```

## Database

Migrations are applied automatically on first run. Verify:

```bash
# Check tables exist
psql $DATABASE_URL -c "\dt stripe_events stripe_sync_log"

# Check workspace_subscriptions has Stripe columns
psql $DATABASE_URL -c "\d workspace_subscriptions" | grep stripe
```

## Testing

### Test Cards (Development)

| Scenario | Card | Exp | CVC |
|----------|------|-----|-----|
| Success | 4242 4242 4242 4242 | 12/26 | 123 |
| Declined | 4000 0000 0000 0002 | 12/26 | 123 |
| Requires Auth | 4000 2500 0000 3155 | 12/26 | 123 |

### Manual Testing Flow

1. Login to Wenzap as workspace admin
2. Navigate to `/dashboard/billing`
3. Click "Fazer Upgrade" on a plan
4. Use test card above
5. Verify subscription is created in DB:
   ```sql
   SELECT id, stripe_subscription_id, status FROM workspace_subscriptions WHERE workspace_id = '<your-workspace-id>';
   ```

## Verification Checklist

- [ ] `STRIPE_API_KEY` set (sk_live_... for production)
- [ ] `STRIPE_WEBHOOK_SECRET` set (whsec_live_... for production)
- [ ] Products & Prices created in Stripe Dashboard
- [ ] Webhook endpoint configured in Stripe Dashboard
- [ ] Database migrations applied
- [ ] `stripe_events` and `stripe_sync_log` tables exist
- [ ] `workspace_subscriptions` has 6 new Stripe columns
- [ ] Billing page loads at `/dashboard/billing`
- [ ] Can view plans and pricing
- [ ] Checkout flow works (test card)
- [ ] Webhook events are being logged in `stripe_events` table

## Troubleshooting

### Webhook not receiving events

1. Check `STRIPE_WEBHOOK_SECRET` matches dashboard
2. Check API logs for 400/401 errors
3. Test with `stripe listen` locally first
4. Verify endpoint is publicly accessible

### Checkout not creating subscription

1. Check `STRIPE_API_KEY` is correct
2. Verify Price IDs match in Stripe Dashboard
3. Check logs for Stripe API errors
4. Ensure workspace has valid `admin_email`

### Coupon not applying

1. Create coupon in Stripe Dashboard
2. Set valid date range (redeem_by)
3. Test with coupon code in billing page
4. Check `stripe_sync_log` for errors

## Next Steps (Phase 2)

- [ ] Email notifications for subscription changes
- [ ] Usage/consumption alerts
- [ ] MRR & churn analytics
- [ ] Admin panel for coupon management
- [ ] Multiple currencies (USD, EUR, etc)
- [ ] Invoice PDF generation
