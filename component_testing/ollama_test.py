"""
Step 3: Confirm the LLM responds correctly via Ollama.
Sends test prompts to Ollama and prints responses + latency.
"""
import ollama
import time

MODEL = "llama3.2:3b"  # change if you pulled a different model

SYSTEM_PROMPT = (
    "You are ARIA (short for Adaptive & Responsive Intelligence Agent), a helpful voice assistant. "
    "Keep responses concise and conversational, "
    "since they will be spoken aloud, not read."
)

def ask(prompt: str):
    print(f"Sending prompt to {MODEL}: \"{prompt}\"\n")
    start = time.time()

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    elapsed = time.time() - start
    reply = response["message"]["content"]

    print(f"--- Response ({elapsed:.2f}s) ---")
    print(reply)
    return reply

if __name__ == "__main__":
    test_prompt = "What's a good name for a voice assistant? Answer in one sentence."
    ask(test_prompt)

    print("\n" + "=" * 50)
    print("Now testing a follow-up, to confirm the basic call works twice:")
    print("=" * 50 + "\n")
    ask("What time zone should I assume you're in if I don't tell you?")