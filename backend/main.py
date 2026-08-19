"""
backend/main.py - LeadStrategus Event Intelligence Agent (slim).

The whole event pipeline now lives in ONE call: /api/search →
gpt_search.run_gpt_event_search() → ChatGPT real web search → top-6
verified events. The only other real endpoint is /api/email-report.
Everything else is a stub kept so the unchanged frontend never breaks.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from config import get_settings
from api.routes_search import router as search_router
from api.routes_email import router as email_router

settings = get_settings()

app = FastAPI(
    title="LeadStrategus Event Intelligence API",
    description="ICP → top-6 verified events via ChatGPT web search",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Maintenance-mode kill switch - same contract the frontend already
# relies on (App.jsx checks /api/maintenance-status before rendering).
_MAINTENANCE_EXEMPT_PATHS = {"/health", "/api/maintenance-status"}


@app.middleware("http")
async def _maintenance_gate(request: Request, call_next):
    if (
        settings.maintenance_mode
        and request.method != "OPTIONS"
        and request.url.path not in _MAINTENANCE_EXEMPT_PATHS
    ):
        return JSONResponse(
            status_code=503,
            content={
                "maintenance": True,
                "message": settings.maintenance_message or "We're doing some quick maintenance - back shortly.",
            },
        )
    return await call_next(request)


app.include_router(search_router, prefix="/api", tags=["search"])
app.include_router(email_router,  prefix="/api", tags=["email"])
logger.info("Slim backend up: /api/search (GPT web search) + /api/email-report")


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
