"""وحدة العملاء (Customers) — أدوات القراءة المطابقة للنسخة الأصلية."""

from app.core.client import get_daftra_client
from app.core.compliance import get_contract
from app.core.permissions import OperationType
from app.core.registry import daftra_tool


@daftra_tool(module="customers", operation=OperationType.READ, contract_key="clients.list")
def list_clients(page: int = 1, limit: int = 10) -> dict:
    """جلب قائمة عملاء صبرة تك من دفترة (مع ترقيم الصفحات)."""
    return get_daftra_client().call(
        get_contract("clients.list"), query={"page": page, "limit": limit}
    )


@daftra_tool(module="customers", operation=OperationType.READ, contract_key="clients.get")
def get_client(client_id: int) -> dict:
    """جلب بيانات عميل واحد برقمه التعريفي في دفترة."""
    return get_daftra_client().call(
        get_contract("clients.get"), path_params={"client_id": client_id}
    )
