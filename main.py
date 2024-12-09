from typing import Optional

from fastapi import FastAPI, HTTPException, Body
from openai import OpenAI
import time
import os

app = FastAPI()
client = OpenAI()
# Set your OpenAI API key
client.api_key = os.environ.get("OPENAI_API_KEY", None)

# Your previously created assistant ID
assistantID = os.environ.get("OPENAI_ASSISTANT_ID", None)


@app.get("/")
async def root():
    return {"message": "Hello World"}


# Pretty printing helper
def response_dict(messages) -> dict:
    data = {}
    for m in messages:
        # If we haven't seen this role before, initialize a list
        if m.role not in data:
            data[m.role] = []
        # Append the message content to the list associated with this role
        # Assuming m.content[0].text.value is a string
        data[m.role].append(m.content[0].text.value)
    return data


def wait_on_run(run, thread):
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run


@app.get("/")
def hello():
    return {"message": "app is running"}


@app.post("/chat")
def chat(
    user_text: str = Body(..., embed=True),
    thread_id: Optional[str] = Body(None, embed=True),
):
    """
    POST JSON:
    {
      "user_text": "hello my world",
      "thread_id": "<optional: if you have one from previous request>"
    }

    If no thread_id is provided, we create a new thread.
    Then we add the user_text as a message in that thread and get the assistant's response.
    Returns:
    {
      "response": "<assistant message>",
      "thread_id": "<thread_id>"
    }
    """
    # If no thread_id, create a new thread
    if not thread_id:
        try:
            # Create a new thread
            thread = client.beta.threads.create()
            thread_id = thread.id
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    try:
        # retrieve thread
        thread = client.beta.threads.retrieve(thread_id)

        # Add a message to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_text,
        )

        # create a run (linking thread to assistant)
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistantID,
            instructions="Be a helpful therapist",
        )
        run = wait_on_run(run, thread)

        if run.status == "completed":
            # Retrieve all messages
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            # If needed, just retrieve the last messages after the user's message
            messages_last = client.beta.threads.messages.list(
                thread_id=thread.id, order="asc", after=message.id
            )
        else:
            # Run was not completed successfully
            print(run.status)

        conversation = client.beta.threads.messages.list(
            thread_id=thread.id, order="asc"
        )

        response = response_dict(conversation)

        return {"response": response, "thread_id": thread_id}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/thread/{thread_id}")
def retrieve_thread(thread_id: str):
    """
    Retrieve a thread and its messages.
    GET /thread/<thread_id>
    """
    try:
        thread = client.beta.threads.retrieve(
            assistant_id=assistantID, thread_id=thread_id
        )
        # The thread object includes messages, title, etc.
        return thread
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
