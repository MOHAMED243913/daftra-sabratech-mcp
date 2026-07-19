"""
محرك الصلاحيات (Permission & Role Engine)
=========================================
طبقة تحقق مستقلة تنفذ قبل أي Tool.

حقيقة هندسية موثقة عمدًا:
مفتاح API في دفترة يمنح صلاحيات الحساب كاملة، لذا هذه الطبقة "ذاتية الفرض"
داخل الخادم — تنظم ما يسمح لهذا الخادم بتنفيذه، ولا تعدل صلاحيات دفترة نفسها.

القواعد:
- لا يستدعى API إطلاقًا قبل نجاح التحقق.
- الرفض يعيد رسالة عربية واضحة بالسبب.
- كل محاولة مرفوضة تسجل في نظام Logging.
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("daftra_mcp.permissions")


class OperationType(str, Enum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    CANCEL = "cancel"
    EXPORT = "export"
    REPORT = "report"
    ANALYSIS = "analysis"
    WORKFLOW = "workflow"


ROLE_LABELS_AR = {
    "admin": "مدير النظام",
    "operator": "مشغل",
    "viewer": "قارئ فقط",
}

# سياسة الأدوار: أي دور غير معروف = صلاحيات القراءة فقط (أمان افتراضي).
ROLE_POLICIES: dict[str, set[OperationType]] = {
    "admin": set(OperationType),
    "operator": {
        OperationType.READ,
        OperationType.CREATE,
        OperationType.UPDATE,
        OperationType.REPORT,
        OperationType.EXPORT,
        OperationType.WORKFLOW,
    },
    "viewer": {OperationType.READ, OperationType.REPORT},
}


class PermissionDeniedError(Exception):
    """ترفع عند رفض العملية — رسالتها عربية وتعاد للمستخدم كما هي."""


class PermissionEngine:
    def __init__(self, role: str = "admin"):
        self.role = role if role in ROLE_POLICIES else "viewer"
        if role not in ROLE_POLICIES:
            logger.warning(
                "الدور '%s' غير معروف — تم تخفيضه تلقائيًا إلى 'viewer' للأمان.", role
            )

    def allowed_operations(self) -> set[OperationType]:
        return ROLE_POLICIES[self.role]

    def check(self, *, tool_name: str, module: str, operation: OperationType) -> None:
        """يرفع PermissionDeniedError عند عدم توفر الصلاحية — قبل أي استدعاء API."""
        if operation in self.allowed_operations():
            return
        role_ar = ROLE_LABELS_AR.get(self.role, self.role)
        logger.warning(
            "محاولة وصول مرفوضة | الأداة=%s | الوحدة=%s | العملية=%s | الدور=%s",
            tool_name,
            module,
            operation.value,
            self.role,
        )
        raise PermissionDeniedError(
            f"تم رفض العملية: الدور الحالي للخادم ({role_ar}) لا يملك صلاحية "
            f"'{operation.value}' على وحدة '{module}'. "
            "لتغيير الدور: عدّل متغير البيئة DAFTRA_ROLE في Render "
            "(القيم المتاحة: admin / operator / viewer)."
        )
