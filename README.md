# Orderly 

AI enabled, speech-based PoS system desinged to automate entire customer ordering workflow and menu ingestion. 
Accomplished using the GPT-4 API, in particular function calls, as well as text to speech capabilities 
in order to understand orders, inquiries, and entire restaurant menus and interact with customers in a human-like way.

# Requirements
- Python 3.10
- Pip
- Pipenv

## Setup

In .env, place your openAI open key

```
OPENAI_API_KEY = <your_key>
```

Provided python 3.10 and a compatible version of pip / pipenv, it should work out of the box. From the
root directory run:

```
pipenv install
```

## Usage

To begin ordering, go into the pipenv shell and run order.py

```
pipenv shell

python order.py --menu "grandslam_deli" --log_level 2
```

### Arg details
- --menu_name: Name of the menu file to use (Default: "archies_deli")
- --mock: Use mock API response for testing (Default: False)
- --speak: Enable or disable speech responses (Default: False)
- --log_level: Logging level (Default: 1/DEBUG)


## Example 

Heres a simple example interaction. The tool should recognize a valid order and intelligently prompt the 
user until their order is complete and valid, showing the order items, sub-total and total cost at each 
step along the way

<img width="1280" alt="image" src="https://github.com/Will-Murphy/orderly/assets/43630470/8b079316-a39c-4a99-b351-9236b2f1793c">
