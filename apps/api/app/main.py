from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import agents, ai_models, health, knowledge_bases, me, members, plans, workspaces

app = FastAPI(title="Nexbrain API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(me.router)
app.include_router(workspaces.router)
app.include_router(members.router)
app.include_router(plans.router)
app.include_router(agents.router)
app.include_router(knowledge_bases.router)
app.include_router(ai_models.router)
