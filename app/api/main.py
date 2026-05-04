from fastapi import FastAPI
from app.api.routes.insights import router as insights_router
from app.db.models import init_db

app = FastAPI(
    title="Retail Insight AI",
    description="AI-powered retail analytics insight generation",
    version="0.2.0",
)

@app.on_event("startup")
def startup():
    init_db()

app.include_router(insights_router)

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.2.0"}