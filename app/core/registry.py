"""
سجل أدوات MCP مع الاكتشاف التلقائي (Tool Registry + Auto Discovery)
===================================================================
النظام المركزي لإدارة جميع الأدوات.

القواعد المنفذة:
1. اكتشاف تلقائي لكل الوحدات داخل app/modules عند بدء التشغيل.
2. إضافة Tool جديدة = ملف/دالة داخل وحدتها فقط، دون تعديل أي جزء آخر.
3. تصنيف حسب الوحدة ونوع العملية.
4. تعطيل أي أداة عبر config/tools_config.json دون لمس الكود.
5. رفض الأسماء المكررة والأدوات بدون وصف أو بعقد API غير مسجل.
6. سجل داخلي كامل (اسم، وصف، وحدة، صلاحيات، Endpoint، إصدار API، حالة).
7. تغليف كل أداة تلقائيًا: تحقق الصلاحيات ثم تنفيذ ثم تحديث السياق ثم Logging.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable

from app.core import compliance
from app.core.compliance import UnsupportedOperationError
from app.core.config import Settings
from app.core.context import get_context
from app.core.permissions import OperationType, PermissionDeniedError, PermissionEngine

logger = logging.getLogger("daftra_mcp.registry")


class ToolStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPERIMENTAL = "experimental"


@dataclass
class ToolSpec:
    name: str
    description: str
    module: str                     # customers / sales / inventory / system
    operation: OperationType
    contract_key: str | None        # مفتاح عقد Daftra API (None لأدوات النظام)
    permissions: tuple[str, ...]
    status: ToolStatus
    func: Callable
    endpoint: str = ""
    api_version: str = ""
    doc_url: str = ""
    notes: str = ""
    errors: list[str] = field(default_factory=list)


# سجل تعريفات دائم يملؤه الـ decorator عند استيراد الوحدات (لا يُمسح أبدًا،
# حتى تعمل إعادة الاكتشاف في الاختبارات وإعادة التشغيل بشكل صحيح).
_REGISTERED_SPECS: list[ToolSpec] = []


def daftra_tool(
    *,
    module: str,
    operation: OperationType,
    contract_key: str | None = None,
    permissions: tuple[str, ...] = (),
    status: ToolStatus = ToolStatus.ACTIVE,
):
    """تسجيل أداة داخل وحدتها فقط — الاكتشاف والتحقق يتمان مركزيًا."""

    def decorator(func: Callable) -> Callable:
        _REGISTERED_SPECS.append(
            ToolSpec(
                name=func.__name__,
                description=(func.__doc__ or "").strip(),
                module=module,
                operation=operation,
                contract_key=contract_key,
                permissions=permissions or (operation.value,),
                status=status,
                func=func,
            )
        )
        return func

    return decorator


class ToolRegistry:
    def __init__(self, mcp, permission_engine: PermissionEngine, settings: Settings):
        self.mcp = mcp
        self.permissions = permission_engine
        self.settings = settings
        self.tools: dict[str, ToolSpec] = {}
        self.skipped: list[ToolSpec] = []

    # ------------------------------------------------------------------
    def discover(self, package: str = "app.modules") -> None:
        """استيراد كل الوحدات تلقائيًا ثم التحقق والتسجيل."""
        pkg = importlib.import_module(package)
        for modinfo in pkgutil.iter_modules(pkg.__path__, prefix=f"{package}."):
            importlib.import_module(modinfo.name)
            logger.info("تم اكتشاف الوحدة: %s", modinfo.name)

        import dataclasses

        for master in _REGISTERED_SPECS:
            # نسخة مستقلة لكل سجل حتى لا تتلوث التعريفات الأصلية.
            self._validate_and_register(dataclasses.replace(master, errors=[]))

        logger.info(
            "اكتمل التسجيل: %d أداة نشطة، %d مستبعدة.",
            len(self.tools),
            len(self.skipped),
        )

    # ------------------------------------------------------------------
    def _validate_and_register(self, spec: ToolSpec) -> None:
        # 1) وصف إلزامي.
        if not spec.description:
            spec.errors.append("الأداة بلا وصف (docstring) — مرفوضة.")
        # 2) منع التكرار.
        if spec.name in self.tools:
            spec.errors.append(f"اسم مكرر: {spec.name} مسجل مسبقًا.")
        # 3) التحقق من عقد Daftra API إن وجد.
        if spec.contract_key is not None:
            try:
                contract = compliance.get_contract(spec.contract_key)
                spec.endpoint = f"{contract.method} /api2/{contract.path}"
                spec.api_version = contract.api_version
                spec.doc_url = contract.doc_url
                spec.notes = contract.notes
            except UnsupportedOperationError as exc:
                spec.errors.append(str(exc))
        # 4) التعطيل عبر الإعدادات.
        if spec.name in self.settings.disabled_tools:
            spec.status = ToolStatus.DISABLED

        if spec.errors:
            self.skipped.append(spec)
            logger.error("رفض تسجيل الأداة %s: %s", spec.name, "; ".join(spec.errors))
            return
        if spec.status == ToolStatus.DISABLED:
            self.skipped.append(spec)
            logger.info("الأداة %s معطلة عبر الإعدادات — لن تسجل.", spec.name)
            return

        wrapped = self._wrap(spec)
        self.mcp.tool(name=spec.name, description=spec.description)(wrapped)
        self.tools[spec.name] = spec

    # ------------------------------------------------------------------
    def _wrap(self, spec: ToolSpec) -> Callable:
        """تغليف موحد: صلاحيات ثم تنفيذ ثم تحديث سياق ثم Logging."""

        @wraps(spec.func)
        def wrapper(*args: Any, **kwargs: Any):
            try:
                self.permissions.check(
                    tool_name=spec.name, module=spec.module, operation=spec.operation
                )
            except PermissionDeniedError as exc:
                return {"success": False, "error": str(exc)}

            logger.info("تنفيذ الأداة %s | الوحدة=%s", spec.name, spec.module)
            try:
                result = spec.func(*args, **kwargs)
            except Exception as exc:
                logger.exception("فشل تنفيذ الأداة %s", spec.name)
                return {"success": False, "error": str(exc)}

            bound = inspect.signature(spec.func).bind_partial(*args, **kwargs)
            get_context().auto_record(
                module=spec.module, tool_name=spec.name, kwargs=dict(bound.arguments)
            )
            return result

        # الحفاظ على التوقيع الأصلي حتى يبني FastMCP مخطط المعاملات الصحيح.
        wrapper.__signature__ = inspect.signature(spec.func)
        return wrapper

    # ------------------------------------------------------------------
    def catalog(self) -> list[dict]:
        """السجل الداخلي الكامل — يعرض عبر أداة registry_catalog."""
        rows = []
        for spec in list(self.tools.values()) + self.skipped:
            rows.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "module": spec.module,
                    "operation": spec.operation.value,
                    "permissions": list(spec.permissions),
                    "endpoint": spec.endpoint or "داخلي (بدون API)",
                    "api_version": spec.api_version or "-",
                    "doc_url": spec.doc_url or "-",
                    "status": spec.status.value,
                    "errors": spec.errors,
                }
            )
        return rows


# مرجع عالمي يضبط في server.py ليصل إليه tool الكتالوج.
active_registry: ToolRegistry | None = None
