import json
import sys

from models.ordering import Menu, SalesAgent


def pprint_assistant(agent=None):
    if len(sys.argv) != 2:
        print("Usage: python script.py <menu_name>")
    else:
        menu_name = sys.argv[1]
        menu = Menu.from_file(menu_name)

        if agent is None:
            agent = SalesAgent(menu, use_speech_input=False)

        print(
            "\n\system message:\n\n", json.dumps(agent.get_system_message(), indent=4)
        )
        print("\n\nfunctions:\n\n", json.dumps(agent.functions, indent=4))
        print("\n\message_history:\n\n", json.dumps(agent.message_history, indent=4))


if __name__ == "__main__":
    pprint_assistant()
