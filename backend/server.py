from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import logging
import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core.database import client
from core.ws import ws_router
from routers import (
    auth, dashboard, escalations, feeds, incidents, notifications,
    predictions, reports, roads, routing, trips, vehicles,
)
from seed import seed_dashboard, seed_users

logger = logging.getLogger("neris")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="NERIS API")

for module in (auth, dashboard, escalations, feeds, incidents, notifications, predictions, reports, roads, routing, trips, vehicles):
    app.include_router(module.router, prefix="/api")
app.include_router(ws_router, prefix="/api")


@app.on_event("startup")
async def on_startup():
    await seed_users()
    logger.info("NERIS: users seeded (owner + demo accounts)")
    await seed_dashboard()
    logger.info("NERIS: dashboard demo dataset ready")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
