"""وحدة المبيعات (Sales) — فواتير صبرة تك."""

from app.core.client import get_daftra_client
from app.core.compliance import get_contract
from app.core.permissions import OperationType
from app.core.registry import daftra_tool


@daftra_tool(module="sales", operation=OperationType.READ, contract_key="invoices.list")
def list_invoices(page: int = 1, limit: int = 10) -> dict:
    """جلب قائمة فواتير صبرة تك من دفترة (مع ترقيم الصفحات)."""
    return get_daftra_client().call(
        get_contract("invoices.list"), query={"page": page, "limit": limit}
    )


@daftra_tool(module="sales", operation=OperationType.READ, contract_key="invoices.get")
def get_invoice(invoice_id: int) -> dict:
    """جلب فاتورة واحدة برقمها التعريفي في دفترة."""
    return get_daftra_client().call(
        get_contract("invoices.get"), path_params={"invoice_id": invoice_id}
    )
