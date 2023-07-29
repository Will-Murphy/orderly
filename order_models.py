import argparse
import ast
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
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
class Menu:
    restaurant_name: str
    full_detail: dict
    flat_menu_items: dict = field(init=False)

    def __post_init__(self):
        self.flat_menu_items = {k.title(): v for k,v in get_innermost_items(self.full_detail).items()}

    @classmethod
    def from_file(cls, menu_name: str) -> dict:
        filename = f"{TEST_MENU_DIR}/{menu_name}.json"
        with open(filename, "r") as f:
            menu = json.load(f)
        return Menu(full_detail=menu, restaurant_name=menu["restaurant"])
    
@dataclass
class Item:
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
class Order:
    HUMAN_RESPONSE = "human_response"
    MENU_ITEMS = "menu_items"
    MENU_ITEM_DETAILS = "menu_item_details"
    COMPLETED ="completed"

    menu: Menu
    human_response: str
    menu_items: List[Item]

    unrecognized_items: List[str] = field(default_factory=list)
    processed_order: DefaultDict[str, Tuple[float, int]] = field(
        default_factory=lambda: defaultdict(lambda: (0, 0))
    )
    total_price: float = 0.0
    completed: str = False

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
    def get_initial_prompt(
        cls, user_input: str, menu: Menu, using_func_calls=USE_FUNCTION_CALLS
    ):
        prompt = (
            f"I have a customer order from the following menu \n: {menu.full_detail}\n"
            f"The order contains the following items: '{user_input}'. \n"
        )

        if not using_func_calls:
            specific_values_desc = (
                f"Translate this into a python dictonary using single quoted keys where the first \n"
                f"key is '{Order.HUMAN_RESPONSE}', the second key is '{Order.MENU_ITEMS}''. \n"
                f"The following describes the values of these items: \n\n"
                f" - '{Order.HUMAN_RESPONSE}' is a witty and charming response to the customers order, with any single quotes "
                f"   character escaped \n"
                f" - '{Order.MENU_ITEMS}' is a python list of dictionarys containing information aboout each item mentioned. "
                f"   Each of these nested dictionaries has keys '{Item.NAME}', '{Item.QAUNTITY}' and '{Item.DETAILS}' \n"
                f"   which map to the following values: \n"
                f"    - '{Item.NAME}' is an item name that from ONLY the innermost key name of each menu item mentioned with the greatest \n"
                f"    specificity item \n"
                f"    - '{Item.QAUNTITY}' is an integer value of the number of times this specific item was mentioned \n"
                f"    - '{Item.DETAILS}' is list of string values containing any additional details about the menu items \n"
            )

            further_intructions = (
                f"\nDon't include any other text besides the above in your response besides the python dictionary. \n"
                f"\nStore each individual item, even if there are multiple of the same, as unique entries in '{Order.MENU_ITEMS}'\n"
                f"\nAll string dictionary values should be single quoted. \n"
                f"\nAny strings you generate with the single quote character should be character escaped. \n"
            )
            prompt += specific_values_desc + further_intructions

        return prompt
    
    def add_clarified_order(self, c_order: "Order"):
        self.processed_order = {
            **self.processed_order, **c_order.processed_order
        }
        
        self.unrecognized_items = list(c_order.unrecognized_items)
            
        self.total_price += c_order.total_price
        self.completed = c_order.completed
        
        
    def get_clarification_prompt(
        self, user_input: str, initial_prompt: str
    ) -> str:
        prompt = (
            f"Based on the following prompt {self.unrecognized_items} were not recognized. \n: \n\n {initial_prompt} \n\n."
            f"The user has clarified their input with the following: '{user_input}'. \n"
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
    "get_initial_user_order": {
        "name": "get_initial_user_order",
        "description": "Gets a users order from a given menu from their spoken request",
        "parameters": {
            "type": "object",
            "properties": {
                f"{Order.MENU_ITEMS}": {
                    "type": "array",
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
                    "description": "A CREATIVE, WIITY GREETING TO THE CUSTOMER",
                },
            },
            "required": [f"{Order.MENU_ITEMS}", f"{Order.HUMAN_RESPONSE}"],
        },
    },
    "get_clarified_order": {
        "name": "get_clarified_order",
        "description": "Gets a clarified user order for a given menu from their original request and a list of unrecognized items",
        "parameters": {
            "type": "object",
            "properties": {
                f"{Order.MENU_ITEMS}": {
                    "type": "array",
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
                f"{Order.COMPLETED}": {
                    "type": "boolean",
                    "description": "Whether or not the order has been sufficiently clarified and is ready to be processed.",
                }
                },
                f"{Order.HUMAN_RESPONSE}": {
                    "type": "string",
                    "description": "A CREATIVE, WIITY RESPONSE TO THE UPDATED ORDER",
                },
            },
            "required": [f"{Order.MENU_ITEMS}", f"{Order.HUMAN_RESPONSE}", f"{Order.COMPLETED}"],
        },
    },
}


