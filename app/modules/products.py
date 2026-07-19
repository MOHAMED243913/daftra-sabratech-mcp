"""وحدة المخزون (Inventory) — منتجات وخدمات صبرة تك."""

from app.core.client import get_daftra_client
from app.core.compliance import get_contract
from app.core.permissions import OperationType
from app.core.registry import daftra_tool


@daftra_tool(module="inventory", operation=OperationType.READ, contract_key="products.list")
def list_products(page: int = 1, limit: int = 10) -> dict:
    """جلب قائمة المنتجات/الخدمات من دفترة (مع ترقيم الصفحات). الكتالوج يتجاوز 280 صنفًا موزعة على 6 صفحات — للبحث الشامل مرّ على جميع الصفحات."""
    return get_daftra_client().call(
        get_contract("products.list"), query={"page": page, "limit": limit}
    )
