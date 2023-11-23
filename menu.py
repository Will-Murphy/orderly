import argparse
import json
import os
import time
import traceback
from dataclasses import asdict, dataclass, field
from typing import List

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support import ui
from webdriver_manager.chrome import ChromeDriverManager

from logger import Logger
from models.base import AbstractAgent, AbstractOrderData

CHROME_PATH = (
    "/Users/williammurphy/Downloads/Google Chrome.app/Contents/MacOS/Google Chrome"
)
PAGE_LOAD_WAIT_TIME = 5

logger = Logger("menu_logger")


@dataclass
class ItemDetails(AbstractOrderData):
    NAME = "name"
    DETAIL_PRICE = "detail_price"

    name: str
    detail_price: float = 0.0

    def as_dict(self):
        return asdict(self)

    @classmethod
    def get_schema(cls):
        return {
            "type": "array",
            "description": "Array of priced item details. Should only contain information relevant to the item."
            "Information should not be repeated between the item and items details",
            "items": {
                "type": "object",
                "description": "A priced item detail.",
                "properties": {
                    f"{ItemDetails.NAME}": {"type": "string"},
                    f"{ItemDetails.DETAIL_PRICE}": {"type": "number"},
                },
            },
            "required": [f"{ItemDetails.NAME}", f"{ItemDetails.DETAIL_PRICE}"],
        }


@dataclass
class ScraperItem(AbstractOrderData):
    NAME = "name"
    DETAILS = "details"
    CATEGORY = "category"
    ITEM_PRICE = "item_price"

    name: str
    category: str
    details: List[str]
    item_price: float

    def as_dict(self):
        return {
            f"{ScraperItem.NAME}": self.name,
            f"{ScraperItem.ITEM_PRICE}": self.item_price,
            f"{ScraperItem.CATEGORY}": self.category,
            f"{ScraperItem.DETAILS}": [x.as_dict() for x in self.details],
        }

    def __post_init__(self, *args, **kwargs):
        self.name = self.name.title()
        self.details = [ItemDetails(**x) for x in self.details]

    def __hash__(self) -> int:
        return hash((self.name, (hash(x for x in self.details) or 0), self.quantity))

    @classmethod
    def get_schema(
        cls,
        name_desc: str = "The name of the item.",
    ):
        return {
            "type": "object",
            "description": (
                "A priced item menu item, all fields should be extracted from html"
                "if an item is to be created at all"
            ),
            "properties": {
                f"{ScraperItem.NAME}": {
                    "type": "string",
                    "description": name_desc,
                },
                f"{ScraperItem.ITEM_PRICE}": {
                    "type": ["number", "null"],
                    "description": "The price of the item. Can be null if details included in the price",
                },
                f"{ScraperItem.CATEGORY}": {
                    "type": ["string", "null"],
                    "description": "The category of the item.",
                },
                f"{ScraperItem.DETAILS}": {
                    **ItemDetails.get_schema(),
                },
            },
            "required": [
                f"{ScraperItem.NAME}",
                f"{ScraperItem.ITEM_PRICE}",
                f"{ScraperItem.CATEGORY}",
                f"{ScraperItem.DETAILS}",
            ],
        }


@dataclass
class ScraperMenu(AbstractOrderData):
    RESTAURANT_NAME = "restaurant_name"
    RESTAURANT_ADDRESS = "restaurant_address"
    MENU_ITEMS = "menu_items"

    restaurant_name: str = None
    restaurant_address: str = None
    menu_items: List[ScraperItem] = field(default_factory=list)

    def __post_init__(self, *args, **kwargs):
        self.menu_items = [ScraperItem(**x) for x in self.menu_items]

    def as_dict(self):
        return {
            f"{ScraperMenu.MENU_ITEMS}": [x.as_dict() for x in self.menu_items],
            f"{ScraperMenu.RESTAURANT_NAME}": self.restaurant_name,
            f"{ScraperMenu.RESTAURANT_ADDRESS}": self.restaurant_address,
        }

    @classmethod
    def get_schema(cls):
        return {
            "type": "object",
            "description": (
                "Structured menu with prices and details extracted from html. "
            ),
            "properties": {
                f"{ScraperMenu.MENU_ITEMS}": {
                    "type": "array",
                    "description": (
                        "Array of menu items extracted from html with all fields filled out according the schema."
                        "Items should ONLY be in this list if they can be ordered."
                    ),
                    "items": ScraperItem.get_schema("item name"),
                },
                f"{ScraperMenu.RESTAURANT_NAME}": {
                    "type": ["string", "null"],
                    "description": "The name of the restaurant. Only to be filled out if the restaurant name is detected.",
                },
                f"{ScraperMenu.RESTAURANT_ADDRESS}": {
                    "type": ["string", "null"],
                    "description": "The address of the restaurant. Only to be filled out if the restaurant address is detected.",
                },
            },
            "required": [
                f"{ScraperMenu.MENU_ITEMS}",
            ],
        }

    def extend_menu(self, other_menu: "ScraperMenu"):
        self.restaurant_name = self.restaurant_name or other_menu.restaurant_name
        self.restaurant_address = (
            self.restaurant_address or other_menu.restaurant_address
        )
        self.menu_items.extend(other_menu.menu_items)


