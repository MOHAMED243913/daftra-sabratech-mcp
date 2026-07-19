"""
إعدادات المشروع (Settings)
==========================
تُقرأ من متغيرات البيئة أولًا، ثم من config/tools_config.json إن وجد
(لتعطيل أدوات أو ضبط الدور دون تعديل الكود).

متغيرات البيئة:
- DAFTRA_SUBDOMAIN : النطاق الفرعي لحساب دفترة (كلمة واحدة، بدون نقاط).
- DAFTRA_APIKEY    : مفتاح API من دفترة.
- DAFTRA_ROLE      : دور الخادم (admin / operator / viewer). الافتراضي: admin.
- PORT             : منفذ التشغيل (يضبطه Render تلقائيًا).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parents[2] / "config" / "tools_config.json"


@dataclass
class Settings:
    role: str = "admin"
    disabled_tools: set[str] = field(default_factory=set)

    @classmethod
    def load(cls) -> "Settings":
        data: dict = {}
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # ملف إعدادات تالف لا يجوز أن يمنع تشغيل الخادم — نتجاهله مع تحذير.
                import logging

                logging.getLogger("daftra_mcp").warning(
                    "ملف الإعدادات config/tools_config.json غير صالح JSON — تم تجاهله."
                )
        role = os.environ.get("DAFTRA_ROLE") or data.get("role") or "admin"
        disabled = set(data.get("disabled_tools", []))
        return cls(role=role, disabled_tools=disabled)


def setup_logging() -> None:
    """تهيئة Logging موحدة لكل المشروع."""
    import logging

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
