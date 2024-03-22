import openai
import os
from dotenv import load_dotenv, find_dotenv
import requests
import json
import time
import streamlit as st

load_dotenv(find_dotenv())

news_api_key = os.getenv("NEWS_API_KEY")

openai.api_key = os.getenv("OPENAI_API_KEY")

model = "gpt-3.5-turbo-16k"


def get_news(topic):

    url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={news_api_key}&pageSize=5"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            news = json.dumps(response.json(), indent=4)
            news_data = json.loads(news)

            status = news_data["status"]
            total_results = news_data["totalResults"]
            articles = news_data["articles"]
            full_news = []

            for article in articles:
                source_name = article["source"]["name"]
                author = article["author"]
                title = article["title"]
                description = article["description"]
                url = article["url"]
                content = article["content"]

                display_news = f"""
                    Title: {title},
                    Author: {author},
                    Source: {source_name},
                    Description: {description},
                    URL: {url}  
                """
                full_news.append(display_news)

            return full_news    
        else:
            return []

    except requests.exceptions.RequestException as e:
        print("Error occured during the API Request", e)



# Create an assistant manager

class AssistantManager:
    thread_id = "thread_XUN41PFpRVUa8s3U5WfpMZmz"
    assistant_id = "asst_xRqX3sZVxYL5uH03IAokybYp"

    def __init__(self, model: str= model):
        self.model = model
        self.assistant = None
        self.thread = None
        self.run = "run_Kkd237n4nwBFvhzcAmENI8pY"
        self.summary = None

        if AssistantManager.assistant_id:
            self.assistant = openai.beta.assistants.retrieve(
                assistant_id=AssistantManager.assistant_id
            )
        if AssistantManager.thread_id:
            self.thread = openai.beta.threads.retrieve(
                thread_id=AssistantManager.thread_id
            )

    def create_assistant(self, name, instructions, tools):
        if not self.assistant:
            created_assistant = openai.beta.assistants.create(
                name=name, instructions=instructions, tools=tools, model=self.model
            )
            AssistantManager.assistant_id = created_assistant.id
            self.assistant = created_assistant
            print(f"AssisID===> {self.assistant.id}")

    def create_thread(self):
        if not self.thread:
            thread_obj = openai.beta.threads.create()
            AssistantManager.thread_id = thread_obj.id
            self.thread = thread_obj
            print(f"ThreadID===> {self.thread.id}")

    def add_message_to_thread(self, role, content):
        if self.thread:
            openai.beta.threads.messages.create(
                thread_id=self.thread.id, role=role, content=content
            )

    def run_assistant(self, instructions):
        if self.thread and self.assistant:
            self.run = openai.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant.id,
                instructions=instructions,
            )

    def process_message(self):
        if self.thread:
            messages = openai.beta.threads.messages.list(thread_id=self.thread.id)
            summary = []

            previous_message = messages.data[0]
            role = previous_message.role
            response = previous_message.content[0].text.value
            summary.append(response)

            self.summary = "\n".join(summary)
            print(f"SUMMARY===> {role.capitalize()}: ==> {response}")

    def call_required_functions(self, required_actions):
        if not self.run:
            return
        tool_outputs = []

        for action in required_actions["tool_calls"]:
            func_name = action["function"]["name"]
            arguments = json.loads(action["function"]["arguments"])

            if func_name == "get_news":
                output = get_news(topic=arguments["topic"])
                print(f"+++{output}+++")
                final_str = ""
                for item in output:
                    final_str += "".join(item)

                tool_outputs.append({"tool_call_id": action["id"], "output": final_str})
            else:
                raise ValueError(f"Unknown function: {func_name}")

        print("Submitting outputs back to the Assistant...")
        openai.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread.id, run_id=self.run.id, tool_outputs=tool_outputs
        )

    def get_summary(self):
        return self.summary

    def wait_for_completion(self):
        if self.thread and self.run:
            while True:
                time.sleep(5)
                run_status = openai.beta.threads.runs.retrieve(
                    thread_id=self.thread.id, run_id=self.run.id
                )
                print(f"RUN STATUS:: {run_status.model_dump_json(indent=4)}")

                if run_status.status == "completed":
                    self.process_message()
                    break
                elif run_status.status == "requires_action":
                    print("FUNCTION CALLING NOW...")
                    self.call_required_functions(
                        required_actions=run_status.required_action.submit_tool_outputs.model_dump()
                    )


def main():
    manager = AssistantManager()

    # Streamlit interface
    st.title("News Summarizer")

    with st.form(key="user_input_form"):
        instructions = st.text_input("Enter topic:")
        submit_button = st.form_submit_button(label="Run Assistant")

        if submit_button:
            manager.create_assistant(
                name="News Summarizer",
                instructions="You are a personal article summarizer Assistant who knows how to take a list of article's titles and descriptions and then write a short summary of all the news articles",
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "get_news",
                            "description": "Get the list of articles/news for the given topic",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "topic": {
                                        "type": "string",
                                        "description": "The topic for the news, e.g. bitcoin",
                                    }
                                },
                                "required": ["topic"],
                            },
                        },
                    }
                ],
            )
            manager.create_thread()

            # Add the message and run the assistant
            manager.add_message_to_thread(
                role="user", content=f"summarize the news on this topic {instructions}?"
            )
            manager.run_assistant(instructions="Summarize the news")

            # Wait for completions and process messages
            manager.wait_for_completion()

            summary = manager.get_summary()

            st.write(summary)


if __name__ == "__main__":
    main()

