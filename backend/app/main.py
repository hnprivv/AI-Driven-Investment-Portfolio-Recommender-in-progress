"""AIPRS API — FastAPI backend.

Skeleton for the React migration: currently exposes just the auth flow
(login/me/logout) so the new frontend can be proven end-to-end before the
rest of the pages are ported over. The existing Streamlit app keeps running
unchanged during the migration.
"""
import os

from dotenv import load_dotenv

# Must run before any other `app.*` import — several modules (app.auth in
# particular) read os.getenv(...) at module-import time, so .env has to be
# loaded before those imports happen, not just before they're first called.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, market, portfolio, recommendations, users

app = FastAPI(title="AIPRS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],  # Vite dev server + preview build
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
app.include_router(market.router, prefix="/market", tags=["market"])


@app.get("/health")
def health():
    return {"status": "ok"}
