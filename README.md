# Campus Customs Multi-Agent Operations

An agent team that runs the Campus Customs shop's ticket board: customer orders, rent, unpaid bills, and discount requests. Three pieces talk to each other:

- **MCP server** (`mcp_server/`, FastMCP): 17 shop tools over a SQLite database. Every shop fact comes from here.
- **FastAPI backend** (`backend/`): a five-agent Pydantic AI team (Boss, Inventory, Accounting, Facilities, Customer Service) with full connectivity, plus the API the dashboard calls.
- **React dashboard** (`frontend/`, React + Vite + TypeScript): pick a ticket, start the team, watch each agent work, approve payments, and see the checking balance.

All agents use **gpt-6-luna** through Portkey. No payment happens without a person clicking Approve, and the pay tool refuses anything that would take cash below zero.

How it all works (tables, tools, agents, API, audit trail, guardrails) is in [`output/harness.md`](output/harness.md). Expected-vs-actual results, the cash ledger, and a reflection are in [`output/desk_tickets.html`](output/desk_tickets.html). The resolved tickets are in [`output/resolved_tickets.json`](output/resolved_tickets.json) and [`output/resolved_board.html`](output/resolved_board.html).

## Requirements

- Python 3.12+ and Node.js 20+
- A Portkey API key with access to `gpt-6-luna`
- The course data pack (`data.zip`), which isn't in this repository

## Setup

```bash
# 1. Data: unzip the course data pack so you have data/campus_customs.db, then make the working copy
unzip data.zip
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python backend/reset_db.py          # copies data/campus_customs.db -> data/campus_customs_new.db

# 2. Secrets
cp .env.example .env                # then put your PORTKEY_API_KEY in .env (never commit it)
```

## Run

```bash
# Terminal 1: backend on http://localhost:8000 (with the .venv active)
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2: dashboard on http://localhost:5173
cd frontend && npm install && npm run dev
```

Or run the team from the command line: `cd backend && python run_team.py --ticket 102`.

To use the MCP server from Claude Code, add it to a `.mcp.json` with command `.venv/bin/python` and args `["mcp_server/server.py"]`.

## Layout

```
├── mcp_server/server.py      # FastMCP server: 17 tools on data/campus_customs_new.db
├── backend/
│   ├── main.py               # FastAPI routes for the dashboard
│   ├── agents/               # boss.py, inventory.py, accounting.py, facilities.py, customer_service.py,
│   │                         # base.py (ask_teammate delegation), config.py (model + MCP), team.py (agent loops)
│   ├── prompts/              # one prompt per agent + shop_rules.md
│   ├── models.py             # data types
│   ├── audit.py              # per-step audit trail -> output/audit_trail.json
│   ├── run_team.py           # command-line runner
│   └── reset_db.py           # reset the working database
├── frontend/                 # React + Vite + TypeScript dashboard
├── output/                   # harness.md, desk_tickets.html, resolved_*, audit_trail.json, team_runs/
└── AI_prompts.md             # log of the prompts used to build this
```
