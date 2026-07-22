"""
Daftra SabraTech MCP Server - Full CRUD
========================================
خادم MCP كامل الصلاحيات (قراءة / انشاء / تعديل / حذف) لحساب دفترة الخاص بصبرة تك.

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

mcp = FastMCP("Daftra SabraTech - Full CRUD")


def _request(method, endpoint, params=None, body=None):
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    try:
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            resp = client.request(method, url, headers=HEADERS,
                                  params=params, json=body)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
            if resp.status_code in (301, 302, 303, 307, 308):
                data["redirect_location"] = resp.headers.get("location", "")
        return {"status_code": resp.status_code, "data": data}
    except Exception as e:
        return {"status_code": 0, "error": str(e)}


RESOURCES = {
    "clients":            ("clients", "Client"),
    "suppliers":          ("suppliers", "Supplier"),
    "products":           ("products", "Product"),
    "invoices":           ("invoices", "Invoice"),
    "estimates":          ("estimates", "Invoice"),
    "purchase_invoices":  ("purchase_invoices", "PurchaseOrder"),
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


def _resolve(resource):
    r = resource.strip().lower()
    if r not in RESOURCES:
        return None, {"error": "resource not supported",
                      "available": list(RESOURCES.keys())}
    return RESOURCES[r], None


@mcp.tool()
def daftra_list(resource: str, page: int = 1, limit: int = 20,
                filters: str = "") -> str:
    """جلب قائمة من اي مورد في دفترة.
    resource: clients, suppliers, products, invoices, estimates,
    purchase_invoices, refund_receipts, expenses, incomes,
    invoice_payments, journals, treasuries, stock_transactions,
    appointments, notes, staff, work_orders.
    filters: نص JSON اختياري مثل {"client_id": 31}
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
            return json.dumps({"error": "filters is not valid JSON"},
                              ensure_ascii=False)
    return json.dumps(_request("GET", endpoint, params=params),
                      ensure_ascii=False)


@mcp.tool()
def daftra_get(resource: str, record_id: int) -> str:
    """جلب سجل واحد بالتفصيل من اي مورد في دفترة برقمه."""
    res, err = _resolve(resource)
    if err:
        return json.dumps(err, ensure_ascii=False)
    endpoint, _ = res
    return json.dumps(_request("GET", f"{endpoint}/{record_id}"),
                      ensure_ascii=False)


@mcp.tool()
def daftra_create(resource: str, data: str) -> str:
    """انشاء سجل جديد في اي مورد في دفترة.
    data: نص JSON بحقول السجل.
    مثال لعرض سعر: {"client_id": 31, "date": "2026-07-19",
      "InvoiceItem": [{"description": "توريد وتركيب قفل",
                       "unit_price": 450, "quantity": 1, "tax1": 15}]}
    مثال لفاتورة مشتريات: {"supplier_id": 54, "date": "2026-06-06",
      "PurchaseOrderItem": [{"product_id": 282, "unit_price": 65,
                             "quantity": 15, "tax1": 15}]}
    """
    res, err = _resolve(resource)
    if err:
        return json.dumps(err, ensure_ascii=False)
    endpoint, model = res
    is_estimate = resource.strip().lower() == "estimates"
    if is_estimate:
        # عروض الاسعار في دفترة هي فواتير من النوع 3
        # ولا يوجد مسار POST /estimates - الانشاء عبر POST /invoices
        endpoint = "invoices"
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"data is not valid JSON: {e}"},
                          ensure_ascii=False)
    body = payload if model in payload else {model: payload}
    if is_estimate and isinstance(body.get("Invoice"), dict):
        body["Invoice"].setdefault("type", 3)
    return json.dumps(_request("POST", endpoint, body=body),
                      ensure_ascii=False)


@mcp.tool()
def daftra_update(resource: str, record_id: int, data: str) -> str:
    """تعديل سجل موجود. data: نص JSON بالحقول المراد تغييرها فقط."""
    res, err = _resolve(resource)
    if err:
        return json.dumps(err, ensure_ascii=False)
    endpoint, model = res
    if resource.strip().lower() == "estimates":
        endpoint = "invoices"
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"data is not valid JSON: {e}"},
                          ensure_ascii=False)
    body = payload if model in payload else {model: payload}
    return json.dumps(_request("PUT", f"{endpoint}/{record_id}", body=body),
                      ensure_ascii=False)


@mcp.tool()
def daftra_delete(resource: str, record_id: int, confirm: bool = False) -> str:
    """حذف سجل نهائيا. يتطلب confirm=True بعد تاكيد المستخدم."""
    if not confirm:
        return json.dumps({
            "warning": "delete is permanent, call again with confirm=True",
            "resource": resource, "record_id": record_id,
        }, ensure_ascii=False)
    res, err = _resolve(resource)
    if err:
        return json.dumps(err, ensure_ascii=False)
    endpoint, _ = res
    if resource.strip().lower() == "estimates":
        endpoint = "invoices"
    return json.dumps(_request("DELETE", f"{endpoint}/{record_id}"),
                      ensure_ascii=False)


