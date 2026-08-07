"""
ARIA - web search tool, backed by DuckDuckGo via ddgs.

search_web and search_news used to be two separate tools with near-identical
descriptions. The small local model this project targets struggled to
reliably invoke either one when given several similarly-worded tools to pick
between (see project notes on tool-call suppression). Merging them into one
tool with a "kind" argument removes that ambiguity - there's only one search
tool to consider, and "kind" is a small, low-stakes classification the model
already has to make anyway ("is this news or not") rather than a decision
about which of two tools to reach for.
"""
from ddgs import DDGS

MAX_RESULTS = 4

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Searches the internet. Use this for any question whose answer "
                "you are not fully confident about, including current events, "
                "facts, statistics, prices, sports results, or news."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A short, specific search query, like you'd type into a search engine.",
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["general", "news"],
                        "description": (
                            "'news' if the user is asking for news, headlines, or "
                            "'what's happening' with a topic. 'general' for everything else."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def _search_general(query: str) -> str:
    """Runs a DuckDuckGo text search and returns a short plain-text summary."""
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


def _search_news(query: str) -> str:
    """Runs a DuckDuckGo news search - returns actual current news articles."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=MAX_RESULTS))
    except Exception as e:
        print(f"[search_web(news) error: {e}]")
        return "News search failed, no results available."

    if not results:
        print("[search_web(news): no results returned]")
        return "The news search returned no results."

    summary_lines = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        date = r.get("date", "")
        summary_lines.append(f"- [{date}] {title}: {body}")

    result_text = "\n".join(summary_lines)
    print(f"[search_web(news) results for '{query}']:\n{result_text}")

    return (
        f"Current news results for '{query}':\n"
        f"{result_text}\n\n"
        f"Use this information directly to answer, including the dates so the "
        f"user knows how recent each item is."
    )


def search_web(query: str, kind: str = "general") -> str:
    """
    Dispatches to a general web search or a news search depending on `kind`.
    Single entry point so the LLM only has one search tool to consider.
    """
    if kind == "news":
        return _search_news(query)
    return _search_general(query)


DISPATCH = {
    "search_web": search_web,
}