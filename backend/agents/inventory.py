"""Inventory: checks stock by SKU and size, spots shortfalls, and works out which vendor can restock."""

from agents.base import make_agent
from agents.config import mcp_tools
from models import SpecialistReport

TOOLS = ("get_shop_date", "list_open_tickets", "get_ticket", "check_stock", "list_vendors", "list_invoices", "get_pricing")

inventory_agent = make_agent("inventory", "inventory.md", SpecialistReport, mcp_tools(*TOOLS))
