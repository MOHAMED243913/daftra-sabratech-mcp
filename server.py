"""
Daftra SabraTech MCP Server — Full CRUD
========================================
خادم MCP كامل الصلاحيات (قراءة / إنشاء / تعديل / حذف) لحساب دفترة الخاص بصبرة تك.

المتغيرات البيئية المطلوبة:
    DAFTRA_SUBDOMAIN  -> النطاق الفرعي لحسابك في دفترة
    DAFTRA_APIKEY     -> مفتاح API من دفترة
"""

import os
import json
import httpx
from fastmcp import FastMCP

SUBDOMAIN = os.environ.get("DAFTRA_SUBDOMAIN", "")
APIKEY = os.environ.get("DAFTRA_APIKEY", "")
BASE_URL = f"https://{SUBDOMAIN}.daftra.com/api2"

HEADERS = {
    "APIKEY": APIKEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

mcp = FastMCP("Daftra SabraTech — Full CRUD")


def _request(method: str, endpoint: str, params: dict | None = None,
             body: dict | None = None) -> dict:
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.request(method, url, headers=HEADERS,
                                  params=params, json=body)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        return {"status_code": resp.status_code, "data": data}
    except Exception as e:
        return {"status_code": 0, "error": str(e)}


RESOURCES = {
    "clients":            ("clients", "Client"),
    "suppliers":          ("suppliers", "Supplier"),
    "products":           ("products", "Product"),
    "invoices":           ("invoices", "Invoice"),
    "estimates":          ("estimates", "Invoice"),
    "purchase_invoices":  ("purchase_invoices", "Invoice"),
    "refund_receipts":    ("refund_receipts", "Invoice"),
    "expenses":           ("expenses", "Expense"),
    "incomes":            ("incomes", "Income"),
    "invoice_payments":   ("invoice_payments", "InvoicePayment"),
    "journals":           ("journals", "Journal"),
    "treasuries":         ("treasuries", "Treasury"),
    "stock_transactions": ("stock_transactions", "StockTransaction"),
    "appointments":       ("appointments", "Appointment"),
    "notes":              ("notes", "Note"),
    "staff":              ("staffs", "Staff"),
    "work_orders":        ("work_orders", "WorkOrder"),
}


def _resolve(resource: str):
    r = resource.strip().lower()
    if r not in RESOURCES:
        return None, {
            "error": f"المورد '{resource}' غير مدعوم.",
            "الموارد_المتاحة": list(RESOURCES.keys()),
        }
    return RESOURCES[r], None


@mcp.tool()
def daftra_list(resource: str, page: int = 1, limit: int = 20,
                filters: str = "") -> str:
    """جلب قائمة من أي مورد في دفترة.
    resource: clients, suppliers, products, invoices, estimates,
    purchase_invoices, refund_receipts, expenses, incomes,
    invoice_payments, journals, treasuries, stock_transactions,
    appointments, notes, staff, work_orders.
    filters: نص JSON اختياري، مثال: {"client_id": 31}
    """
    res, err = _resolve(resource)
    if err:
        return json.dumps(err, ensure_ascii=False)
    endpoint, _ = res
    params = {"page": page, "limit": limit}
    if filters:
        try:
            params.update(json.loads(filters))
        except json.JSONDecodeError:
            return json.dumps({"error": "filters ليست JSON صالح"},
                              ensure_ascii=False)
    return json.dumps(_request("GET", endpoint, params=params),
                      ensure_ascii=False)


@mcp.tool()
def daftra_get(resource: str, record_id: int) -> str:
    """جلب سجل واحد بالتفصيل من أي مورد في دفترة برقمه (ID)."""
    res, err = _resolve(resource)
    if err:
        return json.dumps(err, ensure_ascii=False)
    endpoint, _ = res
    return json.dumps(_request("GET", f"{endpoint}/{record_id}"),
                      ensure_ascii=False)


@mcp.tool()
def daftra_create(resource: str, data: str) -> str:
    """إنشاء سجل جديد في أي مورد في دفترة.
    data: نص JSON بحقول السجل (غلاف الـ Model يُضاف تلقائيًا).
    مثال لعرض سعر (estimates): {"client_id": 31, "date": "2026-07-19",
      "InvoiceItem": [{"description": "توريد وتركيب قفل باب غرفة تبريد",
                       "unit_price": 450, "quantity": 1, "tax1": 15}]}
    """
    res, err = _resolve(resource)
    if err:
        return json.dumps(err, ensure_ascii=False)
    endpoint, model = res
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"data ليست JSON صالح: {e}"},
                          ensure_ascii=False)
    body = payload if model in payload else {model: payload}
    return json.dumps(_request("POST", endpoint, body=body),
                      ensure_ascii=False)


