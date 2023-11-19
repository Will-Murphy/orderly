import json

str = '{\n  "menu_items": [\n    {\n      "name": "Buffalo Chicken",\n      "category": "Pizza",\n      "details": [\n        {\n          "name": "Sm",\n          "price": 12.50\n        },\n        {\n          "name": "Lg",\n          "price": 19.50\n        },\n        {\n          "name": "Fam",\n          "price": 40.00\n        }\n      ]\n    },\n    {\n      "name": "BBQ Chicken",\n      "category": "Pizza",\n      "details": [\n        {\n          "name": "Sm",\n          "price": 12.50\n        },\n        {\n          "name": "Lg",\n          "price": 19.50\n        },\n        {\n          "name": "Fam",\n          "price": 40.00\n        }\n      ]\n    },\n    {\n      "name": "Chicken Bacon Ranch",\n      "category": "Pizza",\n      "details": [\n        {\n          "name": "Sm",\n          "price": 13.50\n        },\n        {\n          "name": "Lg",\n          "price": 20.50\n        },\n        {\n          "name": "Fam",\n          "price": 42.25\n        }\n      ]\n    },\n    {\n      "name": "Chicken Broccoli Alfredo",\n      "category": "Pizza",\n      "details": [\n        {\n          "name": "Sm",\n          "price": 13.50\n        },\n        {\n          "name": "Lg",\n          "price": 20.50\n        },\n        {\n          "name": "Fam",\n          "price": 42.25\n        }\n      ]\n    },\n    {\n      "name": "Pesto Chicken",\n      "category": "Pizza",\n      "details": [\n        {\n          "name": "Sm",\n          "price": 13.50\n        },\n        {\n          "name": "Lg",\n          "price": 20.50\n        }\n      ]\n    }\n  ]\n}'


def remove_chars(s):
    return s.replace("\n", "").replace(" ", "")

print(json.dumps(remove_chars(str.strip()), indent=4))


