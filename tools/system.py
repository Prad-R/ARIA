"""
ARIA - misc system tools that don't fit audio/display (currently just
the system clock). Grows to cover things like battery status, disk
space, etc. if those get added later.
"""
from datetime import datetime

SCHEMAS = [
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
]


def get_current_datetime(**_) -> str:
    """Returns the real current date/time from the system clock - instant, no search needed."""
    now = datetime.now()
    return f"The current date and time is {now.strftime('%A, %B %d, %Y, %I:%M %p')}."


DISPATCH = {
    "get_current_datetime": get_current_datetime,
}