from fastapi import APIRouter

from api.endpoints.api_service import router
from api.endpoints.ha_integration import router as ha_router

main_router = APIRouter()

main_router.include_router(router)
main_router.include_router(ha_router)
