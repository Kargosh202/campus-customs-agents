"""Accounting: watches cash and invoices, checks margins, and prepares payments and purchase orders
for human approval. It never moves money on its own."""

from agents.base import make_agent
from agents.config import mcp_tools
from models import SpecialistReport

TOOLS = (
    "get_shop_date", "list_open_tickets", "get_ticket", "check_stock", "get_lease_status", "get_cash_balance",
    "list_invoices", "list_vendors", "get_pricing", "request_payment", "list_payment_requests",
)

accounting_agent = make_agent("accounting", "accounting.md", SpecialistReport, mcp_tools(*TOOLS))
