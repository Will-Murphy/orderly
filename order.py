import argparse
import ast
import json
import os

import openai
from order_models import Menu, SalesAgent, logger



TEST_MENU_DIR = "tests/test_menus"


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

    sales_agent.process_order()


if __name__ == "__main__":
    main()
