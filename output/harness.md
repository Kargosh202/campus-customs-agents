# Harness

This file explains how the Campus Customs multi-agent operations team works.

## Database tables

The original shop database is `data/campus_customs.db` and stays untouched. The MCP server and backend work on the copy, `data/campus_customs_new.db`, which can be reset from the original before each full run.

### `desk`
One row: the shop's clock.

| Field | Type | Notes |
|---|---|---|
| `date_today` | TEXT | "Today" for the shop (2026-08-31) |
| `notes` | TEXT | Free-text desk notes (empty) |

**Why it matters:** Every agent uses this date, not the real clock, to decide what is overdue or due soon.

### `tickets`
One row per open request on the board (3 rows).

| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Primary key |
| `type` | TEXT | Kind of request: `customer_order`, `rent_notice`, `price_override` |
| `requester` | TEXT | Who asked (customer, landlord, student org) |
| `subject` | TEXT | Short title |
| `sku` | TEXT | Product involved, if any (matches `inventory.sku`) |
| `size` | TEXT | Size involved, if any |
| `qty` | INTEGER | Quantity requested, if any |
| `lease_id` | INTEGER | Linked lease, if any (references `leases.id`) |
| `invoice_id` | INTEGER | Linked invoice, if any (references `invoices.id`) |
| `status` | TEXT | Ticket state (all `open` at the start) |
| `notes` | TEXT | The request in plain words |
| `created_at` | TEXT | When the ticket arrived (ISO timestamp with time zone) |

**Why it matters:** This is the team's work queue. The Boss reads each ticket's type and linked SKU, lease, or invoice to decide who works on it, then closes it when it's resolved.

### `inventory`
One row per SKU and size (10 rows; primary key is `sku` + `size`).

| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT | Product code, e.g. `CC-TEE-WHITE` |
| `name` | TEXT | Product name |
| `size` | TEXT | S, M, L, XL, or OS (one size) |
| `qty` | INTEGER | Units on hand |
| `location` | TEXT | Where it sits in the shop (aisle) |

**Why it matters:** The Inventory agent's source of truth for stock by SKU and size, so it can spot a shortfall before anyone promises a customer an item.

### `pricing`
One row per SKU (4 rows).

| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT | Primary key, matches `inventory.sku` |
| `unit_cost` | REAL | What the shop pays per unit |
| `list_price` | REAL | What the customer pays per unit |

**Why it matters:** Accounting compares cost and price to check the margin on a discount request and to cost out a restock order.

### `vendors`
One row per supplier (3 rows).

| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Primary key |
| `name` | TEXT | Vendor name |
| `specialty` | TEXT | What they supply (apparel reprint, mugs and small goods, local courier) |
| `lead_days` | INTEGER | Days from order to delivery |

**Why it matters:** The Inventory agent matches a shortfall to the vendor that can restock it and gives a real arrival date (today + `lead_days`).

### `leases`
One row per rented space (1 row).

| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Primary key |
| `space_name` | TEXT | The space being rented |
| `landlord` | TEXT | Who the rent is owed to |
| `monthly_rent` | REAL | Rent amount |
| `next_due` | TEXT | Date the next rent payment is due |
| `notes` | TEXT | Free-text notes (empty) |

**Why it matters:** The Facilities agent checks the rent amount and due date against `desk.date_today`, and moves `next_due` forward once rent is paid.

### `cash_accounts`
One row per bank account (1 row).

| Field | Type | Notes |
|---|---|---|
| `name` | TEXT | Primary key, e.g. `checking` |
| `balance` | REAL | Cash available |
| `date` | TEXT | Date the balance is as of |

**Why it matters:** This is all the money the shop has. Accounting uses it to decide which bills can be paid, and the pay tool refuses any payment that would push it below zero.

### `payments`
One row per payment made (empty at the start).

| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Primary key |
| `kind` | TEXT | What type of bill was paid (for example an invoice or rent) |
| `ref_id` | INTEGER | Id of the invoice or lease that was paid |
| `amount` | REAL | Amount paid |
| `account` | TEXT | Cash account it came out of |
| `paid_at` | TEXT | When it was paid |
| `approved_by` | TEXT | The human who approved it |

