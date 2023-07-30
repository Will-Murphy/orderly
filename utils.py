from typing import Dict, List


def get_innermost_items(d: dict) -> Dict:
    innermost_keys = {}
    for k, v in d.items():
        if isinstance(v, dict):
            innermost_keys.update(get_innermost_items(v))
        else:
            innermost_keys[k] = v
    return innermost_keys


def get_generic_order_waiting_phrases() -> List[str]:
    return [
        "One moment please...",
        "Just a second, please...",
        "Bear with me for a moment...",
        "Please hold on a bit...",
        "Allow me a moment, please...",
        "Give me a short while...",
        "Could you wait a moment, please...",
        "Let me check that for you...",
        "Hang on for a sec, please...",
        "A moment to sort this out, please...",
        "Stand by for a minute, please...",
        "Please be patient for a moment...",
        "Just a minute, if you could...",
        "Please give me a moment...",
        "Hold on just a moment...",
        "Allow me a sec to verify that...",
        "I'll be right with you...",
        "Kindly wait a moment...",
        "Please hold on for a moment...",
        "Could you hold on for a sec?...",
        "One brief moment, please...",
        "Please give me a sec...",
        "Please stand by a moment...",
        "Allow me a brief moment...",
        "Could you spare a moment?...",
        "Just need a second, please...",
    ]
