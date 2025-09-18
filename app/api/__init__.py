from fastapi import APIRouter
from . import scraping, admin, words

api_router = APIRouter()
api_router.include_router(scraping.router)
api_router.include_router(admin.router)
api_router.include_router(words.router)