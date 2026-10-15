"""Boss: reads each ticket, decides who should work on it, and makes the final call.

Top-level runs return a BoardPlan. When a teammate asks the Boss something, it answers with a
SpecialistReport instead (see team.run_agent).
"""

from agents.base import make_agent
from agents.config import mcp_tools
from models import BoardPlan

TOOLS = (
    "get_shop_date", "list_open_tickets", "get_ticket", "update_ticket", "check_stock", "get_lease_status",
    "get_cash_balance", "list_invoices", "list_vendors", "get_pricing", "list_payment_requests",
    "list_customer_drafts",
)

boss_agent = make_agent("boss", "boss.md", BoardPlan, mcp_tools(*TOOLS))
