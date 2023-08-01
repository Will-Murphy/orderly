from dataclasses import dataclass, field, asdict
from typing import List
from abstract_models import AbstractAgent, AbstractOrderData
from completion_api import ApiModels
from logger import Logger
import openai
import os
import json
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support import ui

from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

openai.api_key = os.getenv("OPENAI_API_KEY")

CHROME_PATH = (
    "/Users/williammurphy/Downloads/Google Chrome.app/Contents/MacOS/Google Chrome"
)
PAGE_LOAD_WAIT_TIME = 5

logger = Logger("menu_logger")


@dataclass
class ItemDetails(AbstractOrderData):
    NAME = "name"
    PRICE = "price"
    name: str
    price: float = 0.0

    def as_dict(self):
        return asdict(self)

    @classmethod
    def get_schema(cls):
        return {
            "type": "array",
            "description": "Array of priced item details.",
            "items": {
                "type": "object",
                "description": "A priced item detail.",
                "properties": {
                    f"{ItemDetails.NAME}": {"type": "string"},
                    f"{ItemDetails.PRICE}": {"type": "number"},
                },
            },
            "required": [f"{ItemDetails.NAME}", f"{ItemDetails.PRICE}"],
        }


@dataclass
class ScraperItem(AbstractOrderData):
    NAME = "name"
    DETAILS = "details"
    CATEGORY = "category"
    PRICE = "price"

    name: str
    category: str
    details: List[str]
    price: float

    def as_dict(self):
        return {
            f"{ScraperItem.NAME}": self.name,
            f"{ScraperItem.PRICE}": self.price,
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
                f"{ScraperItem.PRICE}": {
                    "type": "number",
                    "description": "The price of the item.",
                },
                f"{ScraperItem.CATEGORY}": {
                    "type": "string",
                    "description": "The category of the item.",
                },
                f"{ScraperItem.DETAILS}": {
                    **ItemDetails.get_schema(),
                },
            },
            "required": [
                f"{ScraperItem.NAME}",
                f"{ScraperItem.PRICE}",
                f"{ScraperItem.CATEGORY}",
                f"{ScraperItem.DETAILS}",
            ],
        }


@dataclass
class ScraperMenu(AbstractOrderData):
    MENU_ITEMS = "menu_items"

    menu_items: List[ScraperItem] = field(default_factory=list)

    def __post_init__(self, *args, **kwargs):
        self.menu_items = [ScraperItem(**x) for x in self.menu_items]

    def as_dict(self):
        return {f"{ScraperMenu.MENU_ITEMS}": [x.as_dict() for x in self.menu_items]}

    @classmethod
    def get_schema(cls):
        return {
            "type": "object",
            "description": (
                "Structured list menu items with prices and details extracted from html"
            ),
            "properties": {
                f"{ScraperMenu.MENU_ITEMS}": {
                    "type": "array",
                    "description": "Array of menu items extracted from html.",
                    "items": ScraperItem.get_schema("item name"),
                },
            },
            "required": [
                f"{ScraperMenu.MENU_ITEMS}",
            ],
        }

    def extend_menu(self, other_menu: "ScraperMenu"):
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

    def scrape(self, url="https://www.ediningexpress.com/live20/927/1749"):
        print(f"Scraping menu from {url}...")
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

        print(f"Menu scraped from {url}...")

        print(html)

        driver.quit()

        return html

    def process_scraped_menu(self, text, chunk_size=4000) -> dict:
        print(f"Creating JSON menu from API...")

        initial_menu = ScraperMenu()

        while text:
            current_chunk = text[:chunk_size]
            text = text[chunk_size:]

            logger.debug(
                f"Processing raw menu chunk of len {len(current_chunk)}: \n\n {current_chunk}"
            )

            prompt = self.get_scraping_prompt(current_chunk)

            response = self.get_function_completion_response(
                prompt, "process_scraped_menu"
            )

            logger.debug(f"Got response from API: \n\n {response}")

            menu_chunk = ScraperMenu.from_api_response(response)

            logger.debug(f"Turned into menu chunk: \n\n {menu_chunk}")

            initial_menu.extend_menu(menu_chunk)

            logger.debug(f"Extended menu: \n\n {initial_menu}")

        return initial_menu


def trim_to_tokens(s, num_tokens=32000):
    return s[:num_tokens]


def main():
    ms = ScraperAgent()
    # Create a menu from the text
    menu_html = ms.scrape()

    # context to large, need function calls and context chunks
    menu = ms.process_scraped_menu(menu_html)

    # Print the menu
    json.dumps(menu, indent=4)


if __name__ == "__main__":
    main()