@mcp.tool()
def create_purchase_invoice(supplier_id: int, items: str, date: str = "",
                            notes: str = "", draft: bool = False,
                            invoice_number: str = "") -> str:
    """انشاء فاتورة مشتريات مرتبطة بمورد.
    items: نص JSON قائمة بنود مثل
    [{"product_id": 282, "unit_price": 65, "quantity": 15, "tax1": 15}]
    او بوصف بدون منتج:
    [{"description": "بند", "unit_price": 100, "quantity": 1, "tax1": 15}]
    invoice_number: رقم فاتورة المورد الورقية (اختياري).
    """
    try:
        items_list = json.loads(items)
        if not isinstance(items_list, list):
            raise ValueError("items must be a list")
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"error": f"invalid items: {e}"},
                          ensure_ascii=False)
    po = {
        "supplier_id": supplier_id,
        "type": 0,
        "draft": 1 if draft else 0,
        "is_offline": 1,
        "currency_code": "SAR",
        "PurchaseOrderItem": items_list,
    }
    if date:
        po["date"] = date
    if notes:
        po["notes"] = notes
    if invoice_number:
        po["po_number"] = invoice_number
    return json.dumps(
        _request("POST", "purchase_invoices", body={"PurchaseOrder": po}),
        ensure_ascii=False)


@mcp.tool()
def create_supplier(business_name: str, phone: str = "", email: str = "",
                    city: str = "", tax_number: str = "",
                    commercial_register: str = "") -> str:
    """اضافة مورد جديد."""
    supplier = {
        "business_name": business_name,
        "is_offline": 1,
        "country_code": "SA",
        "default_currency_code": "SAR",
    }
    if phone:
        supplier["phone1"] = phone
    if email:
        supplier["email"] = email
    if city:
        supplier["city"] = city
    if tax_number:
        supplier["bn1"] = tax_number
        supplier["bn1_label"] = "الرقم الضريبي"
    if commercial_register:
        supplier["bn2"] = commercial_register
        supplier["bn2_label"] = "سجل تجارى/ رقم موحد"
    return json.dumps(
        _request("POST", "suppliers", body={"Supplier": supplier}),
        ensure_ascii=False)


@mcp.tool()
def create_product(name: str, buy_price: float = 0, unit_price: float = 0,
                   description: str = "", category_id: int = 0,
                   supplier_id: int = 0, low_stock_threshold: int = 0,
                   apply_vat: bool = True) -> str:
    """اضافة منتج جديد.
    category_id: رقم التصنيف (مثال: 3 = قطع ميكانيكا).
    apply_vat: تفعيل ضريبة 15% على البيع.
    """
    product = {
        "name": name,
        "track_stock": 1,
        "tracking_type": "quantity_only",
    }
    if buy_price:
        product["buy_price"] = buy_price
    if unit_price:
        product["unit_price"] = unit_price
    if description:
        product["description"] = description
    if category_id:
        product["category_id"] = category_id
    if supplier_id:
        product["supplier_id"] = supplier_id
    if low_stock_threshold:
        product["low_stock_thershold"] = low_stock_threshold
    if apply_vat:
        product["tax1"] = 15
    return json.dumps(
        _request("POST", "products", body={"Product": product}),
        ensure_ascii=False)


@mcp.tool()
def create_estimate(client_id: int, items: str, date: str = "",
                    notes: str = "", draft: bool = False) -> str:
    """انشاء عرض سعر.
    items: نص JSON قائمة بنود مثل
    [{"description": "بند", "unit_price": 450, "quantity": 1, "tax1": 15}]
    """
    try:
        items_list = json.loads(items)
        if not isinstance(items_list, list):
            raise ValueError("items must be a list")
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"error": f"invalid items: {e}"},
                          ensure_ascii=False)
    invoice = {
        "client_id": client_id,
        "type": 3,
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
def create_invoice(client_id: int, items: str, date: str = "",
                   notes: str = "", draft: bool = False) -> str:
    """انشاء فاتورة مبيعات. items بنفس صيغة create_estimate."""
    try:
        items_list = json.loads(items)
        if not isinstance(items_list, list):
            raise ValueError("items must be a list")
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"error": f"invalid items: {e}"},
                          ensure_ascii=False)
    invoice = {
        "client_id": client_id,
        "type": 0,
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
    """اضافة عميل جديد (منشاة)."""
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
    """تسجيل دفعة على فاتورة."""
    payment = {
        "invoice_id": invoice_id,
        "amount": amount,
        "payment_method": payment_method,
        "currency_code": "SAR",
    }
    if date:
        payment["date"] = date
    if treasury_id:
        payment["treasury_id"] = treasury_id
    return json.dumps(
        _request("POST", "invoice_payments", body={"InvoicePayment": payment}),
        ensure_ascii=False)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="http", host="0.0.0.0", port=port, path="/mcp")
