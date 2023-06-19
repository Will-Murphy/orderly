# TODO: make this dynamic based on menu and reponse name (json loads from test file)
from typing import Dict


def get_mock_response(menu="archies_deli") -> Dict:
    return {
        "id": "cmpl-7T39BZZ2FwlKrniJ3pSswHu9a9QoD",
        "object": "text_completion",
        "created": 1687157965,
        "model": "text-davinci-003",
        "choices": [
            {
                "text": "\n{'human_response': 'Coming right up!', \n'menu_items': ['Yahoo with Bacon'], \n'menu_item_details': {'Yahoo with Bacon': '9.0'}}",
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 641, "completion_tokens": 51, "total_tokens": 692},
    }
