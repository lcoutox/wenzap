from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.config import settings
from app.routers import (
    agents,
    ai_models,
    auth,
    channels,
    contacts,
    conversations,
    health,
    knowledge_bases,
    me,
    members,
    onboarding,
    plans,
    public_widgets,
    whatsapp_webhooks,
    workspaces,
)

app = FastAPI(title="Nexbrain API", version="0.1.0")

# ── CORS ──────────────────────────────────────────────────────────────────────
# Authenticated routes: restrict to configured origins (e.g. the dashboard).
# Public widget routes (/public/widgets/*): open to any origin because the
# widget may be embedded on any customer site. Per-channel origin enforcement
# is handled in the service layer via allowed_origins + is_origin_allowed().
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_PUBLIC_WIDGET_PREFIX = "/public/widgets"

@app.middleware("http")
async def public_widget_cors(request: Request, call_next) -> Response:
    """
    Add permissive CORS headers for public widget endpoints.
    These endpoints are intentionally open — the service layer enforces
    per-channel origin restrictions via allowed_origins.
    """
    response: Response = await call_next(request)
    if request.url.path.startswith(_PUBLIC_WIDGET_PREFIX):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Session-Token"
    return response

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(workspaces.router)
app.include_router(members.router)
app.include_router(plans.router)
app.include_router(agents.router)
app.include_router(knowledge_bases.router)
app.include_router(ai_models.router)
app.include_router(channels.router)
app.include_router(public_widgets.router)
app.include_router(contacts.router)
app.include_router(conversations.router)
app.include_router(onboarding.router)
app.include_router(whatsapp_webhooks.router)
