"""
MCP Server для роботи з Amazon Seller Partner API.

Надає інструменти для отримання метрик продажів, списку замовлень
та деталей окремих замовлень через протокол MCP.
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

from sp_api.api import Sales, Orders
from sp_api.base import Granularity, Marketplaces

# ---------------------------------------------------------------------------
# Завантажуємо змінні середовища з .env (кореневий каталог проєкту)
# ---------------------------------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ---------------------------------------------------------------------------
# Облікові дані SP-API
# ---------------------------------------------------------------------------
_CREDENTIALS = dict(
    lwa_app_id=os.getenv("SP_API_CLIENT_ID", ""),
    lwa_client_secret=os.getenv("SP_API_CLIENT_SECRET", ""),
    refresh_token=os.getenv("SP_API_REFRESH_TOKEN", ""),
    aws_access_key=os.getenv("AWS_ACCESS_KEY", ""),
    aws_secret_key=os.getenv("AWS_SECRET_KEY", ""),
    role_arn=os.getenv("AWS_ROLE_ARN", ""),
)

# Маппінг регіонів до маркетплейсів за замовчуванням
_REGION_DEFAULT_MARKETPLACE = {
    "NA": Marketplaces.US,
    "EU": Marketplaces.DE,
    "FE": Marketplaces.JP,
}

_DEFAULT_REGION = os.getenv("SP_API_REGION", "EU")

# Повний маппінг кодів країн на маркетплейси
_COUNTRY_MARKETPLACE = {
    "US": Marketplaces.US,
    "CA": Marketplaces.CA,
    "MX": Marketplaces.MX,
    "BR": Marketplaces.BR,
    "DE": Marketplaces.DE,
    "ES": Marketplaces.ES,
    "FR": Marketplaces.FR,
    "IT": Marketplaces.IT,
    "GB": Marketplaces.GB,
    "UK": Marketplaces.GB,
    "NL": Marketplaces.NL,
    "PL": Marketplaces.PL,
    "SE": Marketplaces.SE,
    "BE": Marketplaces.BE,
    "IE": Marketplaces.IE,
    "JP": Marketplaces.JP,
    "AU": Marketplaces.AU,
    "SG": Marketplaces.SG,
    "IN": Marketplaces.IN,
    "AE": Marketplaces.AE,
    "SA": Marketplaces.SA,
    "EG": Marketplaces.EG,
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ініціалізація FastMCP сервера
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "Amazon Seller API",
    instructions="MCP-сервер для роботи з Amazon Selling Partner API: метрики продажів, замовлення тощо.",
)


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------
def _get_marketplace(country_code: Optional[str] = None) -> Marketplaces:
    """Повертає маркетплейс за кодом країни або за замовчуванням."""
    if country_code:
        code = country_code.upper().strip()
        if code in _COUNTRY_MARKETPLACE:
            return _COUNTRY_MARKETPLACE[code]
    return _REGION_DEFAULT_MARKETPLACE.get(_DEFAULT_REGION, Marketplaces.DE)


def _serialize(obj: object) -> str:
    """Безпечна серіалізація відповіді API в JSON."""
    try:
        return json.dumps(obj, default=str, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)


# ---------------------------------------------------------------------------
# Інструменти (Tools)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_sales_metrics(
    start_date: str,
    end_date: str,
    granularity: str = "DAY",
    country_code: str | None = None,
) -> str:
    """Отримати агреговані метрики продажів за заданий період.

    Args:
        start_date: Початкова дата у форматі YYYY-MM-DD.
        end_date: Кінцева дата у форматі YYYY-MM-DD.
        granularity: Гранулярність даних: DAY, WEEK, MONTH, YEAR або TOTAL.
        country_code: Код країни маркетплейсу (наприклад DE, US, GB). За замовчуванням визначається з SP_API_REGION.

    Returns:
        JSON-рядок з метриками продажів.
    """
    marketplace = _get_marketplace(country_code)

    # Формуємо інтервал у форматі ISO 8601
    interval = (
        f"{start_date}T00:00:00Z--{end_date}T23:59:59Z"
    )

    granularity_map = {
        "DAY": Granularity.DAY,
        "WEEK": Granularity.WEEK,
        "MONTH": Granularity.MONTH,
        "YEAR": Granularity.YEAR,
        "TOTAL": Granularity.TOTAL,
        "HOUR": Granularity.HOUR,
    }
    gran = granularity_map.get(granularity.upper(), Granularity.DAY)

    try:
        sales = Sales(credentials=_CREDENTIALS, marketplace=marketplace)
        response = sales.get_order_metrics(
            interval=interval,
            granularity=gran,
            granularityTimeZone="UTC",
        )
        return _serialize(response.payload)
    except Exception as exc:
        logger.exception("Помилка при отриманні метрик продажів")
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@mcp.tool()
def get_orders_list(
    created_after: str | None = None,
    days_back: int = 7,
    country_code: str | None = None,
    order_statuses: str | None = None,
    max_results: int = 20,
) -> str:
    """Отримати список замовлень.

    Args:
        created_after: Дата у форматі YYYY-MM-DD, після якої створені замовлення. Якщо не вказано, використовується days_back.
        days_back: Кількість днів назад від сьогодні (використовується якщо created_after не вказано).
        country_code: Код країни маркетплейсу (наприклад DE, US, GB).
        order_statuses: Статуси замовлень через кому (наприклад: "Shipped,Unshipped"). Можливі: PendingAvailability, Pending, Unshipped, PartiallyShipped, Shipped, InvoiceUnconfirmed, Canceled, Unfulfillable.
        max_results: Максимальна кількість замовлень у відповіді.

    Returns:
        JSON-рядок зі списком замовлень.
    """
    marketplace = _get_marketplace(country_code)

    if created_after:
        after_dt = datetime.strptime(created_after, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    else:
        after_dt = datetime.now(timezone.utc) - timedelta(days=days_back)

    after_iso = after_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    kwargs: dict = {
        "CreatedAfter": after_iso,
        "MaxResultsPerPage": min(max_results, 100),
    }
    if order_statuses:
        kwargs["OrderStatuses"] = [
            s.strip() for s in order_statuses.split(",")
        ]

    try:
        orders_api = Orders(credentials=_CREDENTIALS, marketplace=marketplace)
        response = orders_api.get_orders(**kwargs)
        payload = response.payload

        # Спрощуємо вивід: повертаємо лише основні поля
        orders_raw = payload.get("Orders", [])
        result = {
            "total_orders": len(orders_raw),
            "orders": [],
        }
        for order in orders_raw[:max_results]:
            result["orders"].append(
                {
                    "order_id": order.get("AmazonOrderId"),
                    "purchase_date": order.get("PurchaseDate"),
                    "status": order.get("OrderStatus"),
                    "total": order.get("OrderTotal"),
                    "fulfillment_channel": order.get("FulfillmentChannel"),
                    "sales_channel": order.get("SalesChannel"),
                    "items_shipped": order.get("NumberOfItemsShipped"),
                    "items_unshipped": order.get("NumberOfItemsUnshipped"),
                }
            )
        return _serialize(result)
    except Exception as exc:
        logger.exception("Помилка при отриманні списку замовлень")
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@mcp.tool()
def get_order_details(
    order_id: str,
    country_code: str | None = None,
) -> str:
    """Отримати детальну інформацію про конкретне замовлення та його товари.

    Args:
        order_id: Ідентифікатор замовлення Amazon (наприклад 123-4567890-1234567).
        country_code: Код країни маркетплейсу (наприклад DE, US, GB).

    Returns:
        JSON-рядок з деталями замовлення та списком товарів.
    """
    marketplace = _get_marketplace(country_code)

    try:
        orders_api = Orders(credentials=_CREDENTIALS, marketplace=marketplace)

        # Отримуємо загальну інформацію про замовлення
        order_response = orders_api.get_order(order_id)
        order_data = order_response.payload

        # Отримуємо товари замовлення
        items_response = orders_api.get_order_items(order_id)
        items_data = items_response.payload

        result = {
            "order": order_data,
            "items": items_data.get("OrderItems", []),
        }
        return _serialize(result)
    except Exception as exc:
        logger.exception("Помилка при отриманні деталей замовлення")
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@mcp.tool()
def get_sales_summary(
    days_back: int = 30,
    country_code: str | None = None,
) -> str:
    """Отримати зведену інформацію про продажі за останні N днів.

    Повертає сумарні метрики продажів (кількість замовлень, сума, середній чек тощо)
    за вказаний період з денною гранулярністю.

    Args:
        days_back: Кількість днів назад від сьогодні (за замовчуванням 30).
        country_code: Код країни маркетплейсу (наприклад DE, US, GB).

    Returns:
        JSON-рядок зі зведеними метриками продажів.
    """
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (
        datetime.now(timezone.utc) - timedelta(days=days_back)
    ).strftime("%Y-%m-%d")

    marketplace = _get_marketplace(country_code)
    interval = f"{start_date}T00:00:00Z--{end_date}T23:59:59Z"

    try:
        sales = Sales(credentials=_CREDENTIALS, marketplace=marketplace)
        response = sales.get_order_metrics(
            interval=interval,
            granularity=Granularity.TOTAL,
            granularityTimeZone="UTC",
        )
        metrics = response.payload

        # Також отримуємо денну розбивку
        daily_response = sales.get_order_metrics(
            interval=interval,
            granularity=Granularity.DAY,
            granularityTimeZone="UTC",
        )
        daily_metrics = daily_response.payload

        result = {
            "period": f"{start_date} — {end_date}",
            "total": metrics,
            "daily_breakdown": daily_metrics,
        }
        return _serialize(result)
    except Exception as exc:
        logger.exception("Помилка при отриманні зведення продажів")
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Точка входу
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
