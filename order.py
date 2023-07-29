import argparse
import ast
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import DefaultDict, Dict, List, Tuple
from logger import Logger

import openai
from order_models import ORDER_FUNCTIONS, Menu, Order, human_item_list
from speech import listen, speek
from tests.mock_reponse import get_mock_response
from utils import get_innermost_items

openai.api_key = os.getenv("OPENAI_API_KEY")

TEST_MENU_DIR = "tests/test_menus"

USE_FUNCTION_CALLS = True

logger = Logger("order_logger")


class OrderProcessingError(Exception):
    pass


def communicate(msg: str, speak=False, with_response=False) -> str:
    def say(x):
        print(x + "\n\n")
        speek(x)

    def listen_for() -> str:
        err_msg = "Sorry, I did not get that. Can you please repeat it?"
        if speak:
            response = listen(logger)
            while not response:
                say(err_msg)
                response = listen(logger)

        else:
            while True:
                response = input("waiting for response... \n\n")
                if response:  # if the user entered something
                    break  # exit the loop
                else:
                    input(err_msg)

        return response

    say(msg)
    if with_response:
        return listen_for()

def get_function_completion_response(prompt: str, fn_name):
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0613",
        messages=[{"role": "user", "content": prompt}],
        functions=[ORDER_FUNCTIONS[fn_name]],
        function_call={"name": fn_name},
    )
    return completion


def process_order(
    user_input: str,
    menu: Menu,
    speak=False,
    mock=False,
    using_func_calls=USE_FUNCTION_CALLS,
) -> Order:
    initial_prompt = Order.get_initial_prompt(
        user_input, menu, using_func_calls=using_func_calls
    )
    logger.debug(f"\nInitial prompt: \n {initial_prompt}\n")

    response = get_function_completion_response(initial_prompt, "get_initial_user_order")
    logger.debug(f"API response: \n{response}\n")

    max_retries = 2
    attempt = 0
    while attempt < max_retries:
        try:
            logger.debug(f"Raw Order: \n {response} \n Attempt: {attempt} \n")

            order = Order.from_api_reponse(response, menu)
            logger.debug(f"Input Order: \n {order} \n")

        except Exception as e:
            # print full error message
            logger.error(f"Error processing order: {str(e)}")

            attempt += 1
            error_message = (
                f"\n Processing of the returned reponse failed with the following error: {e} "
                + f"\n Please try again. \n"
            )
            retry_prompt = f"{initial_prompt} \n {error_message}"

            response = get_function_completion_response(
                retry_prompt, "get_initial_user_order"
            )

            communicate(f"Processing your order, please wait... \n", speak)
        else:
            # successful parsing
            break
    else:
        communicate(
            f"Sorry, we were unable to process your order. Please contact an employee for help.",
            speak,
        )
        raise OrderProcessingError(
            f"Unable to process order after {max_retries} attempt"
        )

    completion_attempts = 0
    while not order.is_complete():
        if order.unrecognized_items:
            response =  communicate(
                f"Sorry, we don't have {human_item_list(order.unrecognized_items)}. "
                f"Can you please be more specific?",
                speak,
                with_response=True
            )
            clarficiation_prompt = order.get_clarification_prompt(
                user_input, initial_prompt
            )
            
            logger.debug(f"\n Clarified prompt: \n {initial_prompt}\n")
            response = get_function_completion_response(clarficiation_prompt, "get_clarified_order")
            logger.debug(f"API response: \n{response}\n")
            
            logger.debug(f"Raw Clarfied Order: \n {response} \n")
            clarification_order = Order.from_api_reponse(response, menu)
            logger.debug(f"Input Clarfied Order: \n {order} \n")
            
            order.add_clarified_order(clarification_order)
            completion_attempts += 1
            
        if not order.menu_items:
            communicate(
                f"Sorry, I didn't understand your order. Please try again.",
                speak,
            )
            return None
            
        else:
            if completion_attempts > 0:
                communicate(f"\nThank you for bearing with me! Enjoy your meal!", speak)
            else:
                communicate(
                    f"\nThank you for dining with {order.menu.restaurant_name}!", speak
                )
                


    return order


def main():
    parser = argparse.ArgumentParser(description="Process a food order.")
    parser.add_argument(
        "--order",
        type=str,
        default="",
        help="The order to process (default: '')",
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
    
    if args.order:
        user_order = args.order
    else:
        user_order = communicate(
            f"Hi, welcome to {menu.restaurant_name}. What can I get for you today? \n",
            args.speak,
            with_response=True,
        )

    communicate(
        f"\n  Great choice! one moment please... \n",
        args.speak,
    )

    order = process_order(user_order, menu, speak=args.speak, mock=args.mock)

    logger.debug(f"Processed Order: {order}")

    order.to_human_response()


if __name__ == "__main__":
    main()
