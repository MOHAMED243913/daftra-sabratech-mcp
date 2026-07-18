import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP("Daftra-SabraTech")

SUBDOMAIN = os.environ["DAFTRA_SUBDOMAIN"]
APIKEY = os.environ["DAFTRA_APIKEY"]

def _get(path: str, params: dict | None = None) -> dict:
    url = f"https://{SUBDOMAIN}.daftra.com/api2/{path}"
    headers = {"apikey": APIKEY, "Accept": "application/json"}
    r = httpx.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

@mcp.tool()
def list_clients(page: int = 1, limit: int = 10) -> dict:
    """جلب قائمة عملاء صبرة تك من دفترة."""
    return _get("clients", {"page": page, "limit": limit})

@mcp.tool()
def get_client(client_id: int) -> dict:
    """جلب بيانات عميل واحد برقمه."""
    return _get(f"clients/{client_id}")

@mcp.tool()
def list_invoices(page: int = 1, limit: int = 10) -> dict:
    """جلب قائمة فواتير صبرة تك."""
    return _get("invoices", {"page": page, "limit": limit})

@mcp.tool()
def list_products(page: int = 1, limit: int = 10) -> dict:
    """جلب قائمة المنتجات من دفترة."""
    return _get("products", {"page": page, "limit": limit})

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )
