"""
خادم MCP لربط Claude مع دفترة — حساب صبرة تك
Daftra MCP Server for Sabra Tech (المعمارية الموسعة v2)

نقطة الدخول الوحيدة: تهيئة Logging ثم تحميل الإعدادات ثم محرك الصلاحيات
ثم السجل مع الاكتشاف التلقائي ثم تشغيل FastMCP.

متغيرات البيئة المطلوبة:
- DAFTRA_SUBDOMAIN : النطاق الفرعي (كلمة واحدة).
- DAFTRA_APIKEY    : مفتاح API من دفترة.
- DAFTRA_ROLE      : اختياري (admin / operator / viewer) — الافتراضي admin.
"""

import os

from fastmcp import FastMCP

from app.core import registry as registry_module
from app.core.config import Settings, setup_logging
from app.core.permissions import PermissionEngine
from app.core.registry import ToolRegistry

setup_logging()
settings = Settings.load()

mcp = FastMCP("Daftra-SabraTech")

registry = ToolRegistry(mcp, PermissionEngine(settings.role), settings)
registry_module.active_registry = registry
registry.discover("app.modules")

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )
