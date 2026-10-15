# AI Prompts Log

## Setup

This section contains the prompts and conversation for HW5 setup.

### 2026-10-14

**User:** [3 screenshots of the assignment: Scenario, Data / Rules of this shop, and "Use your PORTKEY_API_KEY for AI calls."]
datahw5.zip in downloads

use only gpt 6 luna for this assingment

**Assistant:** Read the database in `datahw5.zip` and the Lecture 10 multi-agent starter; the user stopped the turn before anything was built.

**User:** were just getting startd

**Assistant:** Unzipped `datahw5.zip` into `HW 5/data/`, copied it to the working database `data/campus_customs_new.db`, started this log, and summarized the 9 tables and 3 open tickets.

**User:** [3 screenshots of the assignment steps: "Open data/campus_customs.db and look through every table and its fields.", "Copy the original file to data/campus_customs_new.db", "Start output/harness.md."]
for each table list the fields and one short line on why that tbale matters for the agent were building (output/harness.md)

**Assistant:** Created `output/harness.md` with a section for each of the 9 tables listing every field (type and a short note) and one line on why the table matters to the agent team.

**User:** Um, write an MCP server in MCP underscore server forward dash using fast MCP. It's going to talk to data forward slash campus underscore customs dot new dot DB. Um, and then every agent in this project is going to use tools in this MCP server. You're going to add uh, more tools later. For now, just write two tools you know that we're going to need for the tickets in the database. Um, keep the names clear. Don't invent any data.

**User:** try agaion

**Assistant:** Created the HW 5 `.venv` with FastMCP 4.1.0 and wrote `mcp_server/server.py` on `data/campus_customs_new.db` with two read-only tools, `list_open_tickets` and `check_stock(sku, size)`; tested both through an MCP client.

**User:** Okay, at a short um, MCP underscore server, four dash readme dot md file that explains what the MCP server is for. Which database file it uses and the three tools it has. Um, in output harness forward slash harness.md, list each of your three MCP tools for each tool include which table it reads, which ticket it helps unlock, and one sentence and why the tool is good.

**Assistant:** The server had two tools, so added a third, `get_lease_status(lease_id)` (reads `leases` and `desk`) for the rent ticket; wrote `mcp_server/README.md` and added an "MCP tools" section to `output/harness.md` with each tool's table, ticket, and why it's good.

**User:** Add your MPC NC MCP server to this project so that MyPutter can call the tool save the connection JSON text in .mcp.json and the project root. After that, with your uh, the MyPutter connected, test each of the three MCP tools. And save the test evidence and output slash MCP underscore smoke.json. For each tool, include the prompt you asked the VibeCoder the tool name, and the tool output.

**Assistant:** Wrote `HW 5/.mcp.json` (stdio server `campus-customs`) and confirmed it launches and lists all three tools; the smoke test with Claude Code connected still needs a session opened in the `HW 5` folder, since this session's root is `AI Foundations` and MCP servers only load at session start.

**User:** Put .mcp.json at the AI Foundations root instead so this workspace loads it.

**Assistant:** Moved `.mcp.json` to the `AI Foundations` root (paths now `HW 5/.venv/bin/python` and `HW 5/mcp_server/server.py`), removed the `HW 5` copy, and confirmed it launches with all three tools; Claude Code picks it up on the next session start.

**User:** All right, now build the agentic team for campus customs using Pydantic AI. Boss, inventory, accounting, facilities, and customer service include prompts, models, and agent loops that they can delegate work to each other with full connectivity. Then put the agent prompts in backend slash prompts one file per agent. Put data types in backend forward slash models.py in the agent files under backend forward slash your layout can vary as long as the five roles are clear between the agents. Use the port key underscore API underscore key and only GPT-6 Luna for each of these agents. Um, and then for these agents, write um, some detailed prompts that cover the agent's work um, for what they're supposed to do.

**Assistant:** Confirmed `gpt-6-luna` works through Portkey, then built the five-agent Pydantic AI team: `backend/models.py`, a detailed prompt per agent plus shared `shop_rules.md` in `backend/prompts/`, one agent file per role in `backend/agents/` with an `ask_teammate` tool for full connectivity, and `run_team.py`. A test run on ticket 102 worked through Boss → Facilities → Accounting and correctly reported that no tool shows the cash balance yet.

**User:** try again

**Assistant:** Re-ran the team on all three open tickets: all five agents worked (14 delegations, 21 MCP tool calls, no errors) and returned 101 `blocked`, 102 `needs_info`, 103 `needs_info` with two customer drafts, because no tool yet shows cash, invoices, vendors, or pricing; the database was unchanged.

