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


def trim_to_tokens(s, num_tokens=32000):
    return s[:num_tokens]


def create_menu_from_text(text) -> dict:
    # Generate a prompt to convert text to JSON
    # add function calls??
    
    print(f"Creating JSON menu from API...")
    prompt = (
        f"Convert the following menu page html to a JSON menu: '{text}'"
    )

    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k-0613",
        messages=[{"role": "user", "content": prompt}],
    )
    
    print(f"JSON menu created from API... {completion}")

    # Get the generated menu as JSON
    menu = completion.choices[0].message

    return menu.to_dict()["content"]

def main():
    # Create a menu from the text
    menu_html = scrape()

    # context to large, need function calls and context chunks
    menu = create_menu_from_text(trim_to_tokens(menu_html))

    # Print the menu
    json.dumps(menu, indent=4)

# TODO: add chunked scraping 
def scrape(url="https://www.ediningexpress.com/live20/927/1749"):
    
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


if __name__ == "__main__":
    main()
