import json
from collections import Counter

import typer

from agent import run_agent
from database import fetch_all_summary_json_rows, fetch_history_rows, init_db

app = typer.Typer(help="An AI Agent that scrapes and summarizes web pages.")

@app.command()
def summarize(
    url: str = typer.Argument(..., help="The fully qualified URL you want the agent to read.")
):
    """
    Kicks off the Agent loop to summarize the provided URL.
    """
    # Call the orchestrator loop we already built
    result = run_agent(url)

    # Output the strongly-typed data
    if result and "error" not in result.title.lower():
        print("\n" + "="*50)
        print(f"TITLE: {result.title}")
        print(f"CATEGORY: {result.category}")
        print("KEY POINTS:")
        for point in result.key_points:
            print(f" - {point}")
        print("="*50 + "\n")

@app.command()
def status():
    """
    Shows the current database statistics (Count of Categories).
    """
    conn = init_db()
    rows = fetch_all_summary_json_rows(conn)

    if not rows:
        print("\n[System Log] 📭 The database is currently empty.")
        return

    categories = []
    for row in rows:
        # Deserialize the JSON string back into a Python dictionary
        data = json.loads(row[0])
        categories.append(data.get("category", "Unknown"))

    # Counter automatically tallies up the occurrences in the list
    counts = Counter(categories)

    print("\n📊 Database Status: Category Counts")
    for cat, count in counts.items():
        print(f" - {cat}: {count}")
    print("\n")

@app.command()
def history(
    # This creates a boolean flag. Default is False.
    # Users can trigger it with `--titles-only` or the short flag `-t`
    titles_only: bool = typer.Option(False, "--titles-only", "-t", help="Output only the titles, excluding URLs.")
):
    """
    Lists all processed URLs chronologically from first to last.
    """
    conn = init_db()
    rows = fetch_history_rows(conn)

    print("\n📚 Agent Processing History:")
    for index, row in enumerate(rows, start=1):
        url = row[0]
        data = json.loads(row[1])
        title = data.get("title", "No Title")

        if titles_only:
            print(f"{index}. {title}")
        else:
            print(f"{index}. {title} \n   🔗 {url}")
    print("\n")

if __name__ == "__main__":
    # This single line boots up the Typer CLI application
    app()

    # test_url = "https://en.wikipedia.org/wiki/Intelligent_agent"
    # test_url = "https://en.wikipedia.org/wiki/DevOps"
