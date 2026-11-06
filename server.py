"""
Daftra SabraTech MCP Server - Full CRUD
========================================
خادم MCP كامل الصلاحيات (قراءة / انشاء / تعديل / حذف) لحساب دفترة الخاص بصبرة تك.

المتغيرات البيئية المطلوبة:
    DAFTRA_SUBDOMAIN  -> النطاق الفرعي لحسابك في دفترة
    DAFTRA_APIKEY     -> مفتاح API من دفترة

=== سجل التعديلات (2026-07-26) ===
1. اصلاح جوهري: دفترة تتوقع InvoiceItem كشقيق لـ Invoice وليس متداخلا
   داخله. الكود القديم كان يضع InvoiceItem داخل Invoice فترجع دفترة
   الخطا: "Invoice is empty" مع validation_errors: Invoice.InvoiceItem = null
   نفس نمط الخطا الذي اصلحناه سابقا في PurchaseOrderItem.
2. اصلاح tax1: دفترة تتوقع "معرف الضريبة" وليس النسبة المئوية.
   tax1 = 15  -> Invalid tax: tax not found or inactive
   tax1 = 1   -> صحيح (ضريبة القيمة المضافة 15%)
   تم اضافة تحويل تلقائي يقبل 15 ويحولها الى 1 كشبكة امان.
3. اضافة client_email: دفترة ترفض الحفظ برسالة
   "البريد الإلكتروني مطلوب إذا اخترت أن ترسل الفاتورة عبر البريد"
   اذا كان العميل بلا بريد وكان الارسال بالبريد مفعلا في اعدادات دفترة.
4. حماية daftra_update: التعديل على الفواتير وعروض السعر عبر API يمسح
   البنود ويفسد السجل. اصبح يتطلب force=True صريحا.

=== سجل التعديلات (2026-11-06) ===
5. اضافة طبقة الرواتب عبر واجهة الكيانات العامة v2 (/v2/api/entity).
   دفترة لا توثق مسارات الرواتب رسميا، لذلك:
   - payroll_discover: يكتشف مفاتيح الكيانات الصحيحة (قراءة فقط).
   - payrun_list / payrun_get / payslip_list: قراءة المسيرات والقسائم.
   - daftra_entity_list / daftra_entity_get: وصول عام لاي كيان v2.
   متغيرات بيئة اختيارية: DAFTRA_PAYRUN_ENTITY, DAFTRA_PAYSLIP_ENTITY.
   اداة دفع المسير مؤجلة حتى يثبت هيكل البيانات الفعلي.
"""

import os
import json
import httpx
from fastmcp import FastMCP

SUBDOMAIN = os.environ.get("DAFTRA_SUBDOMAIN", "")
APIKEY = os.environ.get("DAFTRA_APIKEY", "")
BASE_URL = f"https://{SUBDOMAIN}.daftra.com/api2"
# واجهة الكيانات العامة (Entities API) - الاصدار الثاني
# المسار الموثق في docs.daftara.dev: /v2/api/entity/{entity}/list/1
V2_BASE_URL = f"https://{SUBDOMAIN}.daftra.com/v2/api"

# مفاتيح كيانات الرواتب. دفترة لا توثق مسارات الرواتب رسميا،
# لذلك المفاتيح قابلة للتغيير من متغيرات البيئة بعد اكتشافها
# عبر الاداة payroll_discover دون تعديل الكود.
PAYRUN_ENTITY = os.environ.get("DAFTRA_PAYRUN_ENTITY", "payrun")
PAYSLIP_ENTITY = os.environ.get("DAFTRA_PAYSLIP_ENTITY", "payslip")