SCRAPING_FUNCTIONS = {
    "process_scraped_menu": {
        "name": "process_scraped_menu",
        "description": (
            f"Processes a structured menu scraped from the web and uses it to transact. "
        ),
        "parameters": {
            **ScraperMenu.get_schema(),
        },
    },
}


@dataclass
class ScraperAgent(AbstractAgent):
    scraper_menu: ScraperMenu = field(default_factory=ScraperMenu)

    @property
    def functions(self):
        return SCRAPING_FUNCTIONS

    @property
    def logger(self):
        return logger

    def get_system_message(self):
        return {
            "role": "system",
            "content": (
                "You are a 'smart' menu web scraper. Your job is to take "
                "unstructured html and return structured menu items. "
            ),
        }

    def add_to_menu(self, item: ScraperItem):
        self.scraper_menu.menu_items.append(item)

    def get_scraping_prompt(self, web_page_html: str):
        prompt = f"Here is the html from the web page with the menu items. \n {  web_page_html}"
        return prompt

    def get_retry_prompt(self, web_page_html: str, error: str):
        prompt = (
            f"This chunk of the restaurants html menu web page failed "
            f"to process: \n {  web_page_html}\n "
            f"due to error: \n {error} \n"
            f"please try again."
        )
        return prompt

    def scrape(self, url="https://www.ediningexpress.com/live20/927/1749"):
        logger.debug(f"Scraping menu from {url}...")
        # Setup Chrome options to run headless
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.binary_location = CHROME_PATH

        # Set up WebDriver
        webdriver_service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)

        # Fetch the webpage
        driver.get(url)
        try:
            ui.WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert.accept()
            print("Alert accepted")
        except TimeoutException:
            print("No alert present")

        # Wait until element is loaded
        ui.WebDriverWait(driver, 10).until(
            lambda driver: driver.find_element(by=By.TAG_NAME, value="body")
        )

        # Wait an additional amount of time for JavaScript to execute
        time.sleep(10)

        # Now you can access the final HTML with JavaScript executed
        html = driver.page_source

        logger.debug(f"Menu scraped from {url}...: \n\n {html}")

        print(html)

        driver.quit()

        return html

    def process_scraped_menu(self, text, chunk_size=2000, max=32000) -> ScraperMenu:
        initial_menu = ScraperMenu()
        total = max or len(text)
        i = 0
        while text and i <= total:
            current_chunk = text[:chunk_size]
            text = text[chunk_size:]
            i += chunk_size

            logger.debug(
                f"\n Processing raw menu chunk of len {len(current_chunk)}. {i} of "
                f"total {total}: \n\n {current_chunk}"
            )

            prompt = self.get_scraping_prompt(current_chunk)

            max_tries = 3
            tries = 0
            error = None
            while tries < max_tries:
                if error is None:
                    response = self.get_func_completion_res(
                        prompt, "process_scraped_menu"
                    )
                    logger.debug(f"Got response from API: \n\n {response}")
                else:
                    logger.debug(f"Retrying with error: \n\n {error}")
                    retry_prompt = self.get_retry_prompt(current_chunk, error)
                    response = self.get_func_completion_res(
                        retry_prompt, "process_scraped_menu"
                    )

                try:
                    menu_chunk = ScraperMenu.from_api_response(response)
                    logger.debug(f"Turned into menu chunk: \n\n {menu_chunk}")
                    break
                except Exception:
                    error = traceback.format_exc()
                    logger.error(f"Scraping failed with error: \n\n {error}")

                tries += 1

            initial_menu.extend_menu(menu_chunk)

            logger.debug(f"Extended menu: \n\n {initial_menu}")

        return initial_menu


def trim_to_tokens(s, num_tokens=32000):
    return s[:num_tokens]


def write_menu(dictionary, filename: str):
    filename = filename.lower().replace(" ", "_") + ".json"
    try:
        with open(filename, "w") as file:
            json.dump(dictionary, file)
        print("Successfully wrote to", filename)
    except Exception as e:
        print("Error occurred:", e)
        print(traceback.format_exc())


def main():
    parser = argparse.ArgumentParser(description="Scrape a menu from the web")
    parser.add_argument(
        "--chunks",
        type=int,
        default=2000,
        help="Chunk size for scraping the menu",
    )
    parser.add_argument(
        "--max_len",
        type=int,
        default=32000,
        help="Max length of the menu to scrape",
    )
    parser.add_argument(
        "--menu_name",
        type=str,
        default=None,
        help="Name of menu to scrape",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="https://www.ediningexpress.com/live20/927/1749",
        help="URL of menu to scrape",
    )
    args = parser.parse_args()

    ms = ScraperAgent()

    # Create a menu from the text
    menu_html = ms.scrape(args.url)
    menu = ms.process_scraped_menu(menu_html, chunk_size=args.chunks, max=args.max_len)

    # Save / print the menu
    json.dumps(menu.as_dict(), indent=4)
    write_menu(
        menu.as_dict(), args.menu_name if args.menu_name else menu.restaurant_name
    )


if __name__ == "__main__":
    main()
