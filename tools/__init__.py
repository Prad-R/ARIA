"""
ARIA - tool calling support.

This package defines the tools the LLM can invoke and the actual Python
functions that execute them. Each submodule owns one area:

    web.py       search_web (general + news via kind arg)   (DuckDuckGo)
    system.py    get_current_datetime
    audio.py     control_volume                 (pactl)
    display.py   control_brightness             (brightnessctl)
    _shell.py    shared subprocess-run-and-check-returncode helper

Everything else in the codebase (llm.py in particular) should keep
importing `TOOLS` and `TOOL_DISPATCH` from `tools` exactly as before -
this file is the only place that needs to know the submodules exist.
To add a new tool: create/extend a submodule with a SCHEMAS list and a
DISPATCH dict in the same shape, then add it to the lists below.
"""
from . import web, system, audio, display

TOOLS = [
    *web.SCHEMAS,
    *system.SCHEMAS,
    *audio.SCHEMAS,
    *display.SCHEMAS,
]

TOOL_DISPATCH = {
    **web.DISPATCH,
    **system.DISPATCH,
    **audio.DISPATCH,
    **display.DISPATCH,
}