"""
Health / readiness endpoint (FastAPI).
"""
from fastapi import FastAPI
from app.config import config

health_app = FastAPI(title="Taxonomy Worker Health")


@health_app.get("/health")
def health():
    return {"status": "UP", "service": "taxonomy-worker"}
