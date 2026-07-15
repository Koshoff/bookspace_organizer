"""
Продуктов каталог — четящи endpoint-и над съществуващия db.products слой.
Защитени: изискват валидна сесия (get_current_operator).
"""
from fastapi import APIRouter, Depends

import db
from app.deps import get_current_operator

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/products")
def list_products(operator: dict = Depends(get_current_operator)):
    """Всички артикули с изчислена наличност (наличността е derived — сума от
    движенията, единствен източник на истина)."""
    return db.get_all_products()


@router.get("/products/{isbn}")
def product_by_isbn(isbn: str, operator: dict = Depends(get_current_operator)):
    return db.get_product_for_delivery(isbn)
