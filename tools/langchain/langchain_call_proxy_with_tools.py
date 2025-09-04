from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
import logging
import argparse
from typing import Dict, Any, Optional
import requests
import json
from pydantic import BaseModel
from datetime import datetime
from zoneinfo import ZoneInfo


# # Setup logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

system_prompt= """
You are an expert in AI solution and you help your colleague to implement AI solutions
"""


# Simplified timezone data
TIMEZONE_DATA = {
    "tokyo": "Asia/Tokyo",
    "san francisco": "America/Los_Angeles",
    "paris": "Europe/Paris"
}

@tool
def get_current_time(location):
    """Get the current time for a given location"""
    print(f"get_current_time called with location: {location}")
    location_lower = location.lower()

    for key, timezone in TIMEZONE_DATA.items():
        if key in location_lower:
            print(f"Timezone found for {key}")
            current_time = datetime.now(ZoneInfo(timezone)).strftime("%I:%M %p")
            return json.dumps({
                "location": location,
                "current_time": current_time
            })

    print(f"No timezone data found for {location_lower}")
    return json.dumps({"location": location, "current_time": "unknown"})


class OutputSchema(BaseModel):
    """Schema for response."""

    answer: str
    justification: str


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Model's name as defined in Azure Deployment model", default="gpt-4o")
    parser.add_argument("--question", help="Question to ask the model", required=False, default="What's the current time in San Francisco?")
    args = parser.parse_args()

    print(f"Script will use the model: {args.model}")
    print(f"Script will answer to the question: {args.question}")

    messages=[SystemMessage(content=system_prompt), HumanMessage(content=args.question)]


    # Initialize model
    print("Initialize llm")

    llm = ChatOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s",
        model=args.model,
        temperature=0,
        max_retries=2
    )

    llm_with_tools = llm.bind_tools([get_current_time])

    print("First API call: Ask the model to use the function")
    ai_msg = llm_with_tools.invoke(messages)

    print(ai_msg.tool_calls)

    messages.append(ai_msg)

    print("Handle tool calls")
    for tool_call in ai_msg.tool_calls:
        selected_tool = {"get_current_time": get_current_time}[tool_call["name"].lower()]
        tool_msg = selected_tool.invoke(tool_call)
        messages.append(tool_msg)

    print(messages)

    print("Second API call: Give the final answer")
    final_ai_msg = llm_with_tools.invoke(messages)

    print(final_ai_msg.content)


if __name__ == "__main__":
    main()