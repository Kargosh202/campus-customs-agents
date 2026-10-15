# Campus Customs MCP server

The shared toolbox for the Campus Customs agent team. Every agent (Boss, Inventory, Accounting, Facilities, Customer Service) reads and updates the shop through these tools instead of touching the database directly. Every value a tool returns comes straight from the database or from arithmetic on it.

## Database

It uses the working copy **`data/campus_customs_new.db`**. The original `data/campus_customs.db` is never touched, so the working copy can be reset from it before a full run (`backend/reset_db.py`). The server adds two tables to the working copy: `payment_requests` (payments waiting for a human) and `customer_drafts` (customer messages that stay on the board).

## Tools (17)

| Tool | What it does |
|---|---|
| `get_shop_date()` | The shop's "today" (`desk.date_today`) and desk notes |
| `list_open_tickets()` | Every ticket still on the board (not `resolved`), oldest first, with all its fields |
| `list_tickets()` | Every ticket, resolved or not, with `is_open` and counts of drafts and pending payments (used by the dashboard) |
| `get_ticket(ticket_id)` | One ticket in full, with its customer drafts and payment requests |
| `update_ticket(ticket_id, status, note, updated_by)` | Sets a ticket's status and appends a dated note. Won't mark a ticket `resolved` while its payment is still pending |
| `check_stock(sku, size=None)` | Units on hand and aisle for a SKU, for one size or every size |
| `get_lease_status(lease_id)` | A lease's rent and due date, plus days until due and whether it's overdue, measured from `desk.date_today` |
| `get_cash_balance(account=None)` | Balance in each cash account and the total |
| `list_invoices(status="open", vendor_id=None, invoice_id=None)` | Vendor invoices with the vendor's name and days overdue |
| `list_vendors()` | Vendors, what they supply, lead time, arrival date if ordered today, and whether an open invoice stops them shipping (`can_ship`) |
| `get_pricing(sku, discount_percent=None, qty=None)` | Unit cost, list price, and margin, also at a discount and for a quantity |
| `request_payment(kind, ...)` | Queues an invoice, rent, or purchase-order payment for human approval. No cash moves. Amount and payee come from the database. Warns when pending requests add up to more than the balance |
| `list_payment_requests(status="pending")` | Payment requests and their status (pending, paid, rejected) |
| `save_customer_draft(ticket_id, message, drafted_by)` | Saves a customer message as a draft addressed to the ticket's requester. Nothing is sent |
| `list_customer_drafts(ticket_id=None)` | Customer drafts on the board |
| `pay_request(request_id, approved_by)` | **Human only.** Pays an approved request: records the payment, takes it out of cash, marks the invoice paid or moves the lease's next due date forward a month. **Refuses if the balance would go below zero** |
| `reject_payment_request(request_id, rejected_by, note)` | **Human only.** Rejects a request. No cash moves |

A bad SKU, size, ticket, lease, invoice, or account returns an error with the valid options instead of a guess.

## Human approval

Payments take two steps. An agent can only call `request_payment`, which queues a pending request. A person approves or rejects it in the dashboard, which calls `pay_request` or `reject_payment_request`. No agent is given those two tools (`backend/agents/config.py` refuses to), and `pay_request` won't accept an agent's name as the approver.

## Run

From `HW 5/`:

```bash
.venv/bin/python mcp_server/server.py
```
