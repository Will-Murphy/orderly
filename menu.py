import openai
import os
import json

openai.api_key = os.getenv('OPENAI_API_KEY')

def create_menu_from_text(text):
    # Generate a prompt to convert text to JSON
    prompt = f"Convert the following menu text to JSON: '{text}'"

    response = openai.Completion.create(
      engine="text-davinci-003",
      prompt=prompt,
      temperature=0.5,
      max_tokens=100
    )

    # Get the generated menu as JSON
    generated_menu_json = response.choices[0].text.strip()
    menu = json.loads(generated_menu_json)

    return menu

def main():
    # Define the menu text
    menu_text = "burger is 5.0, soda is 2.0, pizza is 8.0, coffee is 3.0"

    # Create a menu from the text
    menu = create_menu_from_text(menu_text)

    # Print the menu
    print(menu)

if __name__ == '__main__':
    main()
