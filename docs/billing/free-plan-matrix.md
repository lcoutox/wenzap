# Free Plan Matrix — Billing/Plans.1

## Plan Limits (starter / Free)

| Feature | Free | Growth | Scale | Enterprise |
|---|---|---|---|---|
| Agents | 1 | 5 | 20 | Unlimited |
| Knowledge Bases | 1 | 5 | 20 | Unlimited |
| Sources per KB | 10 | 50 | 200 | Unlimited |
| Users | 1 | 5 | 20 | Unlimited |
| Channels | 1 | 5 | 20 | Unlimited |
| Pipelines | 0 | 3 | 10 | Unlimited |
| Monthly AI Credits | 200 | 2,000 | 10,000 | Custom |
| Monthly Conversations | 50 | 500 | 5,000 | Custom |
| Max File Size | 5 MB | 20 MB | 50 MB | 100 MB |

## Channel Type Gates

| Channel Type | Free | Growth | Scale | Enterprise |
|---|---|---|---|---|
| Web Widget | ✅ | ✅ | ✅ | ✅ |
| API | ✅ | ✅ | ✅ | ✅ |
| WhatsApp | ❌ | ✅ | ✅ | ✅ |
| Instagram | ❌ | ❌ | ✅ | ✅ |
| Telegram | ❌ | ❌ | ✅ | ✅ |
| Slack | ❌ | ❌ | ❌ | ✅ |

## Feature Gates

| Feature | Min Plan |
|---|---|
| WhatsApp channel | Growth |
| Remove "Powered by Wenzap" branding | Growth |
| Pipelines | Growth |
| Integrations | Growth |
| Catalog | Growth |
| Multiple Knowledge Bases | Growth |
| Custom AI model | Scale |
| Analytics | Scale |
| API access | Growth |

## Enforcement Rules

### Conversations (`monthly_conversations = 50` on Free)
- Checked at conversation creation time (dashboard, web widget, WhatsApp inbound).
- Blocked with HTTP 402 when `conversations_count >= monthly_conversations`.
- Counter incremented atomically via `UPDATE ... SET conversations_count = conversations_count + 1`.
- Counter is auto-created on-demand if missing (`get_or_create_usage_counter`).

### AI Credits (`monthly_ai_credits = 200` on Free)
- Checked before each AI reply in `agent_test_service` and `conversation_agent_reply_service`.
- Blocked with HTTP 402 when `ai_credits_used + needed > monthly_ai_credits`.
- Incremented atomically after each reply.
- Counter is auto-created on-demand (no more silent block when counter is missing).

### WhatsApp Channel Blocking
- `POST /channels` with `channel_type = "whatsapp"` returns HTTP 402 on Free plan.
- Enforced in `channel_service.create_channel()` via `check_channel_type_or_402()`.

### Users Limit (`users_limit = 1` on Free)
- **Status: NOT ENFORCED — no member-add flow exists yet.**
- `GET /workspaces/current/members` — lista membros (sem limite).
- `PATCH /workspaces/current/members/{id}/role` — altera role (sem limite).
- Nenhum endpoint `POST /members` ou fluxo de convite existe no produto atual.
- O campo `users_limit` existe no modelo `Plan` e o helper `check_users_limit()` está implementado em `plan_feature_service.py`.
- Quando o fluxo de convite for implementado, chamar `check_users_limit(db, workspace_id)` antes de criar o `WorkspaceMember`.

### "Powered by Wenzap" Branding
- Mandatory on Free plan — cannot be disabled.
- Gate: `plan_allows_feature(plan_code, "remove_powered_by")` returns False for Free.
- Widget config must never suppress branding for Free workspaces.

## Migration Reference

- Seed: `007_seed_plans.py` — initial plan with `name="Starter"`
- Patch: `020_patch_plans_kb_limits.py` — `knowledge_bases_limit=2`
- **This phase**: `048_update_free_plan.py` — sets `name="Free"`, `knowledge_bases_limit=1`, `monthly_ai_credits=200`, `monthly_conversations=50`

## Implementation Files

| File | Change |
|---|---|
| `app/services/plan_feature_service.py` | New — feature gate helpers |
| `app/services/plan_service.py` | `get_or_create_usage_counter`, `check_and_count_new_conversation` |
| `app/services/channel_service.py` | `check_channel_type_or_402` on create |
| `app/services/member_service.py` | `check_users_limit` placeholder |
| `app/services/conversation_service.py` | Conversation limit check on create |
| `app/services/public_widget_service.py` | Conversation limit check on widget session |
| `app/services/whatsapp_inbound_service.py` | Conversation limit check on new conversation |
| `app/services/agent_test_service.py` | Use `get_or_create_usage_counter` |
| `app/services/conversation_agent_reply_service.py` | Use `get_or_create_usage_counter` |
