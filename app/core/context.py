"""
محرك الذاكرة والسياق (Conversation Context Engine)
==================================================
طبقة خفيفة تحفظ "الكيانات النشطة" أثناء الجلسة حتى تعمل الأوامر المترابطة
("نفس العميل"، "الفاتورة الأخيرة") دون إعادة إدخال البيانات.

قرار معماري موثق:
- فهم اللغة الطبيعية (هذا/السابق/نفس العميل) مسؤولية النموذج (Claude) —
  دور هذه الطبقة توفير قيم الكيانات الحالية له عبر أداة show_context.
- التخزين في الذاكرة (In-Memory): على خطة Render المجانية ينام الخادم بعد
  فترة خمول فيفقد السياق — قيد معروف وموثق، وحله الترقية للخطة
  المدفوعة أو تخزين خارجي في مرحلة لاحقة.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("daftra_mcp.context")

# الحقول المدعومة في السياق (حسب مواصفات المشروع).
CONTEXT_FIELDS = (
    "current_client_id",
    "current_project",
    "current_estimate_id",
    "current_invoice_id",
    "current_product_id",
    "current_branch",
    "current_period",
    "current_currency",
    "last_search",
    "last_report",
    "last_file",
)


class ConversationContext:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._updated_at: str | None = None

    # ------------------------------------------------------------------
    def set(self, field: str, value: Any) -> None:
        if field not in CONTEXT_FIELDS:
            raise ValueError(f"حقل سياق غير معروف: {field}")
        self._data[field] = value
        self._updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        logger.info("تحديث السياق | %s = %s", field, value)

    def get(self, field: str, default: Any = None) -> Any:
        return self._data.get(field, default)

    def reset(self, field: str | None = None) -> str:
        """إعادة تعيين حقل واحد أو السياق كاملًا."""
        if field:
            self._data.pop(field, None)
            return f"تمت إعادة تعيين الحقل: {field}"
        self._data.clear()
        return "تمت إعادة تعيين السياق بالكامل."

    def snapshot(self) -> dict:
        return {
            "context": dict(self._data),
            "updated_at": self._updated_at,
            "note": (
                "السياق يعيش في ذاكرة الخادم؛ على خطة Render المجانية يفقد "
                "عند نوم الخادم بعد فترة خمول."
            ),
        }

    # ------------------------------------------------------------------
    def auto_record(self, *, module: str, tool_name: str, kwargs: dict) -> None:
        """تحديث تلقائي للكيانات النشطة بعد نجاح أداة — دون منطق لغوي."""
        mapping = {
            "client_id": "current_client_id",
            "invoice_id": "current_invoice_id",
            "product_id": "current_product_id",
            "estimate_id": "current_estimate_id",
        }
        for arg, field in mapping.items():
            if arg in kwargs and kwargs[arg] is not None:
                self.set(field, kwargs[arg])


# نسخة واحدة مشتركة للخادم (خادم شخصي أحادي المستخدم — قرار موثق).
_context: ConversationContext | None = None


def get_context() -> ConversationContext:
    global _context
    if _context is None:
        _context = ConversationContext()
    return _context
