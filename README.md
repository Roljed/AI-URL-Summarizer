# URL Summarizer Agent

An OpenAI-powered agent that fetches a webpage, produces a structured summary (title, category, bullet points), and caches results in SQLite. You can drive it from a **Typer CLI** or a **Twilio WhatsApp webhook** that replies with the summary.

## Requirements

- Python **3.14+**
- [uv](https://docs.astral.sh/uv/) (recommended) or another PEP 517 installer

## Setup

```bash
cd url-summarizer-agent
uv sync
```

Create a `.env` file in the project root (this path is loaded explicitly by the app so it works even when the working directory differs).

## Environment variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | Agent | OpenAI API key for chat completions and structured output. |
| `TWILIO_ACCOUNT_SID` | Server | Twilio Account SID. |
| `TWILIO_AUTH_TOKEN` | Server | Twilio Auth Token. |
| `TWILIO_WHATSAPP_NUMBER` | Server | **Sender** WhatsApp number from Twilio (e.g. Sandbox `whatsapp:+14155238886`), **not** the customer’s number. Must differ from the recipient ([Twilio 63031](https://www.twilio.com/docs/errors/63031)). |
| `ALLOWED_USERS` | Server | Comma-separated allowlist of Twilio `From` values (must match exactly, e.g. `whatsapp:+1501234567`). **If unset or empty, every sender is rejected** by the webhook guard—set at least your own WhatsApp `From` for testing. |

## Project layout

| File | Role |
|------|------|
| `main.py` | Typer CLI (`summarize`, `status`, `history`). |
| `server.py` | FastAPI app and `POST /webhook/whatsapp` for Twilio (form fields `Body`, `From`). |
| `agent.py` | OpenAI client, `scrape_website` tool, `run_agent` loop. |
| `database.py` | SQLite cache (`agent_memory.db`) helpers. |
| `schemas.py` | Pydantic models (e.g. `URLSummary`). |

## CLI

Run from the project directory:

```bash
uv run python main.py summarize "https://example.com/article"
uv run python main.py status
uv run python main.py history
uv run python main.py history --titles-only
```

Summaries are stored in `agent_memory.db` (gitignored by default).

## WhatsApp webhook (FastAPI)

Start the API server:

```bash
uv run python server.py
```

Default bind: `http://0.0.0.0:8000`.

- **Endpoint:** `POST /webhook/whatsapp` or `POST /webhook/whatsapp/` (both registered).
- **Twilio:** Configure “When a message comes in” to this URL; Twilio sends `application/x-www-form-urlencoded` fields including `Body` (message text, typically a URL) and `From` (sender).
- The handler returns `200` immediately with `{"message": "Processing URL..."}` and runs `run_agent` in a **background task**, then sends the formatted reply via Twilio.

Use your **Twilio Console WhatsApp sender** as `TWILIO_WHATSAPP_NUMBER`; the customer’s number comes from the webhook `From` field as `to` when sending the reply.

## License

This project is licensed under the [MIT License](LICENSE).