**Why it matters:** The record of every payment. Each approved payment adds a row, and `approved_by` is the proof of the human approval the rules require.

### `invoices`
One row per vendor bill (1 row).

| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Primary key |
| `vendor_id` | INTEGER | Vendor who billed (references `vendors.id`) |
| `amount` | REAL | Amount owed |
| `due_date` | TEXT | Date payment was due |
| `status` | TEXT | Bill state (`open` = unpaid) |
| `description` | TEXT | What the bill is for |

**Why it matters:** Accounting watches these for overdue bills, and an open invoice stops that vendor from shipping, so Inventory has to check here before planning a restock.

### Added to the working copy by the MCP server

The server creates these two tables in `campus_customs_new.db` (never in the original). Resetting the working copy clears them.

| Table | Fields | Why it matters |
|---|---|---|
| `payment_requests` | `id`, `kind` (invoice / rent / purchase_order), `ref_id`, `vendor_id`, `sku`, `size`, `qty`, `amount`, `payee`, `account`, `ticket_id`, `reason`, `requested_by`, `requested_at`, `status` (pending / paid / rejected), `decided_by`, `decided_at`, `decision_note`, `payment_id` | The queue between "an agent wants to pay" and "a human paid". Cash only moves from here, after approval |
| `customer_drafts` | `id`, `ticket_id`, `recipient`, `message`, `drafted_by`, `created_at`, `status` (always `draft`) | Customer messages stay on the board for a human to read; nothing is sent |

## MCP tools

The MCP server is `mcp_server/server.py` (FastMCP) on `data/campus_customs_new.db`. It has 17 tools. Every shop fact an agent uses comes from one of them; the backend never opens the database itself.

| Tool | Reads | Writes | Used by |
|---|---|---|---|
| `get_shop_date` | `desk` | | Boss, Inventory, Accounting, Facilities |
| `list_open_tickets` | `tickets` | | all five |
| `list_tickets` | `tickets`, `customer_drafts`, `payment_requests` | | Backend API (dashboard) |
| `get_ticket` | `tickets`, `customer_drafts`, `payment_requests` | | all five, Backend API |
| `update_ticket` | `tickets`, `payment_requests`, `desk` | `tickets` | Boss |
| `check_stock` | `inventory` | | Boss, Inventory, Accounting, Customer Service |
| `get_lease_status` | `leases`, `desk` | | Boss, Accounting, Facilities |
| `get_cash_balance` | `cash_accounts`, `desk` | | Boss, Accounting |
| `list_invoices` | `invoices`, `vendors`, `desk` | | Boss, Inventory, Accounting |
| `list_vendors` | `vendors`, `invoices`, `desk` | | Boss, Inventory, Accounting |
| `get_pricing` | `pricing` | | Boss, Inventory, Accounting, Customer Service |
| `request_payment` | `invoices`, `leases`, `vendors`, `pricing`, `inventory`, `cash_accounts` | `payment_requests` | Accounting |
| `list_payment_requests` | `payment_requests` | | Boss, Accounting, Facilities |
| `save_customer_draft` | `tickets` | `customer_drafts` | Customer Service |
| `list_customer_drafts` | `customer_drafts` | | Boss, Customer Service |
| `pay_request` | `payment_requests`, `cash_accounts`, `invoices`, `leases`, `desk` | `payments`, `cash_accounts`, `invoices`, `leases`, `payment_requests` | **Human only** (`POST /api/payments/{id}/approve`) |
| `reject_payment_request` | `payment_requests` | `payment_requests` | **Human only** (`POST /api/payments/{id}/reject`) |


### `list_open_tickets()`
- **Reads:** `tickets`
- **Unlocks:** All three tickets (101, 102, 103). It's how the Boss sees the board.
- **Why it's good:** It hands the Boss every open ticket with its linked SKU, lease, or invoice in one call, so routing starts from the real board instead of a guess.

### `get_shop_date()`
- **Reads:** `desk`
- **Unlocks:** All three tickets, since "overdue" (invoice 501) and "due in 2 days" (rent) are measured from it
- **Why it's good:** Every agent uses the shop's date, 2026-08-31, instead of the real clock, so date math is the same everywhere.

