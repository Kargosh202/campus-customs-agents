"""Campus Customs MCP server: the shop tools every agent on the team uses.

Works on the working copy data/campus_customs_new.db (never the original campus_customs.db).
Every value a tool returns comes straight from the database or from arithmetic on it; nothing is
estimated or made up.

Payments take two steps so a human always approves them:
1. An agent calls request_payment(). That only queues a pending row in payment_requests; no cash moves.
2. A person approves it in the dashboard, which calls pay_request() (or reject_payment_request()).
   Those two tools are HUMAN ONLY: no agent is given them. pay_request() refuses anything that would
   take a cash balance below zero.

Run from HW 5/:
    .venv/bin/python mcp_server/server.py
Set CAMPUS_DB_PATH to point the server at a different database file (used for testing).
"""

from __future__ import annotations

import calendar
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP

HW_DIR = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("CAMPUS_DB_PATH", HW_DIR / "data" / "campus_customs_new.db"))

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}

# Payment requests live in the working copy only. Resetting the working copy from the original
# drops this table, and connect() creates it again, empty.
PAYMENT_REQUESTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice, rent, or purchase_order
    ref_id INTEGER,                  -- invoice id or lease id (null for purchase orders)
    vendor_id INTEGER,               -- purchase orders: who ships
    sku TEXT,                        -- purchase orders: what to order
    size TEXT,
    qty INTEGER,
    amount REAL NOT NULL,
    payee TEXT NOT NULL,
    account TEXT NOT NULL,
    ticket_id INTEGER,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending, paid, or rejected
    decided_by TEXT,
    decided_at TEXT,
    decision_note TEXT,
    payment_id INTEGER
)
"""

# Customer Service drafts stay on the board here. Nothing is ever sent.
CUSTOMER_DRAFTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS customer_drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,         -- the ticket's requester
    message TEXT NOT NULL,
    drafted_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL             -- always 'draft': this shop never sends messages
)
"""

TICKET_STATUSES = ("open", "waiting_on_approval", "blocked", "needs_info", "resolved")

mcp = FastMCP("Campus Customs")


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}. Copy data/campus_customs.db to it.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(PAYMENT_REQUESTS_SCHEMA)
    conn.execute(CUSTOMER_DRAFTS_SCHEMA)
    return conn


