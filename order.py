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

logger = Logger("order_logger")

class OrderProcessingError(Exception):
    pass


def interact_with_user(msg: str, speak=False, mock=False) -> str:
    print(msg)
    if speak:
        speek(msg)


@dataclass
class Menu:
    restaurant_name: str
    full_detail: dict
    flat_menu_items: dict = field(init=False)

    def __post_init__(self):
        self.flat_menu_items = get_innermost_items(self.full_detail)

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

    def __hash__(self) -> int:
        return hash((self.name, (hash(x for x in self.details) or 0), self.quantity))


@dataclass
class Order:
    HUMAN_RESPONSE = "human_response"
    MENU_ITEMS = "menu_items"
    MENU_ITEM_DETAILS = "menu_item_details"

    menu: Menu
    human_response: str
    menu_items: List[Item]

    unrecognized_items: List[str] = field(default_factory=list)
    processed_order: DefaultDict[str, Tuple[float, int]] = field(
        default_factory=lambda: defaultdict(lambda: (0, 0))
    )
    total_price: float = 0.0

    def __post_init__(self):
        self.menu_items = [Item(**item_args) for item_args in self.menu_items]

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

    @classmethod
    def from_api_reponse(cls, response: str, menu: Menu) -> "Order":
        try:
            order_kwargs = ast.literal_eval(response)
            return Order(menu=menu, **order_kwargs)
        except Exception as e:
            print(e)
            raise OrderProcessingError(
                f"Error processing order {response}, please try again"
            )

    @classmethod
    def get_initial_prompt(cls, user_input: str, menu: Menu):
        high_level_desc = (
            f"I have a customer order from the following menu \n: {menu.full_detail}\n"
            f"The order contains the following items: '{user_input}'. \n"
            f"Translate this into a python dictonary using single quoted keys where the first \n"
            f"key is '{Order.HUMAN_RESPONSE}', the second key is '{Order.MENU_ITEMS}''. \n"
        )

        specific_values_desc = (
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

        return high_level_desc + specific_values_desc + further_intructions

    def get_human_order_summary(self, speech_only=False) -> str:
        hpo = f"Your order is listed below: \n"

        if speech_only:
            for item, (subtotal, count) in self.processed_order.items():
                hpo += f"\n {count} of {item.name}"
        else:
            for item, (subtotal, count) in self.processed_order.items():
                hpo += f"\n * {item.name}: {count} x {self.menu.flat_menu_items[item.name]} = ${subtotal}"

        hpo += f"\n\nFor a total price of: ${self.total_price} \n"

        hpo += f"\nThank you for dining with {self.menu.restaurant_name}!"

        return hpo.strip("/n") if speech_only else hpo

    def to_human_response(self, use_speech=False):
        print(f"{'='*80}\n")
        print(f"{self.human_response} \n")
        print(f"{self.get_human_order_summary()} \n")
        print(f"{'='*80}\n")

        if use_speech:
            speek(self.human_response + self.get_human_order_summary(speech_only=True))


def get_api_response(
    prompt: str,
    engine="text-davinci-003",
    temperature=0.5,
    max_tokens=250,
    menu: Menu = None,
    mock=False,
) -> dict:
    return (
        openai.Completion.create(
            engine=engine,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not mock
        else get_mock_response(menu.restaurant_name)
    )


def process_order(user_input: str, menu: Menu, speak=False, mock=False) -> Order:
    initial_prompt = Order.get_initial_prompt(user_input, menu)
    logger.debug(f"\nInitial prompt: \n {initial_prompt}\n")

    response = get_api_response(initial_prompt, mock=mock)
    logger.debug(f"API response: \n{response}\n")

    max_retries = 2
    attempt = 0
    while attempt < max_retries:
        try:
            raw_order = response.choices[0].text.strip("\n").strip()
            logger.debug(f"Raw Order: \n {raw_order} \n Attempt: {attempt} \n")

            order = Order.from_api_reponse(raw_order, menu)
            logger.debug(f"Input Order: \n {order} \n")

        except Exception as e:
            logger.error(f"Error processing order: {e}")

            attempt += 1
            error_message = (
                f"\n Processing of the returned reponse failed with the following error: {e} "
                + f"\n Please try again. \n"
            )
            retry_prompt = f"{initial_prompt} \n {error_message}"

            response = get_api_response(retry_prompt)

            interact_with_user(f"Processing your order, please wait... \n", speak)
        else:
            # successful parsing
            break
    else:
        interact_with_user(
            f"Sorry, we were unable to process your order. Please contact an employee for help.",
            speak,
        )
        raise OrderProcessingError(f"Unable to process order after {max_retries} attempt")

    return order


def main():
    parser = argparse.ArgumentParser(description="Process a food order.")
    parser.add_argument(
        "--order_input", type=str, default=None, help="The customer order"
    )
    parser.add_argument(
        "--menu_name",
        type=str,
        default="archies_deli",
        help="The menu file to use (default: archies_deli)",
    )
    parser.add_argument(
        "--mock",
        type=bool,
        default=False,
        help="Whether to use the mock API response (default: False)",
    )
    parser.add_argument(
        "--speak",
        type=bool,
        default=False,
        help="Whether or not activate speech responses (default: False)",
    )
    parser.add_argument(
        "--log_level",
        type=int,
        default=1,
        help="The logging level (default: 1/DEBUG)",
    )

    args = parser.parse_args()

    logger.set_level(args.log_level)

    menu = Menu.from_file(args.menu_name)

    logger.debug(f"Menu: {menu} {menu.full_detail} \n")

    interact_with_user(
        f"Hi, welcome to {menu.restaurant_name}. What can I get for you today? \n",
        args.speak,
    )

    user_order = args.order_input if args.order_input else listen(logger)

    interact_with_user(
        f"Great choice! one moment please... \n",
        args.speak,
    )

    order = process_order(user_order, menu, speak=args.speak, mock=args.mock)

    logger.debug(f"Processed Order: {order}")

    order.to_human_response(use_speech=args.speak)


if __name__ == "__main__":
    main()