### `list_tickets()`
- **Reads:** `tickets`, `customer_drafts`, `payment_requests`
- **Unlocks:** The dashboard's board of all three tickets
- **Why it's good:** One call gives every ticket with `is_open` and how many drafts and pending payments it has, so the board can show progress without the API touching the database.

### `get_ticket(ticket_id)`
- **Reads:** `tickets`, `customer_drafts`, `payment_requests`
- **Unlocks:** Any single ticket, including ones already moved off `open`
- **Why it's good:** One call shows a ticket with everything the team already did for it, which prevents duplicate drafts and payment requests.

### `update_ticket(ticket_id, status, note, updated_by)`
- **Reads and writes:** `tickets` (checks `payment_requests`)
- **Unlocks:** All three tickets: it's how the Boss records the final call on the board
- **Why it's good:** The status and a dated note stay on the ticket for the next person, the original notes are kept, and a ticket can't be marked `resolved` while its payment is still waiting for a human.

### `save_customer_draft(ticket_id, message, drafted_by)`
- **Reads:** `tickets`; **writes** `customer_drafts`
- **Unlocks:** Ticket 101 (Tauhid's reply) and ticket 103 (Yale AI Club's reply)
- **Why it's good:** Drafts land on the board, addressed to the ticket's requester, and there's no way to send them, which keeps the "don't email customers" rule.

### `list_customer_drafts(ticket_id)`
- **Reads:** `customer_drafts`
- **Unlocks:** Tickets 101 and 103
- **Why it's good:** The Boss can check that the saved draft matches the final decision before closing out a ticket.

### `check_stock(sku, size)`
- **Reads:** `inventory`
- **Unlocks:** Ticket 101 (tee in S, 0 on hand) and ticket 103 (20 hoodies in M, 8 on hand)
- **Why it's good:** It gives the exact count for the exact size asked for, so the Inventory agent can measure a shortfall instead of assuming something is in stock.

### `get_lease_status(lease_id)`
- **Reads:** `leases` and `desk`
- **Unlocks:** Ticket 102 (rent due on the Chapel Street shop)
- **Why it's good:** It works out days until due from the shop's own date, so the Facilities agent knows how urgent the rent is without doing date math itself.

### `get_cash_balance(account)`
- **Reads:** `cash_accounts` and `desk`
- **Unlocks:** Tickets 101, 102, and 103, since every payment or purchase order draws on the same $3,400 balance
- **Why it's good:** Accounting can't promise a payment fits without the real balance, and this is the only place it lives.

