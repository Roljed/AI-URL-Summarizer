import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

from database import get_cached_summary_json, init_db, save_summary_to_cache
from schemas import URLSummary

# 1. Load environment variables securely
load_dotenv()

# 2. Initialize the OpenAI Client
# It will automatically look for the OPENAI_API_KEY in your environment
client = OpenAI()

print("Environment loaded, client initialized, and Prompt Contract defined.")

# 4. The Execution Function (The "Hands")
def scrape_website(url: str) -> str:
    """Fetches the text from a website, returning up to 10,000 characters."""
    print(f"\n[System Log] 🔧 Executing Tool: Scraping {url}...")
    try:
        # We add a timeout. Never let an agent hang indefinitely on a bad network call.
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # BKM: Truncate the raw HTML to protect the LLM's context window.
        content = response.text
        return content[:10000]
    except Exception as e:
        # BKM: If the tool fails, return the error to the LLM so it knows what happened!
        # Do not just crash the script. Let the agent attempt to reason about the failure.
        return f"Error scraping website: {str(e)}"


# 5. The Tool Definition
# We describe our Python function so the LLM knows HOW and WHEN to use it.
agent_tools = [
    {
        "type": "function",
        "function": {
            "name": "scrape_website",
            "description": "Scrapes a URL and returns the webpage content. Use this to read articles before summarizing them.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The fully qualified URL to scrape (e.g., https://example.com)",
                    }
                },
                "required": ["url"],
            },
        }
    }
]

print("Tool functions and schemas successfully loaded.")


def run_agent(url: str, auto_approve: bool = True):
    """
    Summarize a URL via the agent loop. Tool calls run immediately (no stdin / no approval prompt).
    auto_approve is accepted for API clarity; execution is always unattended.
    """
    print(f"\n[System Log] 🧠 Starting Agent Loop for: {url}")

    # --- CACHE CHECK ---
    conn = init_db()

    cached_json = get_cached_summary_json(conn, url)

    if cached_json:
        print(f"[System Log] ⚡ CACHE HIT! Skipping LLM execution. Loading from memory.")
        # We use Pydantic's built-in method to convert the JSON string back into our class
        return URLSummary.model_validate_json(cached_json)

    # 1. State Management: The Conversation History
    # We initialize it with a System Prompt (the rules) and the User Prompt (the trigger).
    messages = [
        {
            "role": "system",
            "content": "You are an expert research agent. You must use the `scrape_website` tool to read the URL provided. Once you have read it, output the final summary."
        },
        {"role": "user", "content": f"Please summarize this link: {url}"}
    ]

    # 2. First API Call: Planning & Tool Invocation
    # We hand the LLM our state and our tools. We DO NOT force the Pydantic schema yet,
    # because we want it to use the tool first.
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=agent_tools,
    )

    # Extract the LLM's reply and append it to our state history.
    message = response.choices[0].message
    messages.append(message)

    # 3. Intercept and execute the tool
    if message.tool_calls:
        for tool_call in message.tool_calls:
            if tool_call.function.name == "scrape_website":
                args = json.loads(tool_call.function.arguments)
                target_url = args["url"]
                scraped_text = scrape_website(target_url)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": scraped_text
                })

        # 4. Second API Call: The Extraction (Using our Prompt Contract)
        print("[System Log] 🧠 Tool cycle complete. Fetching final response...")

        final_response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=messages,
            response_format=URLSummary,
        )

        summary = final_response.choices[0].message.parsed

        # --- CACHE SAVING LOGIC (From Step 9) ---
        # Only save to cache if the title isn't an error message
        if "error" not in summary.title.lower():
            print("[System Log] 💾 Saving new summary to SQLite database...")
            save_summary_to_cache(conn, url, summary.model_dump_json())

        return summary
