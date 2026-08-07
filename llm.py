"""
ARIA - LLM conversation handling via Ollama.
Keeps a rolling conversation history, capped so a long-running background
service doesn't grow context (and thus latency) unboundedly.
"""
import ollama

import config

conversation_history = [{"role": "system", "content": config.SYSTEM_PROMPT}]


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
    response = ollama.chat(
        model=config.OLLAMA_MODEL,
        messages=conversation_history,
        options={"num_ctx": config.OLLAMA_NUM_CTX},
    )
    reply = response["message"]["content"]
    conversation_history.append({"role": "assistant", "content": reply})
    trim_history()
    return reply