### `list_invoices(status, vendor_id, invoice_id)`
- **Reads:** `invoices`, `vendors`, and `desk`
- **Unlocks:** Ticket 101 (linked invoice 501) and ticket 103 (the hoodie vendor's open invoice)
- **Why it's good:** It shows which bills are unpaid and how many days overdue they are, which is what decides whether a vendor will ship.

### `list_vendors()`
- **Reads:** `vendors`, `invoices`, and `desk`
- **Unlocks:** Ticket 101 (tee restock) and ticket 103 (hoodie shortfall)
- **Why it's good:** In one call Inventory sees who can restock a product, when it would arrive, and whether an unpaid invoice blocks shipping (`can_ship`).

### `get_pricing(sku, discount_percent, qty)`
- **Reads:** `pricing`
- **Unlocks:** Ticket 103 (bulk discount) and the cost of any purchase order
- **Why it's good:** The tool does the margin arithmetic at list price and at a discount, so a discount decision rests on exact numbers rather than the model's math.

### `request_payment(kind, ...)`
- **Reads:** `invoices`, `leases`, `vendors`, `pricing`, `inventory`, `cash_accounts`; **writes** `payment_requests`
- **Unlocks:** Ticket 101 (pay invoice 501), ticket 102 (rent), ticket 103 (restock purchase order)
- **Why it's good:** It puts a payment in front of a human without moving cash, takes the amount and payee from the database so an agent can't mistype them, and warns when pending requests add up to more than the balance.

### `list_payment_requests(status)`
- **Reads:** `payment_requests`
- **Unlocks:** All three tickets, since it shows what's already waiting for approval
- **Why it's good:** It stops duplicate requests and lets agents tell "queued" apart from "paid".

### `pay_request(request_id, approved_by)` (human only)
- **Reads and writes:** `payment_requests`, `cash_accounts`, `payments`, `invoices`, `leases`
- **Unlocks:** Ticket 101 (invoice 501 paid, so the vendor ships again) and ticket 102 (rent paid, lease rolls forward a month)
- **Why it's good:** It is the only way cash moves. It runs only from a person's approval, refuses any payment that would take the balance below zero, and updates every related table in one transaction.

### `reject_payment_request(request_id, rejected_by, note)` (human only)
- **Writes:** `payment_requests`
- **Unlocks:** Any request a person decides against
- **Why it's good:** A "no" is recorded with who said it and why, and no cash moves.

## Agent team

Five Pydantic AI agents in `backend/agents/`, all on **gpt-6-luna** (high reasoning) through Portkey with `PORTKEY_API_KEY`. Prompts are in `backend/prompts/` (one file per agent, plus `shop_rules.md`, which every agent gets), and data types are in `backend/models.py`. Five roles cover every ticket type on the board, so no extra agents were needed.

| Agent | File | Prompt | What it does | MCP tools | Returns |
|---|---|---|---|---|---|
| Boss | `agents/boss.py` | `boss.md` | Reads each ticket, routes work, settles cash conflicts between tickets, makes the final call, records it on the ticket | `get_shop_date`, `list_open_tickets`, `get_ticket`, `update_ticket`, `check_stock`, `get_lease_status`, `get_cash_balance`, `list_invoices`, `list_vendors`, `get_pricing`, `list_payment_requests`, `list_customer_drafts` | `BoardPlan` (a `TicketPlan` per ticket) |
| Inventory | `agents/inventory.py` | `inventory.md` | Stock by SKU and size, shortfalls, which vendor can restock, arrival dates, vendor blockers | `get_shop_date`, `list_open_tickets`, `get_ticket`, `check_stock`, `list_vendors`, `list_invoices`, `get_pricing` | `SpecialistReport` |
| Accounting | `agents/accounting.py` | `accounting.md` | Cash, invoices, margins; queues payments and purchase orders for human approval | `get_shop_date`, `list_open_tickets`, `get_ticket`, `check_stock`, `get_lease_status`, `get_cash_balance`, `list_invoices`, `list_vendors`, `get_pricing`, `request_payment`, `list_payment_requests` | `SpecialistReport` |
| Facilities | `agents/facilities.py` | `facilities.md` | Leases, rent amount and due date, urgency; hands rent to Accounting | `get_shop_date`, `list_open_tickets`, `get_ticket`, `get_lease_status`, `list_payment_requests` | `SpecialistReport` |
| Customer Service | `agents/customer_service.py` | `customer_service.md` | Drafts customer messages from verified facts and saves them on the board | `list_open_tickets`, `get_ticket`, `check_stock`, `get_pricing`, `save_customer_draft`, `list_customer_drafts` | `SpecialistReport` (with `draft_message`) |

- **Full connectivity:** every agent has `ask_teammate(teammate, task)` (`agents/base.py`), so any agent can hand work to any other. The teammate runs its own agent loop and hands back a `SpecialistReport`.
- **Agent loops:** each agent runs Pydantic AI's loop (model → MCP tools or `ask_teammate` → model …) step by step with `agent.iter()` (`agents/team.py`) until it returns its structured output.
- **One MCP connection:** `agents/config.py` opens one stdio connection to `mcp_server/server.py` for the whole run and gives each role only the tools in its `TOOLS` list.
- **Data types (`models.py`):** `TeamDeps` (who is working, the delegation chain, the run id, the event log), `ProposedAction` (anything that should happen, with `requires_human_approval`, `blocked_by`, and `payment_request_id`), `Fact` (a value and the tool it came from), `SpecialistReport`, `TicketPlan`, `BoardPlan`, and `AuditEntry` / `AuditToolCall` for the audit trail.
- **Run it:** from `backend/`, reset with `../.venv/bin/python reset_db.py`, then `../.venv/bin/python run_team.py` (all open tickets) or `--ticket 102`. Each run's plan and events are saved to `output/team_runs/`.

## Backend API

`backend/main.py` is the FastAPI app the React dashboard calls at **http://localhost:8000**. Start it from `backend/` with the HW 5 `.venv` active: `uvicorn main:app --reload --port 8000`. It keeps one MCP connection open for its whole life and gets every shop fact through MCP tools; it never opens the database. CORS allows the dashboard's page origin, `http://localhost:5173` (and `127.0.0.1`, or another local port if Vite picks one), so the browser may call these routes; pages from any other host are refused. Request and response shapes are in `models.py`; interactive docs are at http://localhost:8000/docs.

- `GET /`: lists every API route, as a quick check that the backend is up.
- `GET /api/health`: model, shop date, and whether a team run is going (`get_shop_date`).
- `GET /api/tickets`: all three tickets with their status and `is_open`, open until resolved (`list_tickets`).
- `GET /api/tickets/{id}`: one ticket with its customer drafts and payment requests (`get_ticket`).
- `POST /api/tickets/{id}/run`: starts the agent team on that ticket in the background and returns a `run_id` at once (202); 409 if another run is going, since runs share one cash balance.
- `POST /api/tickets/{id}/resolve`: a person marks the ticket resolved, body `{"resolved_by": "<name>"}`; 409 while a payment for it is still pending (`update_ticket`).
- `GET /api/runs`: runs since the server started (reloaded from `output/team_runs/` after a restart, back to the last database reset), newest first, with status (running / done / error).
- `GET /api/runs/{run_id}`: one run's status and the Boss's final `BoardPlan`.
- `GET /api/events?since=&run_id=&ticket_id=`: recent agent events (who asked whom, which tool with what arguments and result, what each agent said); poll with `since=<last_seq>` to refresh.
- `GET /api/payments?status=`: payment and purchase-order requests, pending by default (`list_payment_requests`).
- `POST /api/payments/{id}/approve`: a person clicked Approve, body `{"approved_by": "<name>"}`; pays it, or 409 if cash would go below zero (`pay_request`).
- `POST /api/payments/{id}/reject`: a person clicked Reject, body `{"rejected_by": "<name>", "note": ""}`; no cash moves (`reject_payment_request`).
- `GET /api/cash`: current checking balance from `cash_accounts` (`get_cash_balance`).

Each finished run is also saved to `output/team_runs/`, and every agent-loop step goes to the audit trail as usual.

## Dashboard

`frontend/` is a React + Vite + TypeScript app. It talks to the backend at `http://localhost:8000` (`src/api.ts`; override with `VITE_API_URL`). Start the backend first, then start the board from `frontend/` with `npm install` (once) and `npm run dev`, and open http://localhost:5173. It is set in Times New Roman, dark purple and white.

- **Masthead:** shop date, whether the agent team is working, the checking balance (with pending total and the balance if everything pending were paid), and a "Signed in as" name used for approvals.
- **Tickets:** all three tickets with their status, open or resolved, and flags for "team working", payments awaiting approval, and drafts. Click one to open it.
- **Ticket panel:** the request and its details, the Boss's dated notes, **Start the agent team** (one run at a time), and **Mark resolved** (disabled until a name is entered and no payment for the ticket is pending).
- **Agent team:** a card per agent showing its state (working, done, not needed), what it is saying right now, a one-line summary of what it did (tool calls, who it asked, payments queued, drafts saved), its final report, and the tools it used.
- **Boss's decision:** the final call, actions with request ids, reasoning, cash summary, and anything that couldn't be verified.
- **Activity:** the live event feed, filterable by agent, with optional tool results.
- **Needs your approval:** every pending payment or purchase order with the amount, payee, reason, and the balance after approval (red if it would overdraw). Approve and Reject each take a confirm step.
- **Customer drafts:** the latest saved draft for the ticket (marked never sent) and earlier versions.

The dashboard polls every 1.5 seconds while the team works and every 8 seconds otherwise.

## Audit trail

Every agent-loop step of every agent is appended to **`output/audit_trail.json`** as soon as the step finishes (`backend/audit.py`, called from `run_loop` in `agents/team.py`). A step is one model response plus the tool results that came back for it. Each entry records:

| Field | What it holds |
|---|---|
| `timestamp` | When the step finished (UTC) |
| `run_id` | Shared by every agent in one team run, so a whole run can be pulled out |
| `agent`, `chain` | Which agent, and how the work reached it (e.g. `boss → facilities → accounting`) |
| `task` | What the agent was asked to do |
| `step` | 1, 2, 3 … within that agent's loop |
| `model`, `reasoning_effort` | The model that answered (e.g. `gpt-6-luna-global`) and the effort setting |
| `tool_calls` | Each tool called (MCP tools, `ask_teammate`, or the final output) with short arguments and its result |
| `text` | Any text the model wrote |
| `stop_reason`, `ended_run` | Why the model stopped, and whether this step produced the agent's final output |
| `input_tokens`, `output_tokens` | Token use for the step |
| `error` | The error, if the loop failed on this step |

The file is append-only: entries are never removed or rewritten. Each write goes to a temp file that is then swapped in, so a crash can't corrupt earlier entries, and a lock keeps agents running in parallel from overwriting each other. Arguments and results are trimmed to 300 characters and email addresses are masked.

## Safety and guardrails

### Money
- **Human approval for every payment.** Agents can only *queue* a payment (`request_payment`), which moves no cash. Cash moves only through `pay_request`, which only the dashboard calls when a person clicks Approve.
- **Agents can't reach the pay tools.** `pay_request` and `reject_payment_request` are in no agent's tool list, and `mcp_tools()` raises an error if anyone tries to give them to an agent. `pay_request` also refuses an approver named after an agent.
- **No negative balances.** `pay_request` refuses any payment larger than the account balance and reports how short it is. `request_payment` warns when one request, or all pending requests together, would exceed the balance, and Accounting's prompt says to queue only what fits in priority order.
- **Amounts come from the database.** `request_payment` takes the amount and payee from the invoice, lease, or pricing record, so an agent can't mistype or inflate a payment. Duplicate pending requests are refused.
- **Everything updates together.** A payment writes `payments`, lowers the balance, and marks the invoice paid or rolls the lease forward in one transaction.

### Facts
- **One source of facts.** Shop facts come only from MCP tools on `data/campus_customs_new.db`; the backend never opens the database itself. The original `campus_customs.db` is only ever read by `reset_db.py`.
- **No invented numbers.** Every prompt requires each number to come from a tool or arithmetic on tool values, with the source listed in `facts`, and anything unverifiable listed in `unknowns`. Tools do the date and margin arithmetic themselves.
- **Bad input fails clearly.** Unknown SKUs, sizes, tickets, leases, invoices, and accounts return an error with the valid values instead of a guess.
- **The shop's date.** "Today" is `desk.date_today` (via `get_shop_date` and the date fields tools return), never the real clock.

### Customers and the outside world
- **Nothing is sent.** No tool sends email or contacts a vendor or landlord. Customer messages are saved with `save_customer_draft` (always status `draft`).
- **No overpromising.** Customer Service may only mention a discount the Boss approved and an arrival date Inventory confirmed, and never shares cost, margin, vendor, or invoice details.

### Agent loops
- **Least privilege.** Each role gets only the MCP tools its job needs (table above). Only Accounting can queue payments, only the Boss can update tickets, and only Customer Service can save drafts.
- **No runaway loops.** The Boss gets at most 30 model calls per run and a teammate 15 per task. An agent can't delegate to itself or back to anyone already in its chain (no A → B → A ping-pong), and chains stop 3 hand-offs deep.
- **Failures don't crash the team.** If a teammate's loop fails, the agent that asked gets a report saying so and carries on, and the error is written to the audit trail.
- **Tickets stay honest.** `update_ticket` won't mark a ticket `resolved` while one of its payment requests is still waiting for a human, and it appends notes rather than overwriting them.
- **Only the API's approve and reject routes reach the human-only tools,** and they need a person's name in the request body. The API also allows only one team run at a time, so two runs can't plan against the same cash.
- **Secrets.** `PORTKEY_API_KEY` is read from the AI Foundations `.env` and is never logged or written to the audit trail.
