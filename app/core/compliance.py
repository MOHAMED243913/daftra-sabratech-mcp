"""
طبقة التحقق من توافق واجهة برمجة دفترة (Daftra API Compliance Layer)
====================================================================
مصدر الحقيقة الوحيد لجميع الـ Endpoints المسموح باستخدامها في المشروع.

القاعدة الإلزامية:
- لا يجوز لأي Tool استدعاء API إلا عبر عقد (Contract) مسجل هنا.
- كل عقد يشير إلى التوثيق الرسمي: https://docs.daftara.dev
- أي عملية غير موجودة هنا تعتبر "غير مدعومة رسميًا" ويرفضها النظام
  برسالة عربية واضحة بدلًا من اختراع Endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


DOCS_BASE = "https://docs.daftara.dev"


class SupportLevel(str, Enum):
    FULL = "full"          # مدعومة بالكامل ومختبرة على حساب صبرة تك
    PARTIAL = "partial"    # مدعومة رسميًا لكن غير مختبرة بعد
    UNSUPPORTED = "unsupported"


class UnsupportedOperationError(Exception):
    """تُرفع عند محاولة استخدام عملية غير موثقة رسميًا في Daftra API."""

    def __init__(self, contract_key: str):
        self.contract_key = contract_key
        super().__init__(
            f"العملية '{contract_key}' غير مسجلة في طبقة التوافق مع Daftra API. "
            "لا يسمح النظام باختراع Endpoints غير موثقة رسميًا. "
            f"راجع التوثيق الرسمي: {DOCS_BASE}"
        )


@dataclass(frozen=True)
class EndpointContract:
    """عقد رسمي لعملية واحدة في Daftra API."""

    key: str                 # معرف داخلي، مثال: "clients.list"
    method: str              # GET / POST / PUT / DELETE
    path: str                # المسار بعد /api2/ ، مثال: "clients"
    api_version: str         # "v2"
    doc_url: str             # رابط صفحة التوثيق الرسمي
    support: SupportLevel    # مستوى الدعم
    notes: str = ""          # قيود أو ملاحظات خاصة بالعملية
    path_params: tuple[str, ...] = field(default_factory=tuple)


_CONTRACTS: dict[str, EndpointContract] = {}


def _register(contract: EndpointContract) -> None:
    if contract.key in _CONTRACTS:
        raise ValueError(f"عقد مكرر في طبقة التوافق: {contract.key}")
    _CONTRACTS[contract.key] = contract


for _c in [
    EndpointContract(
        key="clients.list",
        method="GET",
        path="clients",
        api_version="v2",
        doc_url=f"{DOCS_BASE}/",
        support=SupportLevel.FULL,
        notes="تدعم pagination عبر page و limit. مختبرة على حساب صبرة تك.",
    ),
    EndpointContract(
        key="clients.get",
        method="GET",
        path="clients/{client_id}",
        api_version="v2",
        doc_url=f"{DOCS_BASE}/",
        support=SupportLevel.FULL,
        path_params=("client_id",),
    ),
    EndpointContract(
        key="invoices.list",
        method="GET",
        path="invoices",
        api_version="v2",
        doc_url=f"{DOCS_BASE}/",
        support=SupportLevel.FULL,
        notes="تدعم pagination عبر page و limit.",
    ),
    EndpointContract(
        key="invoices.get",
        method="GET",
        path="invoices/{invoice_id}",
        api_version="v2",
        doc_url=f"{DOCS_BASE}/",
        support=SupportLevel.FULL,
        path_params=("invoice_id",),
    ),
    EndpointContract(
        key="products.list",
        method="GET",
        path="products",
        api_version="v2",
        doc_url=f"{DOCS_BASE}/",
        support=SupportLevel.FULL,
        notes=(
            "الكتالوج الحالي لصبرة تك يتجاوز 280 منتجًا موزعة على 6 صفحات "
            "بحد 50 عنصرًا للصفحة — البحث الكامل يتطلب المرور على جميع الصفحات."
        ),
    ),
]:
    _register(_c)


def get_contract(key: str) -> EndpointContract:
    """إرجاع العقد الرسمي أو رفع خطأ واضح إن لم تكن العملية مدعومة."""
    contract = _CONTRACTS.get(key)
    if contract is None or contract.support == SupportLevel.UNSUPPORTED:
        raise UnsupportedOperationError(key)
    return contract


def all_contracts() -> list[EndpointContract]:
    return list(_CONTRACTS.values())
