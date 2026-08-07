"""
ARIA - tool calling support.
Defines tools the LLM can invoke and the actual Python functions that
execute them. Ollama's tool-calling support lets the model decide when it
needs current information it doesn't have, rather than hallucinating an answer.
"""
from datetime import datetime

from ddgs import DDGS

# ---- Tool schemas, given to the model so it knows what's available ----
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web for current information, facts, or anything that "
                "might have changed since your training data, or that you're not "
                "confident about. ONLY use this for genuine factual lookups, such "
                "as specific current events, statistics, prices, or recent "
                "developments you don't already know. Do NOT use this for casual "
                "conversation, greetings, small talk, opinions, jokes, creative "
                "requests, or anything you can already answer naturally without "
                "looking anything up. Do NOT use this for the current date, time, "
                "or news headlines - use get_current_datetime or search_news instead."
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
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": (
                "Gets the current date and time right now. Always use this for any "
                "question about today's date, the current time, or the day of the "
                "week. This is instant and always accurate, unlike web search."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": (
                "Searches for actual current news headlines and articles on a topic. "
                "Use this instead of search_web whenever the user asks for news, "
                "current events, or 'what's happening' type questions, since it "
                "returns real news articles rather than generic web pages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The news topic to search for, e.g. 'technology' or a specific subject.",
                    }
                },
                "required": ["topic"],
            },
        },
    },
]

MAX_RESULTS = 4


def get_current_datetime(**_) -> str:
    """Returns the real current date/time from the system clock - instant, no search needed."""
    now = datetime.now()
    return f"The current date and time is {now.strftime('%A, %B %d, %Y, %I:%M %p')}."


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

    return (
        f"Current, up to date web search results for '{query}':\n"
        f"{result_text}\n\n"
        f"Use this information directly to answer. This is more current and "
        f"reliable than anything you already know, since your training data "
        f"has a cutoff date and this search just happened right now."
    )


def search_news(topic: str) -> str:
    """
    Runs a DuckDuckGo news search - returns actual current news articles,
    unlike search_web which returns generic web pages.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(topic, max_results=MAX_RESULTS))
    except Exception as e:
        print(f"[search_news error: {e}]")
        return "News search failed, no results available."

    if not results:
        print("[search_news: no results returned]")
        return "The news search returned no results."

    summary_lines = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        date = r.get("date", "")
        summary_lines.append(f"- [{date}] {title}: {body}")

    result_text = "\n".join(summary_lines)
    print(f"[search_news results for '{topic}']:\n{result_text}")

    return (
        f"Current news results for '{topic}':\n"
        f"{result_text}\n\n"
        f"Use this information directly to answer, including the dates so the "
        f"user knows how recent each item is."
    )


# Maps tool name (as the model will call it) to the actual Python function.
TOOL_DISPATCH = {
    "search_web": search_web,
    "get_current_datetime": get_current_datetime,
    "search_news": search_news,
}