@mcp.tool()
def daftra_update(resource: str, record_id: int, data: str) -> str:
    """تعديل سجل موجود. data: نص JSON بالحقول المراد تغييرها فقط."""
    res, err = _resolve(resource)
    if err:
        return json.dumps(err, ensure_ascii=False)
    endpoint, model = res
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"data ليست JSON صالح: {e}"},
                          ensure_ascii=False)
    body = payload if model in payload else {model: payload}
    return json.dumps(_request("PUT", f"{endpoint}/{record_id}", body=body),
                      ensure_ascii=False)


@mcp.tool()
def daftra_delete(resource: str, record_id: int, confirm: bool = False) -> str:
    """حذف سجل — نهائي ولا يمكن التراجع. يتطلب confirm=True بعد تأكيد المستخدم."""
    if not confirm:
        return json.dumps({
            "warning": "الحذف نهائي. أعد الاستدعاء بـ confirm=True بعد تأكيد المستخدم.",
            "resource": resource, "record_id": record_id,
        }, ensure_ascii=False)
    res, err = _resolve(resource)
    if err:
        return json.dumps(err, ensure_ascii=False)
    endpoint, _ = res
    return json.dumps(_request("DELETE", f"{endpoint}/{record_id}"),
                      ensure_ascii=False)


@mcp.tool()
def create_estimate(client_id: int, items: str, date: str = "",
                    notes: str = "", draft: bool = False) -> str:
    """إنشاء عرض سعر مبسط.
    items: نص JSON قائمة بنود:
      [{"description": "...", "unit_price": 450, "quantity": 1, "tax1": 15}]
    """
    try:
        items_list = json.loads(items)
        if not isinstance(items_list, list):
            raise ValueError("items يجب أن تكون قائمة")
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"error": f"items غير صالحة: {e}"},
                          ensure_ascii=False)
    invoice = {
        "client_id": client_id,
        "draft": 1 if draft else 0,
        "is_offline": 1,
        "InvoiceItem": items_list,
    }
    if date:
        invoice["date"] = date
    if notes:
        invoice["notes"] = notes
    return json.dumps(_request("POST", "estimates", body={"Invoice": invoice}),
                      ensure_ascii=False)


@mcp.tool()
def create_invoice(client_id: int, items: str, date: str = "",
                   notes: str = "", draft: bool = False) -> str:
    """إنشاء فاتورة مبيعات مبسطة. items بنفس صيغة create_estimate."""
    try:
        items_list = json.loads(items)
        if not isinstance(items_list, list):
            raise ValueError("items يجب أن تكون قائمة")
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"error": f"items غير صالحة: {e}"},
                          ensure_ascii=False)
    invoice = {
        "client_id": client_id,
        "draft": 1 if draft else 0,
        "is_offline": 1,
        "InvoiceItem": items_list,
    }
    if date:
        invoice["date"] = date
    if notes:
        invoice["notes"] = notes
    return json.dumps(_request("POST", "invoices", body={"Invoice": invoice}),
                      ensure_ascii=False)


@mcp.tool()
def create_client(business_name: str, phone: str = "", email: str = "",
                  city: str = "", tax_number: str = "",
                  commercial_register: str = "") -> str:
    """إضافة عميل جديد (منشأة) بطريقة مبسطة."""
    client = {
        "business_name": business_name,
        "type": 3,
        "is_offline": 1,
        "country_code": "SA",
        "default_currency_code": "SAR",
    }
    if phone:
        client["phone1"] = phone
    if email:
        client["email"] = email
    if city:
        client["city"] = city
    if tax_number:
        client["bn1"] = tax_number
        client["bn1_label"] = "الرقم الضريبي"
    if commercial_register:
        client["bn2"] = commercial_register
        client["bn2_label"] = "سجل تجارى/ رقم موحد"
    return json.dumps(_request("POST", "clients", body={"Client": client}),
                      ensure_ascii=False)


@mcp.tool()
def create_expense(amount: float, description: str, date: str = "",
                   category_id: int = 0, treasury_id: int = 0) -> str:
    """تسجيل مصروف جديد."""
    expense = {"amount": amount, "description": description,
               "currency_code": "SAR"}
    if date:
        expense["date"] = date
    if category_id:
        expense["category_id"] = category_id
    if treasury_id:
        expense["treasury_id"] = treasury_id
    return json.dumps(_request("POST", "expenses", body={"Expense": expense}),
                      ensure_ascii=False)


@mcp.tool()
def record_invoice_payment(invoice_id: int, amount: float,
                           payment_method: str = "cash",
                           date: str = "", treasury_id: int = 0) -> str:
    """تسجيل دفعة على فاتورة موج
