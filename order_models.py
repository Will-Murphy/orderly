import argparse
import ast
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import DefaultDict, Dict, List, Tuple
from logger import Logger

import openai
from speech import listen, speek
from tests.mock_reponse import get_mock_response
from utils import get_innermost_items

openai.api_key = os.getenv("OPENAI_API_KEY")

TEST_MENU_DIR = "tests/test_menus"

USE_FUNCTION_CALLS = True

logger = Logger("order_logger")


@dataclass
class AbstractOrderData:
    def __repr__(self):
        return json.dumps(self.as_dict(), indent=4)

    def __str__(self):
        return self.__repr__()
    
    def as_dict(self):
        raise NotImplementedError


@dataclass
class Menu(AbstractOrderData):
    restaurant_name: str
    full_detail: dict
    flat_menu_items: dict = field(init=False)

    def __post_init__(self):
        self.flat_menu_items = {
            k.title(): v for k, v in get_innermost_items(self.full_detail).items()
        }
        
        
    def as_dict(self):
        return {
            "restaurant_name": self.restaurant_name,
            "full_detail": self.full_detail,
        }

    @classmethod
    def from_file(cls, menu_name: str) -> dict:
        filename = f"{TEST_MENU_DIR}/{menu_name}.json"
        with open(filename, "r") as f:
            menu = json.load(f)
        return Menu(full_detail=menu, restaurant_name=menu["restaurant"])


@dataclass
class Item(AbstractOrderData):
    NAME = "name"
    DETAILS = "details"
    QAUNTITY = "quantity"

    name: str
    details: List[str]
    quantity: int

    def __post_init__(self):
        self.name = self.name.title()

    def __hash__(self) -> int:
        return hash((self.name, (hash(x for x in self.details) or 0), self.quantity))


def human_item_list(items: List[Item]):
    last = ""
    if len(items) > 3:
        last = f" and {items.pop().name}"

    return ", ".join([i.name for i in items]) + last


@dataclass
class Order(AbstractOrderData):
    HUMAN_RESPONSE = "human_response"
    MENU_ITEMS = "menu_items"
    MENU_ITEM_DETAILS = "menu_item_details"
    COMPLETED = "completed"

    menu: Menu
    human_response: str
    menu_items: List[Item]

    unrecognized_items: List[str] = field(default_factory=list)
    processed_order: DefaultDict[Item, Tuple[float, int]] = field(
        default_factory=lambda: defaultdict(lambda: (0, 0))
    )
    total_price: float = 0.0
    completed: str = False

    def as_dict(self):
        return {
            "menu": self.menu.as_dict(),
            "menu_items": [asdict(m) for m in self.menu_items],
            "human_response": self.human_response,
            "processed_order": {k.name: v for k, v in self.processed_order.items()},
            "total_price": self.total_price,
            "unrecognized_items": [asdict(m) for m in self.unrecognized_items],
            "total_price": self.total_price,
            "completed": self.completed,
        }

    def __post_init__(self):
        self.process()

    def process(self):
        self.menu_items = [Item(**item_args) for item_args in self.menu_items]

        for item in self.menu_items:
            if item.name not in self.menu.flat_menu_items.keys():
                self.unrecognized_items.append(item)
                logger.debug(f"Unrecognized item: {item}")
                continue
            else:
                unit_price = self.menu.flat_menu_items[item.name]

                print(f"WSM {unit_price=} {item.quantity=} ")

                subtotal = unit_price * item.quantity

                item_subtotal = self.processed_order[item][0] + subtotal
                item_count = self.processed_order[item][1] + item.quantity

                self.processed_order[item] = (item_subtotal, item_count)

                self.total_price += subtotal
                
    def add_clarified_order(self, c_order: "Order"):
        self.processed_order = {**self.processed_order, **c_order.processed_order}

        self.unrecognized_items = list(c_order.unrecognized_items)

        self.total_price += c_order.total_price
        self.completed = c_order.completed

    def is_complete(self):
        return self.menu_items and not self.unrecognized_items

    @classmethod
    def from_api_reponse(cls, response, menu: Menu) -> "Order":
        if USE_FUNCTION_CALLS:
            reply_content = response.choices[0].message
            string_order_kwargs = reply_content.to_dict()["function_call"]["arguments"]
            order_kwargs = json.loads(string_order_kwargs)
        else:
            string_order_kwargs = response.choices[0].text.strip("\n").strip()
            order_kwargs = ast.literal_eval(response)
        return Order(menu=menu, **order_kwargs)

    @classmethod
    def get_initial_prompt(cls, user_input: str, menu: Menu):
        prompt = (
            f"I have a customer order from the following menu: \n {menu.full_detail}\n"
            f"Here is what the customer has asked for in their own words: \n '{user_input}'. \n"
        )

        return prompt


    def get_clarification_prompt(self, user_input: str, initial_prompt: str) -> str:
        prompt = (
            f"Some user order items were not understood correctly from this menu: \n\n {self.menu.full_detail} \n\n"
            f"\n The items that were not recognized from the above menu are: {human_item_list(self.unrecognized_items)}."
            f"The user has now told use that instead they mean the following: \n '{user_input}'\n"
        )

        return prompt

    def get_human_order_summary(self, speech_only=False) -> str:
        hpo = f"Your order is listed below: \n"

        if speech_only:
            for item, (subtotal, count) in self.processed_order.items():
                hpo += f"\n {count} of {item.name}"
        else:
            for item, (subtotal, count) in self.processed_order.items():
                hpo += f"\n * {item.name}: {count} x {self.menu.flat_menu_items[item.name]} = ${subtotal}"

        hpo += f"\n\nFor a total price of: ${self.total_price} \n"

        return hpo.strip("/n") if speech_only else hpo

    def to_human_response(self):
        print(f"{'='*80}\n")
        print(f"{self.human_response} \n")
        print(f"{self.get_human_order_summary()} \n")
        print(f"{'='*80}\n")
        speek(self.human_response + self.get_human_order_summary(speech_only=True))


