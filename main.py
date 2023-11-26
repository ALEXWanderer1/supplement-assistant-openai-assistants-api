import json
import os
import time
from flask import Flask, request, jsonify
import openai
from openai import OpenAI
import functions

# Check OpenAI version compatibility
from packaging import version

required_version = version.parse("1.1.1")
current_version = version.parse(openai.__version__)
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
if current_version < required_version:
  raise ValueError(
      f"Error: OpenAI version {openai.__version__} is less than the required version 1.1.1"
  )
else:
  print("OpenAI version is compatible.")

# Create Flask app
app = Flask(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Create or load assistant
assistant_id = functions.create_assistant(
    client)  # this function comes from "functions.py"


# Start conversation thread
@app.route('/start', methods=['GET'])
def start_conversation():
  print("Starting a new conversation...")
  thread = client.beta.threads.create()
  print(f"New thread created with ID: {thread.id}")
  return jsonify({"thread_id": thread.id})


# Generate response
@app.route('/chat', methods=['POST'])
def chat():
  data = request.json
  thread_id = data.get('thread_id')
  user_input = data.get('message', '')

  if not thread_id:
    print("Error: Missing thread_id")
    return jsonify({"error": "Missing thread_id"}), 400

  print(f"Received message: {user_input} for thread ID: {thread_id}")

  # Add the user's message to the thread
  client.beta.threads.messages.create(thread_id=thread_id,
                                      role="user",
                                      content=user_input)

  # Run the Assistant
  run = client.beta.threads.runs.create(thread_id=thread_id,
                                        assistant_id=assistant_id)

  # Check if the Run requires action (function call)
  while True:
    run_status = client.beta.threads.runs.retrieve(thread_id=thread_id,
                                                   run_id=run.id)
    # print(f"Run status: {run_status.status}")
    if run_status.status == 'completed':
      break
    elif run_status.status == 'requires_action':
      # Handle the function call
      for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
        if tool_call.function.name == "fetch_supplement_info":
          # Process fetch supplement information
          arguments = json.loads(tool_call.function.arguments)
          output = functions.fetch_supplement_info(
              arguments["query"])
          # Assuming output is a dictionary with the supplement information
          client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id,
                                                         run_id=run.id,
                                                         tool_outputs=[{
                                                             "tool_call_id":
                                                             tool_call.id,
                                                             "output":
                                                             json.dumps(output)
                                                         }])
        elif tool_call.function.name == "search_reviews_duckduckgo":
          # Process fetch supplement information
          arguments = json.loads(tool_call.function.arguments)
          output = functions.search_reviews_duckduckgo(
              arguments["supplement"])
          # Assuming output is a dictionary with the supplement information
          client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id,
                                                         run_id=run.id,
                                                         tool_outputs=[{
                                                             "tool_call_id":
                                                             tool_call.id,
                                                             "output":
                                                             json.dumps(output)
                                                         }])
      time.sleep(1)  # Wait for a second before checking again

  # Retrieve the latest message from the assistant
  messages = client.beta.threads.messages.list(thread_id=thread_id)
  message = messages.data[0]

  # Extract content and annotations
  message_content = message.content[0].text
  annotations = message_content.annotations
  citations = []

  # Process annotations and replace in message text
  for index, annotation in enumerate(annotations):
      message_content.value = message_content.value.replace(annotation.text, f' [{index}]')

      if file_citation := getattr(annotation, 'file_citation', None):
          cited_file = client.files.retrieve(file_citation.file_id)
          citations.append(f'[{index}] {file_citation.quote} from {cited_file.filename}')

  # Append citations to the response
  message_content.value += '\n\n' + '\n'.join(citations)

  # Return the formatted response
  return jsonify({"response": message_content.value})


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=8080)
