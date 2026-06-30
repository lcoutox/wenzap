# AGENTS.md

## Project

Project name: Nexbrain

Nexbrain is a B2B SaaS platform for creating, orchestrating and operating AI agents for companies.

The platform allows companies to create AI agents, connect them to knowledge bases, publish them across channels, manage conversations through an inbox, organize leads/conversations in pipelines, and later connect agents to business tools through integrations and actions.

## Product positioning

Nexbrain is not just a chatbot builder.

Nexbrain is an AI agent orchestration platform for business operations.

Core positioning:

> Create AI agents connected to your company’s data, channels and processes.

The product should help companies apply AI to:

* customer support
* sales
* lead qualification
* onboarding
* collections
* internal operations
* business process automation

## Current stage

The product is in early design and MVP planning stage.

Do not assume the MVP scope unless a specific feature spec or PRD is provided.

When asked to implement something, always verify the relevant documentation first.

## Engineering behavior

Before implementing any non-trivial feature:

1. Read the relevant docs.
2. Summarize your understanding.
3. Propose a technical plan.
4. List files to create or modify.
5. List database changes, if any.
6. List tests to create or update.
7. Wait for approval if the request explicitly asks for planning first.

When implementing:

* Keep scope small.
* Avoid adding features that were not requested.
* Prefer simple, explicit architecture.
* Avoid premature abstraction.
* Preserve multi-tenant isolation.
* Add tests for important business logic.
* Update documentation when decisions change.

## Critical product rules

* Nexbrain must be multi-tenant from the beginning.
* Every customer account is an organization/workspace.
* Business data must be isolated by organization.
* The frontend must never be trusted to define organization_id directly.
* Organization context must come from authenticated user/session context.
* AI agents must always be controllable by humans.
* Human handoff must be supported in the product design.
* AI behavior must be auditable through logs.
* Integrations must be designed as modular connectors.
* Pipelines are operational workflows, not a full CRM replacement.
* Knowledge bases must be reusable across agents.
* Agents should be treated as business operators, not only chatbots.

## Product vocabulary

Use these terms consistently:

* Workspace: customer organization/account.
* User: person using the platform.
* Agent: AI business agent configured by the company.
* Knowledge Base: collection of documents, URLs, Q&A and structured information.
* Source: individual knowledge input inside a Knowledge Base.
* Channel: place where an agent communicates, such as website widget, WhatsApp, Instagram, Telegram, Slack or API.
* Inbox: central place to manage conversations.
* Conversation: message thread between a contact and an agent/company.
* Contact: external person interacting with the company.
* Pipeline: operational board used to organize conversations, leads or tasks.
* Stage: step inside a pipeline.
* Card: item inside a pipeline stage, usually linked to a conversation/contact.
* Action: operation an agent can execute, such as call webhook, create lead or move pipeline card.
* Integration: external system connected to Nexbrain.
* Credit: internal consumption unit for AI usage.

## Initial modules

The complete product vision includes:

* Workspaces
* Users and permissions
* Agents
* Knowledge Bases
* Sources
* Channels
* Website Widget
* Inbox
* Conversations
* Contacts
* Pipelines
* Stages
* Cards
* Actions
* Automations
* Integrations
* Templates
* Analytics
* Billing and usage limits
* Developer API
* Webhooks

Do not implement all modules at once.

Always implement in small vertical slices.

## Recommended development workflow

Use this loop:

1. Spec
2. Plan
3. Implement
4. Test
5. Review
6. Refactor
7. Commit

For every feature, prefer a vertical slice:

* database model/migration
* backend service
* API endpoint
* frontend UI
* tests
* documentation update

## Security rules

Always consider:

* tenant isolation
* authentication
* authorization
* input validation
* rate limiting
* secret handling
* audit logs
* webhook signature validation
* idempotency for external events
* safe logging without sensitive data

Never log:

* API keys
* tokens
* passwords
* private customer data unnecessarily
* full prompts containing sensitive customer information unless explicitly required by a debug/audit feature

## AI rules

AI features must be designed with:

* prompt versioning
* model configuration
* traceability
* error handling
* fallback behavior
* human handoff
* knowledge source tracking when possible
* usage/cost tracking

Agents should not perform irreversible actions without explicit configuration or confirmation rules.

## Code quality

Prefer:

* clear naming
* small functions
* explicit services
* typed schemas
* predictable folder structure
* tests for business rules
* simple abstractions
* readable code over clever code

Avoid:

* hidden global state
* hardcoded tenant IDs
* hardcoded secrets
* business logic inside UI components
* untested critical flows
* large uncontrolled refactors
* mixing unrelated features in one change

## Documentation rule

When a decision affects architecture, product scope or terminology, update the appropriate documentation file.

If no file exists, suggest creating one before implementing.