**User:** Add MCP tools for cash balance, invoices, vendors, and pricing, plus a pay tool that requires human approval and refuses negative balances.

**Assistant:** Added `get_cash_balance`, `list_invoices`, `list_vendors`, `get_pricing`, and a two-step payment flow (`request_payment` queues a pending request in a new `payment_requests` table; human-only `pay_request` / `reject_payment_request` pay or reject it, and `pay_request` refuses negative balances), tested all 11 tools on a scratch copy, gave each agent its tools (none get the human-only ones), updated the prompts, added `reset_db.py`, and re-ran the team: rent ($2,400) and invoice 501 ($840) are queued for approval, ticket 103 is offered 8 hoodies at 10% off with the 12-unit restock blocked by cash, and no cash moved.

**User:** Any add any other tools or agents um, that the MCP needs so they can work on open tickets, shop facts, come from the MCP server over uh, data slash campus underscore customs underscore new. .db um, then why are the agents so that they append to output slash audit underscore trail.json um, so that when they're running for each agent loop step record enough to audit later append this file and output slash harness.md lists each agent and each MCP tool um, and some like safety sections about guardrails

**Assistant:** Added five MCP tools (`get_shop_date`, `get_ticket`, `update_ticket`, `save_customer_draft`, `list_customer_drafts`; 16 total) and kept the five agents; wired every agent loop through `agent.iter()` so each step is appended to `output/audit_trail.json` (run id, agent, chain, task, tool calls with args and results, tokens, stop reason, errors); updated prompts and tool lists; and rewrote `output/harness.md` to list every agent and MCP tool plus "Audit trail" and "Safety and guardrails" sections. A full run queued rent and invoice 501 for approval, saved two customer drafts, and set each ticket's status.

**User:** Um, uh, before you wire the backend, write down what you expect the team to do on each open ticket, build output slash desk underscore ticket slash HTML, a page that you can double click with one tab per ticket. Um, also add empty cache and reflection tabs for later problems. On each of the ticket tabs, fill an expected section only. Leave room for the inactual section. Um, for after you run the agents.

**Assistant:** Built `output/desk_tickets.html`, a self-contained page with tabs for tickets 101, 102, 103 plus empty Cache and Reflection tabs; each ticket tab has a filled Expected section (facts and tools, who does what, expected board state, a good draft, what happens after approval, guardrails) and an empty dashed Actual section. Figures re-checked against the original database; tabs checked in a browser.

**User:** um, make sure in the tickets expected section, um, never mind that.

**Assistant:** Acknowledged; no changes made.

**User:** All right, the React front-end dashboard needs a back-end it can call. That's what we're going to work on next. We're gonna, well, now we're going to work on the back-end. In back-end slash main.py use fast API and add routes that do the following. It's going to return three tickets and whether each is open or resolved. It's going to take a ticket. ID and run the agent team on that ticket. It can also return recent agent events, what each agent said, and which tools they use, so that the board can refresh. It's also going to approve a payment or purchase after a human clicks approve. Um, it can also return the current checking balance from cash underscore accounts.

**Assistant:** Wrote `backend/main.py` (FastAPI) with routes for tickets (`GET /api/tickets` with `is_open`, `GET /api/tickets/{id}`), running the team on one ticket in the background (`POST /api/tickets/{id}/run`, one run at a time), polling agent events (`GET /api/events?since=`), runs, payments (list, approve, reject), and `GET /api/cash`; added a `list_tickets` MCP tool and API types in `models.py`. Tested every route on a live server: ticket 102 run queued rent, approving rent and invoice took cash $3,400 → $160, the $264 purchase order was refused with 409; then reset the database and documented the API in `output/harness.md`.

**User:** uvicorn main:app --reload --port 8000 Um, from the backend folder, start the server with this. This is going to turn on the backend. Add a HTTP localhost colon 8000. Um, so the front end dashboard can call those routes. And then also in an output slash harness.md list each route in one line.

**Assistant:** Started the backend in a Terminal tab from `backend/` with `uvicorn main:app --reload --port 8000` (HW 5 `.venv` active), added a `GET /` route listing every API route, confirmed all routes and CORS for the dashboard (`localhost:5173`) respond at http://localhost:8000, and rewrote the Backend API section of `output/harness.md` with one line per route.

**User:** All right, now we're going to build the front-end dashboard. And uh, front-end, with React plus Vite plus TypeScript. Um, this is going to let you pick uh, list all three tickets, let you pick one ticket and start the agent team on it. It's also going to let you show each agent and what they are saying, um, it can mark a ticket resolved when it finishes, it can show a short summary, of what each agent did, and it can also let a human approve of a pay or purchase when asked. Um, and also show checking balance. Make the dashboard look good. Um, this is where people are going to sit. So make it look kind of professional with a Times New Roman font.

