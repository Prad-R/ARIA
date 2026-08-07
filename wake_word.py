"""
ARIA - wake word detection.
Fuzzy-matches the Whisper transcript against known "ARIA" mishearings,
since openWakeWord has no pretrained "ARIA" model and training a custom
one is a bigger separate project.
"""
import difflib
import re

import config


def strip_punctuation(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text).lower().strip()


def find_wake_word_index(text: str):
    """
    Returns the index (in the raw word list) of the first word/word-pair that
    fuzzy-matches the wake word, or None if no match is found.
    Checks both single words and adjacent two-word pairs (e.g. "are ya").
    """
    raw_words = text.strip().split()
    cleaned_words = [strip_punctuation(w) for w in raw_words]

    for i in range(min(len(cleaned_words), 3)):  # only check near the start
        # single word check
        for variant in config.WAKE_WORD_VARIANTS:
            similarity = difflib.SequenceMatcher(None, cleaned_words[i], variant).ratio()
            if similarity >= config.WAKE_WORD_MATCH_THRESHOLD:
                return i
        # two-word check (e.g. "are ya")
        if i + 1 < len(cleaned_words):
            pair = f"{cleaned_words[i]} {cleaned_words[i + 1]}"
            for variant in config.WAKE_WORD_VARIANTS:
                similarity = difflib.SequenceMatcher(None, pair, variant).ratio()
                if similarity >= config.WAKE_WORD_MATCH_THRESHOLD:
                    return i + 1  # command starts after both words
    return None