HEADERS = {
    "APIKEY": APIKEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# معرف ضريبة القيمة المضافة 15% في حساب صبرة تك بدفترة.
# ليست النسبة المئوية بل رقم الضريبة المسجلة في الاعدادات.
TAX_VAT_ID = 1

# المفاتيح التي يجب ان تبقى في اعلى مستوى الطلب كاشقاء
# للموديل الرئيسي ولا تدخل داخله.
SIBLING_KEYS = (
    "InvoiceItem",
    "PurchaseOrderItem",
    "MultiplePayment",
    "InvoicePayment",
    "InvoiceDocument",
)

mcp = FastMCP("Daftra SabraTech - Full CRUD")


def _request(method, endpoint, params=None, body=None, base=None):
    url = f"{base or BASE_URL}/{endpoint.lstrip('/')}"
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


def _normalize_tax(items, apply_vat=True):
    """تصحيح حقل الضريبة في البنود.

    دفترة تتوقع معرف الضريبة لا نسبتها. اي قيمة 15 او 15.0 او True
    تعني ضريبة القيمة المضافة وتحول الى TAX_VAT_ID.
    apply_vat=True يضيف الضريبة للبنود التي لا تحملها اصلا.
    لالغاء الضريبة على بند بعينه مرر tax1 = 0 صراحة.
    """
    for item in items:
        if not isinstance(item, dict):
            continue
        if "tax1" in item:
            value = item["tax1"]
            if value is True:
                item["tax1"] = TAX_VAT_ID
            elif isinstance(value, (int, float)) and float(value) == 15.0:
                item["tax1"] = TAX_VAT_ID
        elif apply_vat:
            item["tax1"] = TAX_VAT_ID
    return items


def _parse_items(items):
    """تحليل نص JSON لقائمة البنود مع التحقق."""
    try:
        items_list = json.loads(items)
        if not isinstance(items_list, list):
            raise ValueError("items must be a JSON list")
        if not items_list:
            raise ValueError("items list is empty")
    except (json.JSONDecodeError, ValueError) as e:
        return None, {"error": f"invalid items: {e}"}
    return items_list, None


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

    مهم: البنود (InvoiceItem / PurchaseOrderItem) والدفعات
    (MultiplePayment) تكون اشقاء للموديل الرئيسي وليست داخله.
    وحقل tax1 هو معرف الضريبة (1 = ضريبة القيمة المضافة 15%)
    وليس النسبة المئوية.

    مثال لعرض سعر:
    {"Invoice": {"client_id": 31, "date": "2026-07-26",
                 "client_email": "x@y.com", "notes": "..."},
     "InvoiceItem": [{"item": "اسم البند",
                      "description": "وصف تفصيلي",
                      "unit_price": 450, "quantity": 1, "tax1": 1}]}

    مثال لفاتورة مشتريات:
    {"PurchaseOrder": {"supplier_id": 54, "date": "2026-06-06"},
     "PurchaseOrderItem": [{"product_id": 282, "unit_price": 65,
                            "quantity": 15, "tax1": 1}]}
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
    if not isinstance(payload, dict):
        return json.dumps({"error": "data must be a JSON object"},
                          ensure_ascii=False)

    if model in payload:
        body = payload
    else:
        # فصل مفاتيح الاشقاء حتى لا تدخل داخل الموديل الرئيسي
        siblings = {k: payload.pop(k) for k in list(payload)
                    if k in SIBLING_KEYS}
        body = {model: payload}
        body.update(siblings)

    if is_estimate and isinstance(body.get("Invoice"), dict):
        body["Invoice"].setdefault("type", 3)

    for key in ("InvoiceItem", "PurchaseOrderItem"):
        if isinstance(body.get(key), list):
            _normalize_tax(body[key], apply_vat=False)

    return json.dumps(_request("POST", endpoint, body=body),
                      ensure_ascii=False)


@mcp.tool()
def daftra_update(resource: str, record_id: int, data: str,
                  force: bool = False) -> str:
    """تعديل سجل موجود. data: نص JSON بالحقول المراد تغييرها فقط.

    تحذير: التعديل على invoices او estimates عبر API يمسح بنود السجل
    ويفسده. الحل الصحيح هو التعديل من واجهة دفترة او اعادة الانشاء.
    لتجاوز الحماية عن قصد مرر force=True.
    """
    res, err = _resolve(resource)
    if err:
        return json.dumps(err, ensure_ascii=False)
    endpoint, model = res
    r = resource.strip().lower()

    if r in ("invoices", "estimates", "refund_receipts") and not force:
        return json.dumps({
            "blocked": "التعديل عبر API على هذا المورد يفسد البنود",
            "recommendation": "عدل من واجهة دفترة او انشئ سجلا جديدا",
            "override": "لتجاوز الحماية مرر force=True",
            "resource": resource, "record_id": record_id,
        }, ensure_ascii=False)

    if r == "estimates":
        endpoint = "invoices"
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"data is not valid JSON: {e}"},
                          ensure_ascii=False)

    if model in payload:
        body = payload
    else:
        siblings = {k: payload.pop(k) for k in list(payload)
                    if k in SIBLING_KEYS}
        body = {model: payload}
        body.update(siblings)

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
def create_estimate(client_id: int, items: str, date: str = "",
                    notes: str = "", draft: bool = False,
                    client_email: str = "", apply_vat: bool = True) -> str:
    """انشاء عرض سعر.

    items: نص JSON قائمة بنود مثل
    [{"item": "اسم مختصر للبند",
      "description": "وصف تفصيلي كامل",
      "unit_price": 450, "quantity": 1, "tax1": 1}]

    tax1 هو معرف الضريبة لا النسبة (1 = ضريبة القيمة المضافة 15%).
    لالغاء الضريبة على بند مرر tax1 = 0.
    apply_vat=True يضيف الضريبة تلقائيا للبنود التي لا تحملها.

    client_email: مطلوب اذا كان العميل بلا بريد مسجل في دفترة، والا
    ترجع دفترة خطا "البريد الإلكتروني مطلوب".
    """
    items_list, err = _parse_items(items)
    if err:
        return json.dumps(err, ensure_ascii=False)
    _normalize_tax(items_list, apply_vat=apply_vat)

    invoice = {
        "client_id": client_id,
        "type": 3,
        "draft": 1 if draft else 0,
        "is_offline": 1,
        "currency_code": "SAR",
    }
    if date:
        invoice["date"] = date
    if notes:
        invoice["notes"] = notes
    if client_email:
        invoice["client_email"] = client_email

    # دفترة تتوقع InvoiceItem شقيقا لـ Invoice وليس متداخلا داخله
    # هذا كان سبب خطا "Invoice is empty"
    body = {"Invoice": invoice, "InvoiceItem": items_list}
    return json.dumps(_request("POST", "invoices", body=body),
                      ensure_ascii=False)


