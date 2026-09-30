from dotenv import load_dotenv
from typing import List
load_dotenv()

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_tavily import TavilySearch
from tavily import TavilyClient
from pydantic import BaseModel, Field

# Apply Pydantic
class Sources(BaseModel):
    """Schema for sources used by agent"""
    url: str = Field(description="The URL of the source")

class AgentResponse(BaseModel):
    """Schema for Agent responsing the answer and sources"""
    answer: str = Field(description="The agent's answer to the query")
    sources: List[Sources] = Field(default_factory=list, description="List of resources")


# initialize the agent first
agent = create_agent(
        model="openai:gpt-5.5", 
        tools=[TavilySearch()], 
        system_prompt="You are a helpful assistant. Be concise and accurate.",
        response_format=AgentResponse
    )


def main():
    print("Hello World!")
    result = agent.invoke({"messages":HumanMessage(content="search for 3 tourist attracted places in Ha Giang and list their details")})
    print(result)


if __name__ == "__main__":
    main()