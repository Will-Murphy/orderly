import argparse
import ast
import json
import os
from logger import Logger

import openai
from order_models import Menu, SalesAgent

openai.api_key = os.getenv("OPENAI_API_KEY")

TEST_MENU_DIR = "tests/test_menus"

logger = Logger("order_logger")


def main():
    parser = argparse.ArgumentParser(description="Process a food order.")
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

    logger.info(f"Menu: {json.dumps(menu.full_detail, indent=4)} \n")

    sales_agent = SalesAgent(menu, speak=args.speak)

    order = sales_agent.process_order(mock=args.mock)

    logger.debug(f"Processed Order: {order}")


if __name__ == "__main__":
    main()
