import json
import sys

from models.ordering import Menu


def pprint_menu():
    if len(sys.argv) != 2:
        print("Usage: python script.py <menu_name>")
    else:
        menu_name = sys.argv[1]
        menu = Menu.from_file(menu_name)
        print(json.dumps(menu.full_detail, indent=4))


if __name__ == "__main__":
    pprint_menu()
