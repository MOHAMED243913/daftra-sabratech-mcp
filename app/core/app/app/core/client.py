"""
عميل دفترة الموحد (Daftra HTTP Client)
======================================
الطبقة الوحيدة في المشروع المسموح لها بالاتصال المباشر بـ Daftra API.

القواعد:
- كل طلب يمر عبر عقد (EndpointContract) من طبقة التوافق — لا مسارات حرة.
- رسائل الأخطاء تعاد بالعربية مع كود HTTP الحقيقي دون إخفاء التفاصيل.
- التوافق الخلفي: نفس أسلوب الاتصال في النسخة الأصلية
  (header: apikey ، القاعدة: https://subdomain.daftra.com/api2).
"""

from __future__ import annotations

import logging
import os

import httpx

from app.core.compliance import EndpointContract

logger = logging.getLogger("daftra_mcp.client")


class DaftraAPIError(Exception):
    """خطأ من Daftra API مع رسالة عربية واضحة."""


class DaftraClient:
    def __init__(self, subdomain: str | None = None, apikey: str | None = None):
        # قراءة كسولة من البيئة حتى لا تفشل الاختبارات المحلية بدون مفاتيح.
        self._subdomain = subdomain or os.environ.get("DAFTRA_SUBDOMAIN")
        self._apikey = apikey or os.environ.get("DAFTRA_APIKEY")

    # ------------------------------------------------------------------
    def _ensure_credentials(self) -> None:
        if not self._subdomain or not self._apikey:
            raise DaftraAPIError(
                "بيانات الاتصال ناقصة: تأكد من ضبط متغيري البيئة "
                "DAFTRA_SUBDOMAIN و DAFTRA_APIKEY في Render."
            )

    @property
    def base_url(self) -> str:
        return f"https://{self._subdomain}.daftra.com/api2"

    # ------------------------------------------------------------------
    def call(
        self,
        contract: EndpointContract,
        *,
        path_params: dict | None = None,
        query: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        """تنفيذ طلب وفق عقد رسمي فقط."""
        self._ensure_credentials()

        path = contract.path
        for name in contract.path_params:
            value = (path_params or {}).get(name)
            if value is None:
                raise DaftraAPIError(
                    f"المعامل الإلزامي '{name}' مفقود للعملية {contract.key}."
                )
            path = path.replace("{" + name + "}", str(value))

        url = f"{self.base_url}/{path}"
        headers = {"apikey": self._apikey, "Accept": "application/json"}

        try:
            r = httpx.request(
                contract.method,
                url,
                headers=headers,
                params=query,
                json=json_body,
                timeout=30,
            )
        except httpx.RequestError as exc:
            logger.error("فشل الاتصال بدفترة: %s", exc)
            raise DaftraAPIError(
                "تعذر الاتصال بخادم دفترة. تحقق من الإنترنت أو من صحة النطاق الفرعي."
            ) from exc

        if r.status_code == 401:
            raise DaftraAPIError(
                "رفض المصادقة (401): مفتاح API غير صالح أو تم تجديده في دفترة. "
                "حدّث DAFTRA_APIKEY في Render."
            )
        if r.status_code == 403:
            raise DaftraAPIError("صلاحيات غير كافية على مستوى حساب دفترة (403).")
        if r.status_code == 404:
            raise DaftraAPIError(f"السجل المطلوب غير موجود (404): {contract.key}.")
        if r.status_code >= 400:
            raise DaftraAPIError(f"خطأ من دفترة ({r.status_code}): {r.text[:300]}")

        return r.json()


# نسخة واحدة مشتركة (Singleton) لكل الخادم.
_client: DaftraClient | None = None


def get_daftra_client() -> DaftraClient:
    global _client
    if _client is None:
        _client = DaftraClient()
    return _client
