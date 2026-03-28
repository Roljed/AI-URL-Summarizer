# URL Summarizer Agent

An OpenAI-powered agent that fetches a webpage, produces a structured summary (title, category, bullet points), and caches results in SQLite. You can drive it from a **Typer CLI** or a **Twilio WhatsApp webhook** that replies with the summary.

## Architecture & Impact

- **Agentic summarization pipeline** — Uses the OpenAI API with tool calling (page fetch) and **Pydantic structured outputs** so every summary is validated and consistent for downstream UX (CLI or WhatsApp).
- **Durable local state without extra infrastructure** — **SQLite** backs URL result caching and **per-sender rate limiting** (usage logs), keeping ops simple while supporting fair use and repeat traffic.
- **Production-oriented webhook** — **FastAPI** exposes a Twilio-compatible form POST; the handler validates senders, enforces limits, and **returns HTTP 200 quickly** so carriers do not retry storm the service while long-running work finishes out-of-band.
- **Dual interfaces, one core** — The same `run_agent` logic serves interactive **Typer** workflows and **async WhatsApp** replies, reducing duplication and drift between dev and prod paths.
- **Cloud-ready packaging** — Dependencies are locked with **uv**; the app respects **`PORT`** (e.g. Render) and initializes the database at startup so tables exist on every deploy.

## System Design

Modules are split by responsibility so the LLM layer, persistence, HTTP edge, and CLI stay testable and replaceable.

| File | Role |
|------|------|
| `main.py` | Typer CLI (`summarize`, `status`, `history`). |
| `server.py` | FastAPI app, `POST /webhook/whatsapp` for Twilio (`Body`, `From`), security gates, rate limit, background dispatch. |
| `agent.py` | OpenAI client, `scrape_website` tool, `run_agent` loop. |
| `database.py` | SQLite (`agent_memory.db`): summary cache, usage logs, `init_db` / rate limit helpers. |
| `schemas.py` | Pydantic models (e.g. `URLSummary`). |

**Data flow (happy path):** Twilio → `server.py` (validate) → `check_rate_limit` / cache-aware `run_agent` in `agent.py` → SQLite read/write via `database.py` → structured `URLSummary` from `schemas.py` → formatted reply over Twilio (or printed in `main.py`).

## Quick Start

**Requirements:** Python **3.14+**, [uv](https://docs.astral.sh/uv/).

```bash
cd url-summarizer-agent
uv sync
```

Create a `.env` in the project root (the app resolves it next to `server.py` / `agent.py`, so it works even when the working directory is not the project root).

### Environment variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | Agent | OpenAI API key for chat completions and structured output. |
| `TWILIO_ACCOUNT_SID` | Server | Twilio Account SID. |
| `TWILIO_AUTH_TOKEN` | Server | Twilio Auth Token. |
| `TWILIO_WHATSAPP_NUMBER` | Server | **Sender** WhatsApp number from Twilio (e.g. Sandbox `whatsapp:+14155238886`), **not** the customer’s number. Must differ from the recipient ([Twilio 63031](https://www.twilio.com/docs/errors/63031)). |
| `ALLOWED_USERS` | Server | Comma-separated allowlist of Twilio `From` values (exact match, e.g. `whatsapp:+1501234567`). **If unset or empty, every sender is rejected** — set at least your own WhatsApp `From` for testing. |

### CLI

```bash
uv run python main.py summarize "https://example.com/article"
uv run python main.py status
uv run python main.py history
uv run python main.py history --titles-only
```

Summaries are stored in `agent_memory.db` (gitignored by default).

### API server

```bash
uv run python server.py
```

Default bind: `http://0.0.0.0:8000` (or the `PORT` environment variable when set).

## Production BKM: Asynchronous Webhook Flow

Webhook providers (including Twilio/Meta) expect a **timely HTTP response**. If the handler waits for scraping, LLM calls, and Twilio sends, the request can exceed provider timeouts and trigger **retries**, duplicate work, and noisy logs.

**Pattern used here:**

1. **`POST /webhook/whatsapp`** (or `/webhook/whatsapp/`) receives `application/x-www-form-urlencoded` data: **`Body`** (message text, typically a URL) and **`From`** (sender).
2. **Synchronous gates only** — Allowlist and **rate limit** (10 requests per 12 hours per sender, tracked in SQLite) run in the request. Rejected or limited callers still receive **HTTP 200** with a small JSON body (`Unauthorized user ignored.` or `Rate limited`) so the platform does not treat the endpoint as failed. Rate-limited users get a WhatsApp notice when Twilio is configured.
3. **Return immediately after scheduling work** — For allowed traffic, the handler **`return`s `{"message": "Processing URL..."}` right away** and registers **`process_and_notify`** as a **FastAPI background task**. That task runs `run_agent` and sends the WhatsApp reply via Twilio when finished.
4. **Separation of concerns** — The HTTP request lifecycle stays short; **slow I/O and LLM work** move off the critical path of the webhook response.

Configure “When a message comes in” in Twilio to this HTTPS URL. Use your **Twilio Console WhatsApp sender** as `TWILIO_WHATSAPP_NUMBER`; the customer’s number is the webhook **`From`**, passed as `to` when sending the reply.

## License

This project is licensed under the [MIT License](LICENSE).