def shop_today(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT date_today FROM desk").fetchone()["date_today"]


def days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def add_one_month(iso_day: str) -> str:
    d = date.fromisoformat(iso_day)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1])).isoformat()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_invoices_for(conn: sqlite3.Connection, vendor_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, amount, due_date, description FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
        (vendor_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# --- Tickets and stock -------------------------------------------------------


@mcp.tool
def get_shop_date() -> dict[str, Any]:
    """The shop's "today" (desk.date_today) and any desk notes. Use this date, never the real one,
    for anything overdue or due soon."""
    with connect() as conn:
        desk = dict(conn.execute("SELECT * FROM desk").fetchone())
    return desk


@mcp.tool
def list_open_tickets() -> dict[str, Any]:
    """List every ticket still on the board (any status except "resolved"), oldest first, with all of
    its fields (type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at)."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at").fetchall()
    tickets = [dict(row) for row in rows]
    return {"open_ticket_count": len(tickets), "tickets": tickets}


@mcp.tool
def list_tickets() -> dict[str, Any]:
    """Every ticket on the board, resolved or not, oldest first, each with `is_open` (anything not
    "resolved") and how many customer drafts and pending payment requests it has. Used by the dashboard."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT t.*,
                   (SELECT COUNT(*) FROM customer_drafts d WHERE d.ticket_id = t.id) AS draft_count,
                   (SELECT COUNT(*) FROM payment_requests p WHERE p.ticket_id = t.id AND p.status = 'pending')
                       AS pending_payment_count
            FROM tickets t ORDER BY t.created_at
            """
        ).fetchall()
    tickets = [{**dict(r), "is_open": r["status"] != "resolved"} for r in rows]
    return {
        "ticket_count": len(tickets),
        "open_count": sum(t["is_open"] for t in tickets),
        "resolved_count": sum(not t["is_open"] for t in tickets),
        "tickets": tickets,
    }


@mcp.tool
def get_ticket(ticket_id: int) -> dict[str, Any]:
    """One ticket in full, any status, with its customer drafts and payment requests.

    Args:
        ticket_id: Ticket id, e.g. 101.
    """
    with connect() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            valid = [r["id"] for r in conn.execute("SELECT id FROM tickets ORDER BY id")]
            return {"error": f"Unknown ticket id {ticket_id}.", "valid_ticket_ids": valid}
        drafts = [dict(r) for r in conn.execute("SELECT * FROM customer_drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))]
        requests = [dict(r) for r in conn.execute("SELECT * FROM payment_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,))]
    return {"ticket": dict(ticket), "customer_drafts": drafts, "payment_requests": requests}


@mcp.tool
def update_ticket(
    ticket_id: int,
    status: Literal["open", "waiting_on_approval", "blocked", "needs_info", "resolved"],
    note: str,
    updated_by: str,
) -> dict[str, Any]:
    """Set a ticket's status and add a dated note to it. The ticket's original notes are kept;
    the new note is appended.

    Args:
        ticket_id: Ticket id.
        status: "waiting_on_approval" (plan ready, a human must approve a payment), "blocked"
            (something outside the team stops it), "needs_info", "resolved" (nothing left to do),
            or "open".
        note: One or two sentences on what was decided, for the next person who reads the ticket.
        updated_by: Which agent or person is updating it.
    """
    if status not in TICKET_STATUSES:
        return {"error": f"Unknown status '{status}'.", "valid_statuses": list(TICKET_STATUSES)}
    if not note.strip() or not updated_by.strip():
        return {"error": "A note and updated_by are required."}
    with connect() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"error": f"Unknown ticket id {ticket_id}."}
        if status == "resolved":
            pending = conn.execute(
                "SELECT id FROM payment_requests WHERE ticket_id = ? AND status = 'pending'", (ticket_id,)
            ).fetchall()
            if pending:
                return {
                    "error": "Can't resolve a ticket with payment requests still waiting for a human.",
                    "pending_request_ids": [r["id"] for r in pending],
                }
        today = shop_today(conn)
        entry = f"[{today} {updated_by.strip()}: {status}] {note.strip()}"
        notes = f"{ticket['notes']}\n{entry}" if ticket["notes"] else entry
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
        updated = dict(conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone())
    return {"previous_status": ticket["status"], "ticket": updated}


@mcp.tool
def save_customer_draft(ticket_id: int, message: str, drafted_by: str) -> dict[str, Any]:
    """Save a customer message as a DRAFT on the board, addressed to the ticket's requester.
    Nothing is sent: this shop never emails customers.

    Args:
        ticket_id: The ticket the message answers.
        message: The full draft text.
        drafted_by: Which agent wrote it, e.g. "customer_service".
    """
    if not message.strip():
        return {"error": "The draft is empty."}
    with connect() as conn:
        ticket = conn.execute("SELECT requester FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"error": f"Unknown ticket id {ticket_id}."}
        cur = conn.execute(
            "INSERT INTO customer_drafts (ticket_id, recipient, message, drafted_by, created_at, status) "
            "VALUES (?, ?, ?, ?, ?, 'draft')",
            (ticket_id, ticket["requester"], message.strip(), drafted_by, now_utc()),
        )
        draft = dict(conn.execute("SELECT * FROM customer_drafts WHERE id = ?", (cur.lastrowid,)).fetchone())
    return {"draft": draft, "note": "Saved as a draft on the board. Nothing was sent."}


@mcp.tool
def list_customer_drafts(ticket_id: int | None = None) -> dict[str, Any]:
    """Customer message drafts on the board, newest last.

    Args:
        ticket_id: Optional, only this ticket's drafts.
    """
    query, params = "SELECT * FROM customer_drafts", ()
    if ticket_id is not None:
        query, params = query + " WHERE ticket_id = ?", (ticket_id,)
    with connect() as conn:
        drafts = [dict(r) for r in conn.execute(query + " ORDER BY id", params)]
    return {"count": len(drafts), "drafts": drafts}


@mcp.tool
def check_stock(sku: str, size: str | None = None) -> dict[str, Any]:
    """Look up units on hand for a SKU, for one size or for every size.

    Args:
        sku: Product code, e.g. "CC-TEE-WHITE".
        size: Optional size, e.g. "S" or "OS" (one size). Leave out to get every size.
    """
    with connect() as conn:
        rows = conn.execute("SELECT * FROM inventory WHERE sku = ? ORDER BY rowid", (sku,)).fetchall()
        if not rows:
            valid = [r["sku"] for r in conn.execute("SELECT DISTINCT sku FROM inventory ORDER BY sku")]
            return {"error": f"Unknown SKU '{sku}'.", "valid_skus": valid}
    stock = [dict(row) for row in rows]
    if size is not None:
        match = [row for row in stock if row["size"] == size]
        if not match:
            return {"error": f"SKU '{sku}' has no size '{size}'.", "valid_sizes": [row["size"] for row in stock]}
        stock = match
    return {"sku": sku, "name": stock[0]["name"], "stock": stock}


# --- Space -------------------------------------------------------------------


@mcp.tool
def get_lease_status(lease_id: int) -> dict[str, Any]:
    """Look up a lease's rent and when it is next due, measured from the shop's today (desk.date_today).

    Args:
        lease_id: Lease id, e.g. the lease_id on a rent_notice ticket.
    """
    with connect() as conn:
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if lease is None:
            valid = [r["id"] for r in conn.execute("SELECT id FROM leases ORDER BY id")]
            return {"error": f"Unknown lease id {lease_id}.", "valid_lease_ids": valid}
        today = shop_today(conn)
    days_until_due = days_between(today, lease["next_due"])
    return {
        **dict(lease),
        "date_today": today,
        "days_until_due": days_until_due,
        "overdue": days_until_due < 0,
    }


# --- Money -------------------------------------------------------------------


@mcp.tool
def get_cash_balance(account: str | None = None) -> dict[str, Any]:
    """Cash on hand: one account, or every account and the total. Cash only goes out in this shop.

    Args:
        account: Optional account name, e.g. "checking". Leave out to see every account.
    """
    with connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name")]
        today = shop_today(conn)
    if account is not None:
        rows = [r for r in rows if r["name"] == account]
        if not rows:
            return {"error": f"Unknown account '{account}'."}
    return {"date_today": today, "accounts": rows, "total_balance": round(sum(r["balance"] for r in rows), 2)}


@mcp.tool
def list_invoices(
    status: Literal["open", "paid", "all"] = "open",
    vendor_id: int | None = None,
    invoice_id: int | None = None,
) -> dict[str, Any]:
    """Vendor invoices with the vendor's name and how overdue each open one is (measured from desk.date_today).
    An open invoice means the vendor won't ship new product until it's paid.

    Args:
        status: "open" (unpaid, the default), "paid", or "all".
        vendor_id: Optional, only this vendor's invoices.
        invoice_id: Optional, just this one invoice.
    """
    query = "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE 1 = 1"
    params: list[Any] = []
    if status != "all":
        query += " AND i.status = ?"
        params.append(status)
    if vendor_id is not None:
        query += " AND i.vendor_id = ?"
        params.append(vendor_id)
    if invoice_id is not None:
        query += " AND i.id = ?"
        params.append(invoice_id)
    with connect() as conn:
        rows = [dict(r) for r in conn.execute(query + " ORDER BY i.due_date", params)]
        today = shop_today(conn)
    for row in rows:
        if row["status"] == "open":
            overdue_by = days_between(row["due_date"], today)
            row["days_overdue"] = max(overdue_by, 0)
            row["overdue"] = overdue_by > 0
    return {
        "date_today": today,
        "invoice_count": len(rows),
        "total_amount": round(sum(r["amount"] for r in rows), 2),
        "invoices": rows,
    }


@mcp.tool
def list_vendors() -> dict[str, Any]:
    """Every vendor with what they supply, lead time, expected arrival if ordered today, and whether an
    open unpaid invoice is stopping them from shipping."""
    with connect() as conn:
        vendors = [dict(r) for r in conn.execute("SELECT * FROM vendors ORDER BY id")]
        today = shop_today(conn)
        for v in vendors:
            open_invoices = open_invoices_for(conn, v["id"])
            v["arrival_if_ordered_today"] = (date.fromisoformat(today) + timedelta(days=v["lead_days"])).isoformat()
            v["open_invoices"] = open_invoices
            v["can_ship"] = not open_invoices
    return {"date_today": today, "vendors": vendors}


@mcp.tool
def get_pricing(sku: str, discount_percent: float | None = None, qty: int | None = None) -> dict[str, Any]:
    """Unit cost, list price, and margin for a SKU. Optionally, the price and margin after a discount,
    and totals for a quantity.

    Args:
        sku: Product code, e.g. "CC-HOOD-NAVY".
        discount_percent: Optional discount off list price, e.g. 15 for 15%.
        qty: Optional quantity, for order totals.
    """
    with connect() as conn:
        row = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if row is None:
            valid = [r["sku"] for r in conn.execute("SELECT sku FROM pricing ORDER BY sku")]
            return {"error": f"No pricing for SKU '{sku}'.", "valid_skus": valid}
    cost, price = row["unit_cost"], row["list_price"]
    result: dict[str, Any] = {
        "sku": sku,
        "unit_cost": cost,
        "list_price": price,
        "margin_per_unit": round(price - cost, 2),
        "margin_percent": round((price - cost) / price * 100, 1),
    }
    if discount_percent is not None:
        if not 0 <= discount_percent < 100:
            return {"error": "discount_percent must be at least 0 and below 100."}
        sale = round(price * (1 - discount_percent / 100), 2)
        result["discount"] = {
            "discount_percent": discount_percent,
            "unit_price": sale,
            "margin_per_unit": round(sale - cost, 2),
            "margin_percent": round((sale - cost) / sale * 100, 1),
            "below_cost": sale < cost,
        }
    if qty is not None:
        result["qty"] = qty
        result["total_at_list"] = round(price * qty, 2)
        result["total_cost"] = round(cost * qty, 2)
        if "discount" in result:
            result["discount"]["total"] = round(result["discount"]["unit_price"] * qty, 2)
            result["discount"]["total_margin"] = round(result["discount"]["margin_per_unit"] * qty, 2)
    return result


# --- Payments ----------------------------------------------------------------


@mcp.tool
def request_payment(
    kind: Literal["invoice", "rent", "purchase_order"],
    requested_by: str,
    reason: str,
    ref_id: int | None = None,
    vendor_id: int | None = None,
    sku: str | None = None,
    size: str | None = None,
    qty: int | None = None,
    account: str = "checking",
    ticket_id: int | None = None,
) -> dict[str, Any]:
    """Queue a payment for HUMAN APPROVAL. No cash moves: this only adds a pending request to the
    dashboard. The amount and payee come from the database, never from the caller.

    Args:
        kind: "invoice" (ref_id = invoice id), "rent" (ref_id = lease id), or "purchase_order"
            (vendor_id, sku, size, qty; cost = qty x unit cost).
        requested_by: Which agent is asking, e.g. "accounting".
        reason: One or two sentences on why this should be paid, for the human approver.
        ref_id: Invoice id or lease id.
        vendor_id: Purchase orders only: the vendor to order from.
        sku: Purchase orders only: the product.
        size: Purchase orders only: the size.
        qty: Purchase orders only: how many units.
        account: Cash account to pay from (default "checking").
        ticket_id: Optional ticket this payment resolves.
    """
    with connect() as conn:
        if conn.execute("SELECT 1 FROM cash_accounts WHERE name = ?", (account,)).fetchone() is None:
            return {"error": f"Unknown account '{account}'."}
        warnings: list[str] = []

        if kind == "invoice":
            inv = conn.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (ref_id,),
            ).fetchone()
            if inv is None:
                return {"error": f"Unknown invoice id {ref_id}."}
            if inv["status"] != "open":
                return {"error": f"Invoice {ref_id} is already {inv['status']}."}
            amount, payee, vendor_id = inv["amount"], inv["vendor_name"], inv["vendor_id"]
            sku = size = qty = None
        elif kind == "rent":
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                return {"error": f"Unknown lease id {ref_id}."}
            amount, payee = lease["monthly_rent"], lease["landlord"]
            vendor_id = sku = size = qty = None
        else:
            if vendor_id is None or not sku or not size or not qty or qty <= 0:
                return {"error": "Purchase orders need vendor_id, sku, size, and a positive qty."}
            vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
            if vendor is None:
                return {"error": f"Unknown vendor id {vendor_id}."}
            if conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone() is None:
                return {"error": f"SKU '{sku}' has no size '{size}' in inventory."}
            pricing = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
            if pricing is None:
                return {"error": f"No unit cost for SKU '{sku}', so the order can't be priced."}
            amount, payee, ref_id = round(pricing["unit_cost"] * qty, 2), vendor["name"], None
            blockers = open_invoices_for(conn, vendor_id)
            if blockers:
                warnings.append(
                    f"{vendor['name']} has open invoice(s) {[b['id'] for b in blockers]}; they won't ship until those are paid."
                )

        duplicate = conn.execute(
            "SELECT id FROM payment_requests WHERE status = 'pending' AND kind = ? AND ref_id IS ? "
            "AND vendor_id IS ? AND sku IS ? AND size IS ? AND qty IS ?",
            (kind, ref_id, vendor_id, sku, size, qty),
        ).fetchone()
        if duplicate:
            return {"error": f"A pending request for this already exists (request {duplicate['id']}).", "request_id": duplicate["id"]}

        balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()["balance"]
        pending = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM payment_requests WHERE status = 'pending' AND account = ?",
            (account,),
        ).fetchone()["total"]
        if amount > balance:
            warnings.append(f"${amount:,.2f} is more than the ${balance:,.2f} in {account}; pay_request will refuse it.")
        elif pending + amount > balance:
            warnings.append(
                f"With other pending requests (${pending:,.2f}) this totals ${pending + amount:,.2f}, more than the "
                f"${balance:,.2f} in {account}. Not all of them can be approved."
            )

        cur = conn.execute(
            "INSERT INTO payment_requests (kind, ref_id, vendor_id, sku, size, qty, amount, payee, account, ticket_id, "
            "reason, requested_by, requested_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
            (kind, ref_id, vendor_id, sku, size, qty, amount, payee, account, ticket_id, reason, requested_by, now_utc()),
        )
        request = dict(conn.execute("SELECT * FROM payment_requests WHERE id = ?", (cur.lastrowid,)).fetchone())
    return {
        "request": request,
        "balance": balance,
        "pending_total_including_this": round(pending + amount, 2),
        "warnings": warnings,
        "note": "Pending human approval. No cash has moved.",
    }


@mcp.tool
def list_payment_requests(status: Literal["pending", "paid", "rejected", "all"] = "pending") -> dict[str, Any]:
    """Payment requests waiting for (or already given) a human decision.

    Args:
        status: "pending" (default), "paid", "rejected", or "all".
    """
    query = "SELECT * FROM payment_requests"
    params: tuple = ()
    if status != "all":
        query += " WHERE status = ?"
        params = (status,)
    with connect() as conn:
        rows = [dict(r) for r in conn.execute(query + " ORDER BY id", params)]
    return {"count": len(rows), "total_amount": round(sum(r["amount"] for r in rows), 2), "requests": rows}


@mcp.tool
def pay_request(request_id: int, approved_by: str) -> dict[str, Any]:
    """HUMAN ONLY: pay a pending request after a person approves it in the dashboard. Agents never get
    this tool. Refuses if the payment would take the account below zero.

    On success, in one transaction: adds a row to payments, takes the amount out of the cash account,
    marks an invoice paid or moves a lease's next_due forward one month, and marks the request paid.

    Args:
        request_id: The payment request to pay.
        approved_by: The name of the person approving it.
    """
    approver = approved_by.strip()
    if not approver or approver.lower() in AGENT_NAMES:
        return {"error": "Payments need a named human approver, not an agent."}
    with connect() as conn:
        req = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"error": f"Unknown payment request {request_id}."}
        if req["status"] != "pending":
            return {"error": f"Request {request_id} is already {req['status']}."}
        balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (req["account"],)).fetchone()["balance"]
        new_balance = round(balance - req["amount"], 2)
        if new_balance < 0:
            return {
                "error": "Refused: not enough cash. Balances can't go negative.",
                "account": req["account"],
                "balance": balance,
                "amount": req["amount"],
                "short_by": round(-new_balance, 2),
            }
        if req["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                return {"error": f"Invoice {req['ref_id']} is no longer open."}

        today = shop_today(conn)
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (req["kind"], req["ref_id"] if req["kind"] != "purchase_order" else request_id, req["amount"],
             req["account"], today, approver),
        )
        payment_id = cur.lastrowid
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (new_balance, today, req["account"]))
        updated: dict[str, Any] = {}
        if req["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            updated["invoice"] = {"id": req["ref_id"], "status": "paid"}
        elif req["kind"] == "rent":
            next_due = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()["next_due"]
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (add_one_month(next_due), req["ref_id"]))
            updated["lease"] = {"id": req["ref_id"], "old_next_due": next_due, "new_next_due": add_one_month(next_due)}
        conn.execute(
            "UPDATE payment_requests SET status = 'paid', decided_by = ?, decided_at = ?, payment_id = ? WHERE id = ?",
            (approver, now_utc(), payment_id, request_id),
        )
        payment = dict(conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone())
    return {"paid": True, "payment": payment, "balance_before": balance, "balance_after": new_balance, "updated": updated}


@mcp.tool
def reject_payment_request(request_id: int, rejected_by: str, note: str = "") -> dict[str, Any]:
    """HUMAN ONLY: reject a pending payment request from the dashboard. No cash moves.

    Args:
        request_id: The payment request to reject.
        rejected_by: The name of the person rejecting it.
        note: Optional reason.
    """
    person = rejected_by.strip()
    if not person or person.lower() in AGENT_NAMES:
        return {"error": "Rejections need a named human, not an agent."}
    with connect() as conn:
        req = conn.execute("SELECT status FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"error": f"Unknown payment request {request_id}."}
        if req["status"] != "pending":
            return {"error": f"Request {request_id} is already {req['status']}."}
        conn.execute(
            "UPDATE payment_requests SET status = 'rejected', decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?",
            (person, now_utc(), note, request_id),
        )
    return {"rejected": True, "request_id": request_id}


if __name__ == "__main__":
    mcp.run(show_banner=False)
