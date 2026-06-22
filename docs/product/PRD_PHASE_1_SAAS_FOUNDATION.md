# PRD — Phase 1: SaaS Foundation

## 1. Phase name

SaaS Foundation

## 2. Product context

Nexbrain is a B2B SaaS platform for creating, orchestrating and operating AI agents for companies.

The long-term product will include AI agents, knowledge bases, channels, inbox, pipelines, automations, integrations, analytics and billing.

Before building AI features, Nexbrain needs a secure and extensible SaaS foundation.

This phase creates the basic structure required for all future modules.

## 3. Objective

Create the initial product foundation that allows users to access Nexbrain inside a workspace with authentication, organization context, roles, plan information and usage limits.

The goal is not to create AI agents yet.

The goal is to ensure that all future product modules can be built on top of a correct multi-tenant architecture.

## 4. User problem

Companies using Nexbrain will need private and isolated workspaces.

Each company must be able to:

* access its own account;
* manage its own workspace;
* have multiple users;
* assign user roles;
* operate inside a plan;
* have usage limits;
* access only its own data.

Without this foundation, future modules like agents, conversations, knowledge bases and pipelines would be insecure or difficult to scale.

## 5. Target users for this phase

### Workspace owner

The person who creates or owns the company account.

Needs to:

* access the platform;
* view the workspace;
* manage basic workspace settings;
* view plan and usage;
* see workspace members.

### Admin

A user who helps manage the workspace.

Needs to:

* access the dashboard;
* view members;
* use workspace-level features allowed by role.

### Member

A regular operational user.

Needs to:

* access the platform;
* operate inside the current workspace;
* be restricted by role.

### Viewer

A read-only user.

Needs to:

* access allowed pages;
* not perform restricted actions.

## 6. User flows

### 6.1 Login flow

A user should be able to log in to Nexbrain using the configured authentication provider.

Expected behavior:

1. User opens Nexbrain.
2. User is redirected to login if not authenticated.
3. User logs in.
4. User is redirected to the authenticated dashboard.
5. The system identifies the current user.
6. The system identifies the current workspace.

### 6.2 Workspace access flow

A logged-in user should access Nexbrain inside a workspace context.

Expected behavior:

1. User logs in.
2. System resolves the user’s current workspace.
3. Dashboard shows the current workspace name.
4. API requests use the authenticated workspace context.
5. User cannot access data from another workspace.

### 6.3 Basic member management flow

A workspace owner or admin should be able to view workspace members.

Expected behavior:

1. User accesses workspace members page.
2. System lists members of the current workspace.
3. User can see names, emails, roles and status.
4. Unauthorized users cannot change restricted information.

### 6.4 Plan and usage flow

A workspace user should be able to view plan and usage information.

Expected behavior:

1. User accesses plan/usage page.
2. System shows current plan.
3. System shows configured limits.
4. System shows current usage counters, even if usage is initially zero.

### 6.5 Authorization flow

The system should restrict actions based on role.

Expected behavior:

1. Owner can manage workspace-level settings.
2. Admin can manage most operational settings.
3. Member has limited operational access.
4. Viewer can only view allowed data.
5. Unauthorized actions return a clear error.

## 7. Functional requirements

### 7.1 Authentication

The system must support user authentication.

Requirements:

* allow login;
* allow logout;
* protect authenticated routes;
* expose current authenticated user to the frontend;
* validate authenticated API requests;
* reject unauthenticated API requests.

Preferred provider:

* Clerk

### 7.2 Internal user model

The system must maintain an internal user record linked to the external authentication provider.

The internal user should include:

* id;
* external auth provider user id;
* email;
* name;
* avatar URL when available;
* timestamps.

### 7.3 Workspace model

The system must support workspaces as customer organizations.

A workspace should include:

* id;
* external auth provider organization id when available;
* name;
* slug;
* owner user id;
* plan id;
* status;
* timestamps.

### 7.4 Workspace membership

The system must support multiple users per workspace.

A membership should include:

* id;
* workspace id;
* user id;
* role;
* status;
* timestamps.

Initial roles:

* owner;
* admin;
* member;
* viewer.

### 7.5 Current workspace context

The backend must resolve the current workspace from authenticated context.

Rules:

* the frontend must not be trusted to define workspace ownership;
* workspace id must not be accepted from request body for authorization decisions;
* all future customer-owned records must be filtered by workspace context.

### 7.6 RBAC

The system must implement basic role-based access control.

Initial behavior:

* owner can manage all workspace settings;
* admin can manage operational workspace settings;
* member can access operational modules;
* viewer can access read-only pages;
* unauthorized actions must be rejected.

Advanced permissions are out of scope for this phase.

### 7.7 Plans

The system must have a plan structure, even without real payment integration.

