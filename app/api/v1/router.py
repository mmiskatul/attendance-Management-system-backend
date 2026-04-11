"""Aggregate API v1 routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import admin, attendance, auth, faces, health, students


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(students.router)
api_router.include_router(faces.router)
api_router.include_router(attendance.router)
api_router.include_router(health.router)
api_router.include_router(admin.router)
