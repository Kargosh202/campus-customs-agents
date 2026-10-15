"""Facilities: handles the shop space (leases, rent amounts, due dates)."""

from agents.base import make_agent
from agents.config import mcp_tools
from models import SpecialistReport

TOOLS = ("get_shop_date", "list_open_tickets", "get_ticket", "get_lease_status", "list_payment_requests")

facilities_agent = make_agent("facilities", "facilities.md", SpecialistReport, mcp_tools(*TOOLS))