Initial plans:

* starter;
* growth;
* scale;
* enterprise.

A plan should include limits such as:

* agents limit;
* knowledge bases limit;
* users limit;
* pipelines limit;
* integrations limit;
* monthly AI credits;
* monthly conversations.

### 7.8 Workspace subscription

Each workspace should be associated with a plan.

A workspace subscription should include:

* workspace id;
* plan id;
* status;
* current period start;
* current period end.

Real billing integration is out of scope.

### 7.9 Usage counters

The system should have usage counters prepared for future modules.

Initial counters:

* AI credits used;
* conversations count;
* messages count.

Usage can initially be zero.

### 7.10 Dashboard shell

The frontend must include an authenticated dashboard shell.

The shell should include:

* sidebar or navigation;
* current workspace display;
* user menu;
* logout action;
* placeholder pages for future modules if useful.

Initial pages:

* dashboard home;
* workspace settings;
* members;
* plan and usage.

## 8. Non-functional requirements

### 8.1 Security

The system must enforce tenant isolation from the beginning.

Critical rules:

* no workspace should access another workspace’s data;
* no unauthenticated user should access protected API routes;
* frontend-provided workspace ids must not be trusted;
* secrets must not be exposed in logs or frontend code.

### 8.2 Scalability

The architecture should allow future modules to be added without rewriting authentication, tenancy or plan logic.

Future modules include:

* agents;
* knowledge bases;
* conversations;
* inbox;
* pipelines;
* integrations;
* automations.

### 8.3 Maintainability

The code should be simple, explicit and easy to extend.

Avoid:

* premature abstractions;
* over-engineered permission systems;
* hardcoded workspace ids;
* hardcoded plan logic spread across the codebase.

### 8.4 Developer experience

The project should run locally with clear setup instructions.

The development environment should support:

* backend app;
* frontend app;
* PostgreSQL;
* migrations;
* tests.

## 9. Out of scope

This phase does not include:

* AI agents;
* LLM integration;
* knowledge bases;
* RAG;
* file upload;
* website widget;
* inbox;
* conversations;
* contacts;
* pipelines;
* automations;
* WhatsApp;
* integration marketplace;
* public API;
* webhooks;
* real billing integration;
* payment provider integration;
* advanced analytics;
* advanced permissions.

## 10. Success criteria

This phase is successful when:

1. A user can log in.
2. A user can access the authenticated dashboard.
3. The system can identify the current user.
4. The system can identify the current workspace.
5. A workspace has members.
6. A workspace has a plan.
7. A workspace has usage counters.
8. Basic roles exist.
9. Protected API routes reject unauthenticated requests.
10. Tenant isolation is enforced.
11. The frontend displays workspace, members and plan/usage information.
12. Tests confirm that one workspace cannot access another workspace’s data.

## 11. Acceptance criteria

### Authentication

* Unauthenticated users are redirected or blocked from protected pages.
* Authenticated users can access the dashboard.
* API requests without valid authentication are rejected.

### Workspace

* Current workspace can be retrieved.
* Workspace settings can be viewed.
* Workspace data is scoped to the authenticated workspace.

### Members

* Members of the current workspace can be listed.
* Member roles are visible.
* Unauthorized role changes are blocked.

### Plans and usage

* Available plans can be listed.
* Current workspace plan can be viewed.
* Usage counters can be viewed.
* Usage structure is ready for future modules.

### Tenant isolation

* Test data from workspace A cannot be accessed by a user from workspace B.
* API endpoints apply workspace filtering.
* Authorization does not rely on workspace id sent from the frontend.

## 12. Risks

### Risk: overbuilding RBAC

Mitigation:

Start with simple roles and avoid advanced permission matrices.

### Risk: building billing too early

Mitigation:

Create plan and subscription structure only. Do not integrate payments yet.

### Risk: weak tenant isolation

Mitigation:

Add tests early and make workspace context mandatory in protected services.

### Risk: spending too much time on UI

Mitigation:

Create a simple functional dashboard shell. Visual polish comes later.

### Risk: coupling to auth provider too strongly

Mitigation:

Maintain internal user and workspace tables linked to external auth IDs.

## 13. Product decision notes

* Workspaces are the root customer entity.
* All future customer-owned modules must belong to a workspace.
* Plans and limits should exist structurally before billing.
* RBAC should start simple.
* Tenant isolation is more important than UI polish in this phase.
* This phase creates foundation, not the core AI product yet.

## 14. Next phase preview

After this phase, the recommended next phase is:

Phase 2 — Agents Core

Expected scope:

* create agent;
* list agents;
* edit agent;
* activate/deactivate agent;
* configure prompt;
* configure tone/persona;
* choose model;
* test agent in dashboard without RAG initially.
