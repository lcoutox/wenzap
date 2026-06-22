# PHASE_1_SAAS_FOUNDATION.md

## Phase name

SaaS Foundation

## Objective

Create the initial technical foundation for Nexbrain as a multi-tenant B2B SaaS platform.

This phase does not implement AI agents, knowledge bases, inbox, pipelines or integrations yet.

The goal is to create a secure and extensible foundation for future product modules.

## Scope

This phase includes:

* monorepo setup
* backend API setup
* frontend web app setup
* local development environment
* authentication integration
* workspace/tenant model
* internal user model
* basic RBAC
* plan and usage limit structure
* authenticated dashboard shell
* tenant isolation tests

## Out of scope

This phase does not include:

* AI agents
* LLM integration
* knowledge base / RAG
* file upload
* website widget
* inbox
* conversations
* contacts
* pipelines
* automations
* real billing integration
* WhatsApp
* public API
* integration marketplace
* analytics dashboard

## Proposed monorepo structure

```txt
nexbrain/
  apps/
    api/
    web/
  packages/
    shared/
  docs/
    product/
    architecture/
    development/
  infra/
  CLAUDE.md
  README.md
  docker-compose.yml
```

## Applications

### apps/api

Backend API.

Suggested stack:

* Python
* FastAPI
* PostgreSQL
* SQLAlchemy or SQLModel
* Alembic
* Pydantic
* Pytest

### apps/web

Frontend dashboard.

Suggested stack:

* React or Next.js
* TypeScript
* Tailwind CSS
* Clerk frontend SDK
* API client

### packages/shared

Shared types, constants or schemas when useful.

Do not overuse this package early.

## Authentication

Use external authentication provider if configured.

Preferred initial provider:

* Clerk

Authentication responsibilities:

* handle login
* handle logout
* manage authenticated session
* provide user identity
* provide organization/workspace context when possible

The backend must validate authenticated requests.

The backend must not trust user_id or workspace_id from request body.

## Internal identity model

Even when using an external auth provider, Nexbrain should maintain internal records.

Suggested entities:

### users

Internal representation of authenticated users.

Fields:

* id
* external_auth_user_id
* email
* name
* avatar_url
* created_at
* updated_at

### workspaces

Customer organization/account.

Fields:

* id
* external_auth_org_id
* name
* slug
* owner_user_id
* plan_id
* status
* created_at
* updated_at

### workspace_members

Relationship between users and workspaces.

Fields:

* id
* workspace_id
* user_id
* role
* status
* created_at
* updated_at

## Basic roles

Initial roles:

* owner
* admin
* member
* viewer

Role rules:

### owner

Can manage everything in the workspace.

### admin

Can manage most workspace settings and product modules.

### member

Can use operational modules.

### viewer

Can only view data.

Do not implement advanced permissions in this phase.

## Plan structure

Create initial plan structure but do not implement real payment integration yet.

Suggested entities:

### plans

Fields:

* id
* code
* name
* description
* monthly_price_cents
* currency
* agents_limit
* knowledge_bases_limit
* users_limit
* pipelines_limit
* integrations_limit
* monthly_ai_credits
* monthly_conversations
* is_active
* created_at
* updated_at

Initial seed plans:

* starter
* growth
* scale
* enterprise

### workspace_subscriptions

Fields:

* id
* workspace_id
* plan_id
* status
* current_period_start
* current_period_end
* created_at
* updated_at

### usage_counters

Fields:

* id
* workspace_id
* period_start
* period_end
* ai_credits_used
* conversations_count
* messages_count
* created_at
* updated_at

## Tenant isolation

Tenant isolation is mandatory from phase 1.

Rules:

* Every customer-owned entity must include workspace_id.
* workspace_id must come from authenticated context.
* API endpoints must filter data by current workspace.
* Frontend must never decide workspace_id for authorization.
* Tests must verify that data from workspace A cannot be accessed by workspace B.

## Backend API requirements

Initial endpoints may include:

### Health

* GET /health

### Auth/session

* GET /me

Returns current authenticated user and current workspace context.

### Workspaces

* GET /workspaces
* GET /workspaces/current
* PATCH /workspaces/current

### Members

* GET /workspaces/current/members
* PATCH /workspaces/current/members/{member_id}/role

### Plans

* GET /plans
* GET /workspaces/current/plan
* GET /workspaces/current/usage

## Frontend requirements

Initial screens:

* login page
* authenticated app shell
* dashboard home
* workspace settings
* members page
* plan/usage page

The UI can be simple.

Focus on structure and correctness.

## Testing requirements

Create tests for:

* health endpoint
* authenticated /me endpoint
* unauthenticated requests are rejected
* workspace context is resolved correctly
* workspace member role is respected
* tenant isolation between two workspaces
* plan limits can be loaded for a workspace

## Acceptance criteria

This phase is complete when:

1. The monorepo is created.
2. The API app runs locally.
3. The web app runs locally.
4. PostgreSQL runs locally through Docker Compose.
5. Migrations are configured.
6. Authentication works.
7. Authenticated user is mapped to internal user.
8. Workspace context is available in the API.
9. Workspace has members and roles.
10. Workspace has an associated plan.
11. Usage counters structure exists.
12. Dashboard shell is accessible only after login.
13. Tenant isolation tests pass.
14. Documentation is updated.

## Implementation instructions for Claude Code

Before implementation:

1. Read CLAUDE.md.
2. Read PRODUCT_VISION.md.
3. Read PRODUCT_MODULES.md.
4. Read this document.
5. Propose a technical plan.
6. List files to create.
7. List database models.
8. List migration steps.
9. List tests.
10. Do not implement until the plan is approved if the user asks for planning first.

During implementation:

* Keep changes small.
* Do not implement out-of-scope modules.
* Prioritize tenant isolation.
* Add tests for security-critical behavior.
* Avoid premature abstractions.
* Prefer explicit services and clear naming.
