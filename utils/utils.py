from typing import Dict
import json
import base64
import zlib


def get_innermost_items(d: dict) -> Dict:
    innermost_keys = {}
    for k, v in d.items():
        if isinstance(v, dict):
            innermost_keys.update(get_innermost_items(v))
        else:
            innermost_keys[k] = v
    return innermost_keys

def encode_json(data):
    # Convert JSON to string and compress
    compressed_data = zlib.compress(json.dumps(data).encode('utf-8'))
    # Encode compressed data to base64 for readability
    return base64.b64encode(compressed_data).decode('utf-8')



