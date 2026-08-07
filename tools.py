"""
ARIA - tool calling support.
Defines tools the LLM can invoke (currently: web search) and the actual
Python functions that execute them. Ollama's tool-calling support lets the
model decide when it needs current information it doesn't have, rather
than hallucinating an answer.
"""
from ddgs import DDGS

# ---- Tool schema, given to the model so it knows what's available ----
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web for current information, facts, news, or anything "
                "that might have changed since your training data, or that you're "
                "not confident about. Use this whenever the user asks about current "
                "events, recent facts, prices, weather, or anything you don't know "
                "for certain."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A short, specific search query, like you'd type into a search engine.",
                    }
                },
                "required": ["query"],
            },
        },
    }
]

MAX_RESULTS = 4


def search_web(query: str) -> str:
    """
    Runs a DuckDuckGo search and returns a short plain-text summary of the
    top results, formatted for an LLM to read and turn into a spoken answer.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=MAX_RESULTS))
    except Exception as e:
        print(f"[search_web error: {e}]")
        return "Web search failed, no results available."

    if not results:
        print("[search_web: no results returned]")
        return "The search returned no results."

    summary_lines = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        summary_lines.append(f"- {title}: {body}")

    result_text = "\n".join(summary_lines)
    print(f"[search_web results for '{query}']:\n{result_text}")

    # Explicitly label this as current, authoritative information - small
    # models otherwise tend to fall back on stale training data even when
    # tool results are provided, so we make it unambiguous which to trust.
    return (
        f"Current, up to date web search results for '{query}':\n"
        f"{result_text}\n\n"
        f"Use this information directly to answer. This is more current and "
        f"reliable than anything you already know, since your training data "
        f"has a cutoff date and this search just happened right now."
    )


# Maps tool name (as the model will call it) to the actual Python function.
TOOL_DISPATCH = {
    "search_web": search_web,
}