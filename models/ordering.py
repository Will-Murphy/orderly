from __future__ import annotations

import asyncio
import datetime
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import DefaultDict, Dict, List, Tuple

from logger import Logger
from models.base import (
    DEFAULT_MAX_API_RETRIES,
    AbstractAgent,
    AbstractOrderData,
    ApiResponseException,
    NoInputException,
)
from utils.utils import get_innermost_items
from utils.ux import get_generic_order_waiting_phrases

TEST_MENU_DIR = "tests/test_menus"

logger = Logger("order_logger")

random.seed(datetime.datetime.now())


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
    details: List[str] = field(default_factory=list)
    quantity: int = field(default=0)

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
    IS_COMPLETED = "is_completed"
    IS_FINALIZED = "is_finalized"

    menu: Menu
    human_response: str
    menu_items: List[Item]

    unrecognized_items: List[str] = field(default_factory=list)
    processed_order: DefaultDict[Item, Tuple[float, int]] = field(
        default_factory=lambda: defaultdict(lambda: (0, 0))
    )
    total_price: float = 0.0
    is_completed: str = False
    is_finalized: str = False

    def as_dict(self):
        return {
            "menu": self.menu.as_dict(),
            "menu_items": [asdict(m) for m in self.menu_items],
            "human_response": self.human_response,
            "processed_order": {k.name: v for k, v in self.processed_order.items()},
            "total_price": self.total_price,
            "unrecognized_items": [asdict(m) for m in self.unrecognized_items],
            "total_price": self.total_price,
            "is_completed": self.is_completed,
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

    def is_complete(self) -> bool:
        return self.is_completed

    def is_final(self) -> bool:
        return self.is_finalized

    @classmethod
    def from_api_response(cls, response, menu: Menu) -> "Order":
        return super().from_api_response(response, menu=menu)

    def get_human_order_summary(self, speech_only=False) -> str:
        hpo = f"Your order is listed below: \n"

        for item, (subtotal, count) in self.processed_order.items():
            if speech_only:
                hpo += f"\n {count} of {item.name}"
            else:
                hpo += f"\n * {item.name}: {count} x {self.menu.flat_menu_items[item.name]} = ${subtotal}"

            for detail in item.details:
                hpo += f"\n    - {detail}"

        hpo += f"\n\nFor a total price of: ${self.total_price} \n"

        return (
            hpo.strip("/n")
            if speech_only
            else f"\n\n{'='*80}\n" + hpo + f"{'='*80}\n\n"
        )

    @classmethod
    def get_schema(
        cls,
        menu_items_desc="A structured mapping to all the unique menu items the user has asked for during their session.",
        unrec_items_desc="A structured mapping of items not directly mentioned in the menu AFTER clarification.",
        single_unrec_name_desc="key user mentioned that was not found in the menu.",
        is_completed_desc="Whether or not the order has been sufficiently clarified",
        is_finalized_desc="Whether or not the user has given definitive, final confirmation of their order.",
        human_res_desc="A CREATIVE, WITTY GREETING TO THE CUSTOMER",
    ) -> dict:
        return {
            "type": "object",
            "properties": {
                f"{Order.MENU_ITEMS}": {
                    "type": "array",
                    "description": menu_items_desc,
                    "items": {**Item.get_schema()},
                },
                f"{Order.UNRECOGNIZED_ITEMS}": {
                    "type": "array",
                    "description": unrec_items_desc,
                    "items": {**Item.get_schema(name_desc=single_unrec_name_desc)},
                },
                f"{Order.IS_FINALIZED}": {
                    "type": "boolean",
                    "description": is_finalized_desc,
                },
                f"{Order.IS_COMPLETED}": {
                    "type": "boolean",
                    "description": is_completed_desc,
                },
                f"{Order.HUMAN_RESPONSE}": {
                    "type": "string",
                    "description": human_res_desc,
                    "minLength": 10,
                },
            },
            "required": [
                f"{Order.MENU_ITEMS}",
                f"{Order.HUMAN_RESPONSE}",
                f"{Order.IS_COMPLETED}",
                f"{Order.IS_FINALIZED}",
            ],
        }


ORDER_FUNCTIONS = {
    "process_user_order": {
        "name": "process_user_order",
        "description": (
            f"Processes a users order for a given menu in order to return both a "
            f"human readable response and a itemized transaction summary. Recognized and "
            f"unrecognized items must be provided as separate lists. If the order is not "
            f"yet complete due to ambiguity, the user will be prompted to clarify their order."
            f"If the order is complete, the user will be prompted to confirm their order."
        ),
        "parameters": {**Order.get_schema()},
    },
    "clarify_user_order": {
        "name": "clarify_user_order",
        "description": (
            f"Processes a clarification to a users order for a given menu and in order to return both a "
            f"human readable response, an itemized transaction summary, and whether the order is complete."
            f"Clarified and unrecognized items must be provided as separate lists, only items from the users "
            f"recent clarification should be added the list of unrecognized items, not those being clarified."
            f"Once an order has been sufficiently clarified, the user will be prompted to confirm their order."
        ),
        "parameters": {
            **Order.get_schema(
                unrec_items_desc=(
                    f"A structure of items from the users current input that were not clarified. If the users "
                    f"current input is clear then this should be empty."
                ),
                single_unrec_name_desc="key user mentioned that was not found in the menu.",
                is_completed_desc="Whether or not the order has been sufficiently clarified and is ready to be processed.",
                human_res_desc="A CREATIVE, WITTY GREETING TO THE CUSTOMER that matches the is_completed status of the order.",
            )
        },
    },
    "finalize_user_order": {
        "name": "finalize_user_order",
        "description": (
            f"Processes a final user users order for a given menu and in order to complete their transaction."
            f"Recieves a human readable response, an itemized transaction summary, and whether the order is complete, "
            f"and whether the user has confirmed that their order is finalized. Note: the human response should match "
            f"the finalization status of the order."
        ),
        "parameters": {
            **Order.get_schema(
                unrec_items_desc=(
                    f"Any items that have not are not clear during finalization"
                ),
                single_unrec_name_desc="key user mentioned that was not found in the menu.",
                is_completed_desc="Whether or not the order has been unambigously is_finalized and is ready to be processed.",
                human_res_desc="A CREATIVE, WITTY GREETING TO THE CUSTOMER that matches the is_finalized status of the order.",
            )
        },
    },
}

DEFAULT_PERSONALITY_MODIFIER = "friendly and helpful"


@dataclass
class SalesAgent(AbstractAgent):
    menu: Menu
    speech_input: bool = True
    personality_modifier: str = DEFAULT_PERSONALITY_MODIFIER
    max_error_retries: int = DEFAULT_MAX_API_RETRIES

    @property
    def functions(self) -> Dict[str, Dict]:
        return ORDER_FUNCTIONS

    @property
    def logger(self):
        return logger

    def get_system_message(self):
        return {
            "role": "system",
            "content": (
                f"You are a 'smart' server for {self.menu.restaurant_name} "
                f"interacting with a customer and mapping their order directly"
                f"to the following menu items in an attempt to finalize their order"
                f"while being {self.personality_modifier}:\n\n"
                f"{self.menu.full_detail}\n\n"
            ),
        }

    def get_initial_prompt(self, user_input: str) -> str:
        prompt = f"Here is what the customer has asked for in their own words: \n '{user_input}'. \n"

        return prompt

    def get_finalization_prompt(self, user_input: str) -> str:
        prompt = f"We think the user has finalized their order as a final response they have said: \n '{user_input}'. \n"

        return prompt

    def get_clarification_prompt(self, user_input: str, order: Order) -> str:
        prompt = (
            f"Some items were not understood correctly or the users order was ambiguous."
            f"The items that were not previously recognized from the above menu are: "
            f"\n {human_item_list(order.unrecognized_items)}. \n"
            f"The user has now told use that instead they mean the following: "
            f"\n '{user_input}'\n"
        )

        return prompt

    def process_order(self) -> Order:
        try:
            asyncio.run(self.process_order_async())
        except NoInputException as e:
            logger.debug(f"No input error: \n{e}\n")
            self.communicate(
                "Sorry, it seems I am unable to hear you or that you've stepped away."
                "Thank you for stopping by!"
            )
            return

    async def process_order_async(self) -> Order:
        await self.adjust_for_ambient_noise_task()

        initial_input = self.communicate(
            f"Hi, welcome to {self.menu.restaurant_name}. What can I get for you today? \n",
            get_response=True,
        )
        order = await self._initialize_order(initial_input)

        api_errors = 0
        while not (order.is_complete() and order.is_final()):
            try:
                if not order.is_complete():
                    order = await self._clarify_order(order)

                if order.is_complete() and not order.is_final():
                    order = await self._finalize_order(order)

            except ApiResponseException as e:
                logger.debug(f"API response error: \n{e}\n")
                order = await self._reinitialize_after_error()
                api_errors += 1
                continue

            if api_errors >= self.max_error_retries:
                logger.debug(f"Max API errors exceeded: {api_errors}\n")
                self.communicate(
                    "Sorry, there seems to be an issue with our system or the internet connection. "
                    "Please try again later."
                )
                return

        self.communicate(
            order.human_response,
            display_summary=order.get_human_order_summary(),
            speech_summary=order.get_human_order_summary(speech_only=True),
        )
        logger.debug(f"Customers Final Order: \n {order} \n")
        logger.debug(f"Total API Usage Data \n {self.usage_data} \n")

        return order

    async def _initialize_order(self, user_input: str = "") -> Order:
        initial_prompt = self.get_initial_prompt(user_input) if user_input else ""
        logger.debug(f"\nInitialize order prompt: \n {initial_prompt}\n")

        response = await self.get_func_completion_res_with_waiting(
            initial_prompt, "process_user_order", with_message_history=True
        )
        logger.debug(f"API response: \n{response}\n")

        order = Order.from_api_response(response, self.menu)
        logger.debug(f"Input Order: \n {order} \n")

        return order

    async def _reinitialize_after_error(self) -> Order:
        self.communicate(
            "Sorry, something went wrong processing your request. "
            + random.choice(get_generic_order_waiting_phrases())
        )
        self.add_system_message(
            "There was an issue processing the order up to this point, it must be retried."
        )
        order = await self._initialize_order()

        return order

    async def _clarify_order(self, order: Order) -> Order:
        if not order.menu_items:
            retry_input = self.communicate(
                order.human_response,
                get_response=True,
            )
            order = await self._initialize_order(retry_input)
        else:
            user_clar_input = self.communicate(
                order.human_response,
                get_response=True,
                display_summary=order.get_human_order_summary(),
            )
            clarficiation_prompt = self.get_clarification_prompt(user_clar_input, order)

            logger.debug(f"\n Clarified prompt: \n {clarficiation_prompt}\n")
            response = await self.get_func_completion_res_with_waiting(
                clarficiation_prompt, "clarify_user_order", with_message_history=True
            )
            logger.debug(f"API response: \n{response}\n")

            logger.debug(f"Raw Clarfied Order: \n {response} \n")
            order = Order.from_api_response(response, self.menu)
            logger.debug(f"Clarified Order: \n {order} \n")

            logger.debug(f"Input Clarfied Order: \n {order} \n")

        return order

    async def _finalize_order(self, order: Order) -> Order:
        final_response = self.communicate(
            order.human_response,
            display_summary=order.get_human_order_summary(),
            speech_summary=order.get_human_order_summary(speech_only=True),
            get_response=True,
        )

        finalization_prompt = self.get_finalization_prompt(final_response)

        response = await self.get_func_completion_res_with_waiting(
            finalization_prompt, "finalize_user_order", with_message_history=True
        )
        logger.debug(f"Finalization API response: \n{response}\n")

        finalized_order = Order.from_api_response(response, self.menu)
        logger.debug(f"Finalized Order from response: \n {finalized_order} \n")

        return finalized_order

    def get_display_summary(self, order: Order):
        return f"{'='*80}\n" + f"{order.get_human_order_summary()} \n" + f"{'='*80}\n"
