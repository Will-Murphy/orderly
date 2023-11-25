import argparse
import json

from models.api import ApiVoices
from models.base import DEFAULT_API_VOICE
from models.ordering import DEFAULT_PERSONALITY_MODIFIER, Menu, SalesAgent, logger

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
        "--speech_input",
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
    parser.add_argument(
        "--personality",
        type=str,
        default=DEFAULT_PERSONALITY_MODIFIER,
        help="Personality modifier for agent. Usage: <agent instructions> while being <personality>",
    )
    parser.add_argument(
        "--voice",
        choices=[v.value for v in ApiVoices],
        default=DEFAULT_API_VOICE,
        help="Voice selection for agent when interation with users",
    )

    args = parser.parse_args()

    logger.set_level(args.log_level)

    menu = Menu.from_file(args.menu_name)
    logger.info(f"Menu: {json.dumps(menu.full_detail, indent=4)} \n")

    sales_agent = SalesAgent(
        menu,
        speech_input=args.speech_input,
        personality_modifier=args.personality,
        voice_selection=args.voice,
    )

    sales_agent.process_order()


if __name__ == "__main__":
    main()
