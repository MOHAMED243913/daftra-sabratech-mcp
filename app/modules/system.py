"""وحدة النظام (System) — أدوات داخلية: الكتالوج، السياق، إعادة التعيين."""

from app.core import registry as registry_module
from app.core.context import CONTEXT_FIELDS, get_context
from app.core.permissions import OperationType
from app.core.registry import daftra_tool


@daftra_tool(module="system", operation=OperationType.READ, contract_key=None)
def registry_catalog() -> list[dict]:
    """عرض السجل الداخلي الكامل لأدوات الخادم: الاسم، الوحدة، نوع العملية، الـ Endpoint، إصدار API، الحالة، وأي أدوات مستبعدة مع أسباب استبعادها."""
    reg = registry_module.active_registry
    if reg is None:
        return [{"error": "السجل غير مهيأ بعد."}]
    return reg.catalog()


@daftra_tool(module="system", operation=OperationType.READ, contract_key=None)
def show_context() -> dict:
    """عرض السياق الحالي للجلسة: العميل الحالي، الفاتورة الحالية، المنتج الحالي، وغيرها من الكيانات النشطة."""
    return get_context().snapshot()


@daftra_tool(module="system", operation=OperationType.UPDATE, contract_key=None)
def set_context(field: str, value: str) -> dict:
    """ضبط حقل في سياق الجلسة يدويًا. الحقول المتاحة: current_client_id, current_invoice_id, current_product_id, current_estimate_id, current_project, current_branch, current_period, current_currency, last_search, last_report, last_file."""
    try:
        get_context().set(field, value)
        return {"success": True, "message": f"تم ضبط {field} = {value}"}
    except ValueError as exc:
        return {"success": False, "error": str(exc), "available_fields": list(CONTEXT_FIELDS)}


@daftra_tool(module="system", operation=OperationType.UPDATE, contract_key=None)
def reset_context(field: str | None = None) -> dict:
    """إعادة تعيين السياق: مرر اسم حقل واحد لإعادة تعيينه فقط، أو اتركه فارغًا لمسح السياق بالكامل."""
    return {"success": True, "message": get_context().reset(field)}
