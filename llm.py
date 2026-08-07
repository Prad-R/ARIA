"""
ARIA - LLM conversation handling via Ollama.
Keeps a rolling conversation history, capped so a long-running background
service doesn't grow context (and thus latency) unboundedly.

Supports tool calling: the model can request a web search when it needs
current information rather than guessing. See tools.py for the actual
tool definitions and implementations.
"""
import re

import ollama

import config
from tools import TOOLS, TOOL_DISPATCH

conversation_history = [{"role": "system", "content": config.SYSTEM_PROMPT}]

# Safety cap: if the model somehow keeps requesting tools in a loop,
# stop forcing a final answer after this many rounds rather than hanging.
MAX_TOOL_ROUNDS = 3


def strip_thinking(text: str) -> str:
    """
    Safety net: some models (like Qwen3) can leak raw <think>...</think>
    reasoning into the visible reply if think=False isn't respected by the
    installed Ollama version. This strips it defensively so a misconfigured
    setup never speaks the raw reasoning out loud - it doesn't fix the
    latency cost of that reasoning happening, only prevents it being spoken.
    """
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Handle an unclosed tag too, in case generation got cut off mid-thought.
    cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def trim_history():
    """Keeps the system prompt plus only the most recent N turn-pairs."""
    global conversation_history
    system_msg = conversation_history[0]
    turns = conversation_history[1:]  # everything except system prompt
    max_messages = config.MAX_HISTORY_TURNS * 2  # each turn = 1 user + 1 assistant message
    if len(turns) > max_messages:
        turns = turns[-max_messages:]
    conversation_history = [system_msg] + turns


def ask_llm(user_text: str) -> str:
    conversation_history.append({"role": "user", "content": user_text})

    for _ in range(MAX_TOOL_ROUNDS):
        response = ollama.chat(
            model=config.OLLAMA_MODEL,
            messages=conversation_history,
            tools=TOOLS,
            think=config.OLLAMA_THINK,
            options={"num_ctx": config.OLLAMA_NUM_CTX},
        )
        message = response["message"]
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            # No tool needed (or no more needed) - this is the final answer.
            reply = strip_thinking(message["content"])
            conversation_history.append({"role": "assistant", "content": reply})
            trim_history()
            return reply

        # Record the assistant's tool-call request in history, then execute
        # each requested tool and feed the result back as a "tool" message.
        conversation_history.append(message)
        print(f"[tool call: {[tc['function']['name'] for tc in tool_calls]}]")

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"].get("arguments", {})

            if tool_name not in TOOL_DISPATCH:
                tool_result = f"Unknown tool: {tool_name}"
            else:
                try:
                    tool_result = TOOL_DISPATCH[tool_name](**tool_args)
                except Exception as e:
                    tool_result = f"Tool {tool_name} failed: {e}"

            conversation_history.append({
                "role": "tool",
                "content": tool_result,
                "name": tool_name,
            })

    # Hit MAX_TOOL_ROUNDS without a final answer - ask one last time without
    # tools available, forcing it to just answer with what it has.
    response = ollama.chat(
        model=config.OLLAMA_MODEL,
        messages=conversation_history,
        think=config.OLLAMA_THINK,
        options={"num_ctx": config.OLLAMA_NUM_CTX},
    )
    reply = strip_thinking(response["message"]["content"])
    conversation_history.append({"role": "assistant", "content": reply})
    trim_history()
    return reply