"""Customer Service: drafts messages for customers. Drafts stay on the board and are never sent."""

from agents.base import make_agent
from agents.config import mcp_tools
from models import SpecialistReport

TOOLS = (
    "list_open_tickets", "get_ticket", "check_stock", "get_pricing", "save_customer_draft", "list_customer_drafts",
)

customer_service_agent = make_agent("customer_service", "customer_service.md", SpecialistReport, mcp_tools(*TOOLS))
