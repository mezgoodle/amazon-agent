"""
Amazon Seller Agent — AI-агент для роботи з Amazon Seller Partner API.

Використовує Google ADK та локальний MCP-сервер для виклику
інструментів Amazon SP-API (продажі, замовлення тощо).
"""

import os
import sys

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import MCPToolset, StdioConnectionParams
from mcp.client.stdio import StdioServerParameters

# Шлях до MCP-сервера — лежить поруч із цим файлом
_MCP_SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "mcp_server.py")

# Шлях до Python з поточного venv
_PYTHON = sys.executable

root_agent = Agent(
    model="gemini-2.5-flash",
    name="amazon_seller_agent",
    description="AI-помічник для аналізу продажів на Amazon",
    instruction="""Ти — розумний помічник Amazon Seller. Ти допомагаєш продавцю
аналізувати метрики продажів, переглядати замовлення та отримувати зведену
інформацію.

Основні можливості:
• get_sales_metrics — агреговані метрики продажів за довільний період
• get_orders_list — список замовлень з фільтрацією
• get_order_details — детальна інформація про конкретне замовлення
• get_sales_summary — зведення продажів за останні N днів

Якщо користувач не вказує маркетплейс, використовуй значення за замовчуванням.
Якщо не вказані дати, запропонуй розумні значення (наприклад, останні 7 або 30 днів).
Відповідай чітко і структуровано. Для числових даних можеш використовувати таблиці.
Відповідай тією мовою, якою запитує користувач.
""",
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=_PYTHON,
                    args=[_MCP_SERVER_SCRIPT],
                ),
                timeout=30.0,
            ),
        ),
    ],
)