**Assistant:** Built `frontend/` (React + Vite + TypeScript, Times New Roman, dark purple and white): ticket list with open/resolved status, start-the-team button, live agent cards with what each is saying and a one-line summary, Boss's decision, activity feed, approval queue with confirm steps, customer drafts, and the checking balance. Added a `POST /api/tickets/{id}/resolve` route, fixed a race where the last events arrived after a run showed done, and made the backend reload runs after a restart. Tested a ticket 101 run end to end from the dashboard.

**User:** ok its taken too long lets jsust go with what we have - skip the ticket

**Assistant:** Stopped testing and wrote up the dashboard in `output/harness.md`; the ticket 102 run already started from the dashboard was left to finish in the backend.

**User:** Um, next, the uh, front end should talk to the back end at localhost 8000. On the back end, allow the by page origin. Um, so the browser is allowed to call these routes. Start the board with npm run dev. This is going to open the React desk in the browser. Um, I can do that, I guess.

**Assistant:** Confirmed the dashboard calls `http://localhost:8000` and widened the backend CORS to the Vite page origin (`localhost:5173`, `127.0.0.1`, or another local port) while refusing other hosts; checked GET and POST preflights; stopped my preview server so `npm run dev` can use port 5173; noted it in `output/harness.md`.

**User:** All right, let's go reset the database data slash campus customs new.db. Um, then let's run three tickets. One hundred one, one hundred two, and one hundred three until they're resolved. Uh, and then open output slash desk tickets dot html from problem six. On each ticket tab, fill the actual section from this run. Uh, what the agents did and what tools they used.

**Assistant:** Reset the working database and started the team on tickets 101, 102, and 103 one at a time through the backend API.

**User:** All right, on the uh, cache tab of the same um, output slash desk tickets.html itemize the money. Start checking balance for each ticket. How cash change when that ticket resolved? And why? Ending checking balance much should match cash accounts in the working database. Um, also, for for each ticket, save output slash resolved underscore tickets.json. Um, for each ticket, this is going to have ID, final status, and a short outcome. And then also output slash resolved underscore board.html. This is going to be a page you can double click um, on the React board for each resolved ticket.

**Assistant:** Added the new outputs to the plan (reading "cache" as the Cash tab) while the runs continued; 101 and 102 finished waiting on approval.

**User:** its fine just dont do ticket 103

**Assistant:** Stopped the ticket 103 run by restarting the backend; it had already set 103 to `needs_info` and saved a draft. Asked who should approve the two pending payments.

**User:** I approve both payments: request 2 (rent, $2,400) and request 1 (invoice 501, $840). Approve them as Tyson Zhang, mark 101 and 102 resolved, and fill in the outputs.

**Assistant:** Approved request 2 (rent, $3,400 → $1,000) and request 1 (invoice 501, → $160) as Tyson Zhang and marked 101 and 102 resolved; filled the Actual sections in `output/desk_tickets.html` (agents' steps and tools per ticket, 103 marked as partly run), renamed the Cache tab to Cash and itemized the money ($3,400 → $160, matching `cash_accounts`), wrote `output/resolved_tickets.json`, and generated `output/resolved_board.html`, a double-clickable snapshot of the board for the two resolved tickets.

**User:** lets open output/desk tickets.html and write in the reflection tab. 

about the agents performance. what are ssome problems campus customes might face that this agent team could solve with the cisting tools. also how is the performance of this agnet.

**Assistant:** Filled the Reflection tab in `output/desk_tickets.html`: a per-run performance table from the audit trail (steps, tool calls, hand-offs, tokens, errors), what went well and what didn't, a table of problems Campus Customs could hand the team with the existing 17 tools (e.g. the Crest Mug stockout via Elm City Gifts), what the tools can't do yet, and an overall verdict with next changes.

**User:** push the code to uh, public GitHub repository. And also put it into output slash GitHub dot underscore URL dot TXT. Um, remember, don't push the real.env to the GitHub repo.

**Assistant:** Prepared `HW 5` as its own git repo with a `.gitignore` (excludes `.env`, `.venv`, `node_modules`, and the data `.db` files), `.env.example`, and a README; scanned the 66 staged files and confirmed the real Portkey key and `.env` are not in them; committed locally. The GitHub CLI isn't installed, so asked the user to create the empty public repo before pushing over SSH.
