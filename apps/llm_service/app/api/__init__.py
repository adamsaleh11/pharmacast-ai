from fastapi import APIRouter

from apps.llm_service.app.api.chat import router as chat_router
from apps.llm_service.app.api.explain import router as explain_router
from apps.llm_service.app.api.purchase_order import router as purchase_order_router


router = APIRouter(prefix="/llm")
router.include_router(explain_router)
router.include_router(chat_router)
router.include_router(purchase_order_router)