ORDER_FUNCTIONS = {
    "process_user_order": {
        "name": "process_user_order",
        "description": (
            f"Processes a users order for a given menu in order to return both a"
            f"human readable response and a itemized transaction summary."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                f"{Order.MENU_ITEMS}": {
                    "type": "array",
                    "description": "A structured mapping to the exact menu items the user has asked for.",
                    "items": {
                        "type": "object",
                        "properties": {
                            f"{Item.NAME}": {
                                "type": "string",
                                "description": "key from ONLY the innermost keys of each menu item mentioned with the greatest specificity item",
                            },
                            f"{Item.QAUNTITY}": {
                                "type": "number",
                                "description": "The quantity of the item.",
                            },
                            f"{Item.DETAILS}": {
                                "type": "array",
                                "description": "Array of item details.",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            f"{Item.NAME}",
                            f"{Item.QAUNTITY}",
                            f"{Item.DETAILS}",
                        ],
                    },
                },
                f"{Order.HUMAN_RESPONSE}": {
                    "type": "string",
                    "description": "A CREATIVE, WITTY GREETING TO THE CUSTOMER",
                },
            },
            "required": [f"{Order.MENU_ITEMS}", f"{Order.HUMAN_RESPONSE}"],
        },
    },
    "clarify_user_order": {
        "name": "clarify_user_order",
        "description": (
             "Processes a clarification to a users order for a given menu and in order to return both a"
            f"human readable response, an itemized transaction summary, and whether the order is complete."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                f"{Order.MENU_ITEMS}": {
                    "type": "array",
                    "description": "A structured mapping to the corrected menu items the user has asked for.",
                    "items": {
                        "type": "object",
                        "properties": {
                            f"{Item.NAME}": {
                                "type": "string",
                                "description": "key from ONLY the innermost keys of each menu item mentioned with the greatest specificity item",
                            },
                            f"{Item.QAUNTITY}": {
                                "type": "number",
                                "description": "The quantity of the item.",
                            },
                            f"{Item.DETAILS}": {
                                "type": "array",
                                "description": "Array of item details.",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            f"{Item.NAME}",
                            f"{Item.QAUNTITY}",
                            f"{Item.DETAILS}",
                        ],
                    },
                },
                f"{Order.COMPLETED}": {
                    "type": "boolean",
                    "description": "Whether or not the order has been sufficiently clarified and is ready to be processed.",
                },
                f"{Order.HUMAN_RESPONSE}": {
                    "type": "string",
                    "description": "A CREATIVE, WITTY RESPONSE TO THE CLARIFIED ORDER",
                },
            },
            "required": [
                f"{Order.MENU_ITEMS}",
                f"{Order.HUMAN_RESPONSE}",
                f"{Order.COMPLETED}",
            ],
        },
    },
}
