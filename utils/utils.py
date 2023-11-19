from typing import Dict


def get_innermost_items(d: dict) -> Dict:
    innermost_keys = {}
    for k, v in d.items():
        if isinstance(v, dict):
            innermost_keys.update(get_innermost_items(v))
        else:
            innermost_keys[k] = v
    return innermost_keys
