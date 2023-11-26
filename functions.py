import json
import requests
import os
from openai import OpenAI
from prompts import assistant_instructions
from langchain.tools import DuckDuckGoSearchRun

OPENAI_API_KEY = os.environ['OPENAI_API_KEY']

# Init OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)

# Function to fetch supplement information
def fetch_supplement_info(query):
  SERPAPI_KEY = os.environ['SERPAPI_KEY']  # Ensure you have set this environment variable
  params = {
      "engine": "google_shopping",
      "q": query,
      "num": 5,
      "api_key": SERPAPI_KEY
  }

  try:
      response = requests.get("https://serpapi.com/search", params=params)
      response.raise_for_status()
      data = response.json()

      products = data.get('shopping_results', [])
      if not products:
          return "No supplements found for your query."

      # Format and return the results
      results = []
      for product in products:
          result = {
              "name": product.get("title"),
              "link": product.get("link"),
              "price": product.get("extracted_price"),
              "image": product.get("thumbnail")
          }
          results.append(result)
  
      return results

  except requests.RequestException as e:
      return f"An error occurred: {e}"

def search_reviews_duckduckgo(supplement):
  search = DuckDuckGoSearchRun()
  results = search.run(f'{supplement} reviews site:webmd.com')
  if results:
      return results
  else:
      return None

# Create or load assistant
def create_assistant(client):
  assistant_file_path = 'assistant.json'

  # If there is an assistant.json file already, then load that assistant
  if os.path.exists(assistant_file_path):
    with open(assistant_file_path, 'r') as file:
      assistant_data = json.load(file)
      assistant_id = assistant_data['assistant_id']
      print("Loaded existing assistant ID.")
  else:
    # If no assistant.json is present, create a new assistant using the below specifications

    # To change the knowledge document, modifiy the file name below to match your document
    # If you want to add multiple files, paste this function into ChatGPT and ask for it to add support for multiple files
    file = client.files.create(file=open("KB.docx", "rb"),
                               purpose='assistants')

    assistant = client.beta.assistants.create(
        # Getting assistant prompt from "prompts.py" file, edit on left panel if you want to change the prompt
        instructions=assistant_instructions,
        model="gpt-3.5-turbo-1106",
        tools=[
            {
                "type": "retrieval"  # This adds the knowledge base as a tool
            },
            {
              "type": "function",  # Supplement showcase function
              "function": {
                  "name": "fetch_supplement_info",
                  "description": "Search for supplement price, brands when user is requesting current information about some of the supplements to buy",
                  "parameters": {
                      "type": "object",
                      "properties": {
                          "query": {
                              "type": "string",
                              "description": "Query term to search for supplements."
                          }
                      },
                      "required": ["query"]
                  }
              }
            },
            {
              "type": "function",  # Supplement reviews function
              "function": {
                  "name": "search_reviews_duckduckgo",
                  "description": "Search for supplement's reviews when user is asking for reviews",
                  "parameters": {
                      "type": "object",
                      "properties": {
                        "supplement": {
                              "type": "string",
                              "description": "Suplement to search reviews for."
                          }
                      },
                      "required": ["supplement"]
                  }
              }
            }
            ],
            file_ids=[file.id])

    # Create a new assistant.json file to load on future runs
    with open(assistant_file_path, 'w') as file:
      json.dump({'assistant_id': assistant.id}, file)
      print("Created a new assistant and saved the ID.")

    assistant_id = assistant.id

  return assistant_id