@mcp.tool()
def create_invoice(client_id: int, items: str, date: str = "",
                   notes: str = "", draft: bool = False,
                   client_email: str = "", apply_vat: bool = True) -> str:
    """انشاء فاتورة مبيعات. items بنفس صيغة create_estimate."""
    items_list, err = _parse_items(items)
    if err:
        return json.dumps(err, ensure_ascii=False)
    _normalize_tax(items_list, apply_vat=apply_vat)

    invoice = {
        "client_id": client_id,
        "type": 0,
        "draft": 1 if draft else 0,
        "is_offline": 1,
        "currency_code": "SAR",
    }
    if date:
        invoice["date"] = date
    if notes:
        invoice["notes"] = notes
    if client_email:
        invoice["client_email"] = client_email

    body = {"Invoice": invoice, "InvoiceItem": items_list}
    return json.dumps(_request("POST", "invoices", body=body),
                      ensure_ascii=False)


@mcp.tool()
def create_purchase_invoice(supplier_id: int, items: str, date: str = "",
                            notes: str = "", draft: bool = False,
                            invoice_number: str = "",
                            payments: str = "",
                            supplier_email: str = "",
                            apply_vat: bool = True) -> str:
    """انشاء فاتورة مشتريات مرتبطة بمورد.

    items: نص JSON قائمة بنود مثل
    [{"product_id": 282, "unit_price": 65, "quantity": 15, "tax1": 1}]
    او بوصف بدون منتج:
    [{"description": "بند", "unit_price": 100, "quantity": 1, "tax1": 1}]

    tax1 هو معرف الضريبة لا النسبة (1 = ضريبة القيمة المضافة 15%).

    invoice_number: رقم فاتورة المورد الورقية (اختياري).
    supplier_email: مرره اذا كان المورد بلا بريد مسجل في دفترة.

    payments: نص JSON اختياري لقائمة الدفعات مثل
    [{"payment_method": "cash", "amount": 115, "treasury_id": 1}]
    قيم payment_method المعتمدة: bank او cash.
    الخزائن: 1 = خزينة صبره تك، 2 = بنك الراجحي.
    اتركه فارغا لانشاء فاتورة اجلة غير مدفوعة.
    ملاحظة: حقل MultiplePayment لم يثبت نجاحه بعد عبر API - الاسلوب
    الموثوق حاليا هو انشاء الفاتورة اجلة ثم تسجيل الدفعة من الواجهة.
    """
    items_list, err = _parse_items(items)
    if err:
        return json.dumps(err, ensure_ascii=False)
    _normalize_tax(items_list, apply_vat=apply_vat)

    po = {
        "supplier_id": supplier_id,
        "type": 0,
        "draft": 1 if draft else 0,
        "is_offline": 1,
        "currency_code": "SAR",
    }
    if date:
        po["date"] = date
    if notes:
        po["notes"] = notes
    if invoice_number:
        po["po_number"] = invoice_number
    if supplier_email:
        po["supplier_email"] = supplier_email

    # دفترة تتوقع PurchaseOrderItem شقيقا لـ PurchaseOrder
    # وليس متداخلا داخله - هذا كان سبب خطا
    # "At least one item is required"
    body = {"PurchaseOrder": po, "PurchaseOrderItem": items_list}

    if payments:
        try:
            payments_list = json.loads(payments)
            if not isinstance(payments_list, list):
                raise ValueError("payments must be a list")
        except (json.JSONDecodeError, ValueError) as e:
            return json.dumps({"error": f"invalid payments: {e}"},
                              ensure_ascii=False)
        for p in payments_list:
            if isinstance(p, dict):
                p.setdefault("currency_code", "SAR")
                if date:
                    p.setdefault("date", date)
        body["MultiplePayment"] = payments_list

    return json.dumps(_request("POST", "purchase_invoices", body=body),
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
def create_client(business_name: str, phone: str = "", email: str = "",
                  city: str = "", tax_number: str = "",
                  commercial_register: str = "") -> str:
    """اضافة عميل جديد (منشاة).
    يفضل تمرير email دائما لان دفترة قد ترفض انشاء فواتير لعميل
    بلا بريد الكتروني.
    """
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
def create_product(name: str, buy_price: float = 0, unit_price: float = 0,
                   description: str = "", category_id: int = 0,
                   supplier_id: int = 0, low_stock_threshold: int = 0,
                   apply_vat: bool = True) -> str:
    """اضافة منتج جديد.
    category_id: رقم التصنيف (مثال: 3 = قطع ميكانيكا).
    apply_vat: ربط المنتج بضريبة القيمة المضافة 15%.
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
        # ملاحظة: التسمية الخاطئة thershold هي تسمية دفترة نفسها
        # ولا يجوز تصحيحها والا لن يقرأ الحقل
        product["low_stock_thershold"] = low_stock_threshold
    if apply_vat:
        # معرف الضريبة لا النسبة
        product["tax1"] = TAX_VAT_ID
    return json.dumps(
        _request("POST", "products", body={"Product": product}),
        ensure_ascii=False)


@mcp.tool()
def create_expense(amount: float, description: str, date: str = "",
                   category_id: int = 0, treasury_id: int = 0,
                   notes: str = "") -> str:
    """تسجيل مصروف جديد.
    الخزائن: 1 = خزينة صبره تك، 2 = بنك الراجحي.
    ملاحظة: حقل description لا يظهر في واجهة دفترة، لذلك يتم نسخه
    الى حقل notes ايضا ليكون مرئيا.
    """
    expense = {"amount": amount, "description": description,
               "currency_code": "SAR"}
    expense["notes"] = notes if notes else description
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
    """تسجيل دفعة على فاتورة.
    payment_method: cash او bank.
    الخزائن: 1 = خزينة صبره تك، 2 = بنك الراجحي.
    """
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


# =====================================================================
# الرواتب (Payroll) - عبر واجهة الكيانات العامة v2
# =====================================================================
# دفترة لا توثق مسارات الرواتب في واجهتها الرسمية. الادوات التالية
# للقراءة فقط حاليا. اداة الدفع تضاف بعد التحقق من هيكل البيانات
# الفعلي لان دفع المسير ينشئ قيودا محاسبية ولا يجوز تجربته عشوائيا.

PAYROLL_CANDIDATES = (
    "payrun", "payruns", "pay_run", "payroll", "payroll_run",
    "payslip", "payslips", "pay_slip", "salary_slip",
    "contract", "contracts", "staff_contract",
)


def _v2(method, path, params=None, body=None):
    return _request(method, path, params=params, body=body,
                    base=V2_BASE_URL)


def _entity_list(entity, page=1, per_page=20, filters=None):
    params = {"page": page, "per_page": per_page}
    if filters:
        params.update(filters)
    return _v2("GET", f"entity/{entity}/list/1", params=params)


def _parse_filters(filters):
    if not filters:
        return {}, None
    try:
        f = json.loads(filters)
        if not isinstance(f, dict):
            raise ValueError("filters must be a JSON object")
        return f, None
    except (json.JSONDecodeError, ValueError) as e:
        return None, {"error": f"invalid filters: {e}"}


@mcp.tool()
def daftra_entity_list(entity: str, page: int = 1, per_page: int = 20,
                       filters: str = "") -> str:
    """جلب قائمة من اي كيان عبر واجهة الكيانات العامة v2.
    entity: مفتاح الكيان مثل invoice, client, product, expense
    او كيانات غير موثقة مثل الرواتب بعد اكتشافها.
    filters: نص JSON اختياري.
    """
    f, err = _parse_filters(filters)
    if err:
        return json.dumps(err, ensure_ascii=False)
    return json.dumps(_entity_list(entity.strip(), page, per_page, f),
                      ensure_ascii=False)


@mcp.tool()
def daftra_entity_get(entity: str, record_id: int) -> str:
    """جلب سجل واحد من اي كيان عبر واجهة v2."""
    return json.dumps(_v2("GET", f"entity/{entity.strip()}/{record_id}"),
                      ensure_ascii=False)


@mcp.tool()
def payroll_discover() -> str:
    """اكتشاف مفاتيح كيانات الرواتب الفعلية في حساب دفترة.
    تجرب قائمة مفاتيح محتملة وتعيد رمز الاستجابة وعينة من الحقول.
    المفتاح الذي يرجع 200 هو الصحيح: ضعه في متغير البيئة
    DAFTRA_PAYRUN_ENTITY او DAFTRA_PAYSLIP_ENTITY على Render.
    للقراءة فقط - لا يعدل اي بيانات.
    """
    results = {}
    for key in PAYROLL_CANDIDATES:
        r = _entity_list(key, page=1, per_page=1)
        code = r.get("status_code")
        entry = {"status_code": code}
        data = r.get("data")
        if code == 200 and isinstance(data, dict):
            rows = data.get("data")
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                entry["sample_fields"] = list(rows[0].keys())[:40]
            meta = data.get("meta")
            if isinstance(meta, dict):
                entry["total"] = meta.get("total")
        elif "error" in r:
            entry["error"] = r["error"]
        results[key] = entry
    return json.dumps({
        "configured": {"payrun": PAYRUN_ENTITY, "payslip": PAYSLIP_ENTITY},
        "results": results,
    }, ensure_ascii=False)


@mcp.tool()
def payrun_list(page: int = 1, per_page: int = 20,
                filters: str = "") -> str:
    """جلب مسيرات الرواتب مع حالتها (مسودة / معتمد / مدفوع)."""
    f, err = _parse_filters(filters)
    if err:
        return json.dumps(err, ensure_ascii=False)
    return json.dumps(_entity_list(PAYRUN_ENTITY, page, per_page, f),
                      ensure_ascii=False)


@mcp.tool()
def payrun_get(payrun_id: int) -> str:
    """جلب مسير رواتب واحد بالتفصيل برقمه (مثال: 5 = مسير سبتمبر)."""
    return json.dumps(_v2("GET", f"entity/{PAYRUN_ENTITY}/{payrun_id}"),
                      ensure_ascii=False)


@mcp.tool()
def payslip_list(payrun_id: int = 0, page: int = 1,
                 per_page: int = 50) -> str:
    """جلب قسائم الرواتب، اختياريا لمسير محدد.
    كل قسيمة تحمل الموظف والاجمالي والاستقطاعات والصافي والحالة.
    """
    f = {"filter[payrun_id]": payrun_id} if payrun_id else None
    return json.dumps(_entity_list(PAYSLIP_ENTITY, page, per_page, f),
                      ensure_ascii=False)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="http", host="0.0.0.0", port=port, path="/mcp")
