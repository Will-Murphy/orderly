from __future__ import annotations

import datetime
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field, asdict
import random
from typing import DefaultDict, Dict, List, Tuple
from completion_api import ApiModels
from logger import Logger
from halo import Halo


import openai
from speech import listen, speak
from tests.mock_reponse import get_mock_response
from utils import get_generic_order_waiting_phrases, get_innermost_items

openai.api_key = os.getenv("OPENAI_API_KEY")

TEST_MENU_DIR = "tests/test_menus"


logger = Logger("order_logger")

random.seed(datetime.datetime.now())


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

    @classmethod
    def get_schema(
        cls,
        name_desc: str = "key from ONLY the innermost keys of each menu item mentioned with the greatest specificity item",
    ):
        return {
            "type": "object",
            "properties": {
                f"{Item.NAME}": {
                    "type": "string",
                    "description": name_desc,
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
        }


def human_item_list(items: List[Item]):
    last = ""
    if len(items) > 3:
        last = f" and {items.pop().name}"
    elif len(items) == 2:
        return f"{items[0].name} and {items[1].name}"

    return ", ".join([i.name for i in items]) + last


@dataclass
class Order(AbstractOrderData):
    HUMAN_RESPONSE = "human_response"
    MENU_ITEMS = "menu_items"
    UNRECOGNIZED_ITEMS = "unrecognized_items"
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
        self.initialize()

    def initialize(self):
        def to_item(dict_items: List[Dict]):
            return [Item(**item_args) for item_args in dict_items]

        self.menu_items = to_item(self.menu_items)
        self.unrecognized_items = to_item(self.unrecognized_items)

        for item in self.menu_items:
            if item.name not in self.menu.flat_menu_items.keys():
                self.unrecognized_items.append(item)
                logger.debug(f"Unrecognized item: {item}")
                continue
            else:
                unit_price = self.menu.flat_menu_items[item.name]

                subtotal = unit_price * item.quantity

                item_subtotal = self.processed_order[item][0] + subtotal
                item_count = self.processed_order[item][1] + item.quantity

                self.processed_order[item] = (item_subtotal, item_count)

                self.total_price += subtotal

    def add_clarified_order(self, c_order: "Order"):
        self.processed_order = {**self.processed_order, **c_order.processed_order}

        self.unrecognized_items = list(c_order.unrecognized_items)
        self.human_response = c_order.human_response

        self.total_price += c_order.total_price
        self.completed = c_order.completed

    def is_complete(self) -> bool:
        return self.completed

    @classmethod
    def from_api_reponse(cls, response, menu: Menu) -> "Order":
        reply_content = response.choices[0].message
        string_order_kwargs = reply_content.to_dict()["function_call"]["arguments"]
        order_kwargs = json.loads(string_order_kwargs)
        return Order(menu=menu, **order_kwargs)

    def get_human_order_summary(self, speech_only=False) -> str:
        hpo = f"Your order is listed below: \n"

        if speech_only:
            for item, (subtotal, count) in self.processed_order.items():
                hpo += f"\n {count} of {item.name}"
        else:
            for item, (subtotal, count) in self.processed_order.items():
                hpo += f"\n * {item.name}: {count} x {self.menu.flat_menu_items[item.name]} = ${subtotal}"

        hpo += f"\n\nFor a total price of: ${self.total_price} \n"

        return hpo.strip("/n") if speech_only else f"\n\n{'='*80}\n" + hpo + f"{'='*80}\n\n"


ORDER_FUNCTIONS = {
    "process_user_order": {
        "name": "process_user_order",
        "description": (
            f"Processes a users order for a given menu in order to return both a "
            f"human readable response and a itemized transaction summary. Recognized and "
            f"unrecognized items must be provided as separate lists. If the order is not "
            f"yet complete, the user will be prompted to clarify their order."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                f"{Order.MENU_ITEMS}": {
                    "type": "array",
                    "description": "A structured mapping to the exact menu items the user has asked for.",
                    "items": {**Item.get_schema()},
                },
                f"{Order.UNRECOGNIZED_ITEMS}": {
                    "type": "array",
                    "description": "A structured mapping of items not directly mentioned in the menu AFTER clarification.",
                    "items": {
                        **Item.get_schema(
                            name_desc="key user mentioned that was not found in the menu."
                        )
                    },
                },
                f"{Order.COMPLETED}": {
                    "type": "boolean",
                    "description": "Whether or not the order has been sufficiently clarified and is ready to be finalized.",
                },
                f"{Order.HUMAN_RESPONSE}": {
                    "type": "string",
                    "description": "A CREATIVE, WITTY GREETING TO THE CUSTOMER",
                },
            },
            "required": [
                f"{Order.MENU_ITEMS}",
                f"{Order.HUMAN_RESPONSE}",
                f"{Order.COMPLETED}",
            ],
        },
    },
    "clarify_user_order": {
        "name": "clarify_user_order",
        "description": (
            f"Processes a clarification to a users order for a given menu and in order to return both a "
            f"human readable response, an itemized transaction summary, and whether the order is complete."
            f"Clarified and unrecognized items must be provided as separate lists, only items from the users "
            f"recent clarification should be added the list of unrecognized items, not those being clarified."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                f"{Order.MENU_ITEMS}": {
                    "type": "array",
                    "description": "A structured mapping to the corrected menu items the user has asked for.",
                    "items": {**Item.get_schema()},
                },
                f"{Order.UNRECOGNIZED_ITEMS}": {
                    "type": "array",
                    "description": (
                        f"A structure of items from the users current input that were not clarified. If the users "
                        f"current input is clear then this should be empty."
                    ),
                    "items": {
                        **Item.get_schema(
                            name_desc="key user mentioned that was not found in the menu."
                        )
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


@dataclass
class SalesAgent:
    menu: Menu
    speak: bool = True
    api_model: str = ApiModels.GPT4.value
    messages: List[Dict] = field(default_factory=list)

    @Halo(spinner="dots", color="green", text="Thinking...")
    def get_function_completion_response(
        self, prompt: str, fn_name, with_message_history=False
    ):
        default_messages = [
            self.get_system_message(),
            {"role": "user", "content": prompt},
        ]
        if with_message_history:
            default_messages.append(self.messages)

        completion = openai.ChatCompletion.create(
            model=self.api_model,
            messages=[
                self.get_system_message(),
                {"role": "user", "content": prompt},
            ],
            functions=[ORDER_FUNCTIONS[fn_name]],
            function_call={"name": fn_name},
        )
        return completion

    def get_system_message(self):
        return {
            "role": "system",
            "content": (
                f"You are a 'smart' server for {self.menu.restaurant_name} "
                f"interacting with a customer and mapping their order directly"
                f"to the following menu items while being friendly and helpful:\n\n"
                f"{self.menu.full_detail}\n\n"
            ),
        }
        
    def add_user_message(self, msg):
        self.messages.append({"role": "user", "content": msg})

    def add_agent_message(self, msg):
        self.messages.append({"role": "assistant", "content": msg})

    def get_initial_prompt(self, user_input: str) -> str:
        prompt = f"Here is what the customer has asked for in their own words: \n '{user_input}'. \n"

        return prompt

    def get_clarification_prompt(self, user_input: str, order: Order) -> str:
        prompt = (
            f"Some user order items were not understood correctly "
            f"The items that were not previously recognized from the above menu are: "
            f"\n {human_item_list(order.unrecognized_items)}. \n"
            f"The user has now told use that instead they mean the following: "
            f"\n '{user_input}'\n"
        )

        return prompt

    def process_order(self, mock=False) -> Order:
        order = self._intialize_order()

        if not order.is_complete():
            order = self._clarify_order(order)

        self.communicate(
            order.human_response,
            display_summary=order.get_human_order_summary(),
            speech_summary=order.get_human_order_summary(speech_only=True)
        )

        return order

    def _intialize_order(self) -> Order:
        initial_input = self.communicate(
            f"Hi, welcome to {self.menu.restaurant_name}. What can I get for you today? \n",
            get_response=True,
        )

        initial_prompt = self.get_initial_prompt(initial_input)
        logger.debug(f"\nInitial prompt completion: \n {initial_prompt}\n")

        self.waiting_for_api_response()

        response = self.get_function_completion_response(
            initial_prompt, "process_user_order"
        )
        logger.debug(f"API response: \n{response}\n")

        order = Order.from_api_reponse(response, self.menu)
        logger.debug(f"Input Order: \n {order} \n")

        return order

    def _clarify_order(self, order: Order) -> Order:
        while not order.is_complete():
            if not order.menu_items:
                retry_input = self.communicate(
                    order.human_response,
                    get_response=True,
                )
                order = Order.from_api_reponse(retry_input, self.menu)
            else:
                user_clar_input = self.communicate(
                    order.human_response, get_response=True, display_summary=order.get_human_order_summary()
                )
                clarficiation_prompt = self.get_clarification_prompt(user_clar_input, order)

                self.waiting_for_api_response()

                logger.debug(f"\n Clarified prompt: \n {clarficiation_prompt}\n")
                response = self.get_function_completion_response(
                    clarficiation_prompt,
                    "clarify_user_order",
                    with_message_history=True,
                )
                logger.debug(f"API response: \n{response}\n")

                logger.debug(f"Raw Clarfied Order: \n {response} \n")
                clarification_order = Order.from_api_reponse(response, self.menu)
                logger.debug(f"Clarified Order: \n {clarification_order} \n")

                order.add_clarified_order(clarification_order)
                logger.debug(f"Input Clarfied Order: \n {order} \n")

        return order

    def get_display_summary(self, order: Order):
        return f"{'='*80}\n" + f"{order.get_human_order_summary()} \n" + f"{'='*80}\n"

    def waiting_for_api_response(self):
        self.communicate(f"\n {random.choice(get_generic_order_waiting_phrases())} \n")

    @Halo(spinner="dots", color="red")
    def communicate(
        self,
        msg: str,
        get_response=False,
        display_summary: str = "",
        speech_summary: str = "",
    ) -> str | None:

        def listen_for() -> str:
            err_msg = "Sorry, I did not get that. Can you please repeat it?"
            if self.speak:
                response = listen(logger)
                while not response:
                    print(err_msg + "\n\n")
                    speak(err_msg)
                    response = listen(logger)

            else:
                while True:
                    response = input("waiting for response... \n\n")
                    if response:  # if the user entered something
                        break  # exit the loop
                    else:
                        input(err_msg)

            return response

        print(msg + display_summary + "\n\n")
        speak(msg + speech_summary)
        
        
        self.add_agent_message(msg)
        if get_response:
            user_response = listen_for()
            self.add_user_message(user_response)
            return user_response
