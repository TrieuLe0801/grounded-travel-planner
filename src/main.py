from dotenv import load_dotenv
load_dotenv()

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_tavily import TavilySearch
from tavily import TavilyClient


# Intialize Tavily
tavily_client = TavilyClient()

# Initialize tools
@tool
def search(query: str) -> str:
    """
    Tool that searches over internet
    Args:
        query: The query to search for
    Returns:
        The search result
    """
    print(f"Result for {query}")
    return str(tavily_client.search(query=query))

# initialize the agent first
agent = create_agent(
        model="openai:gpt-5.5", 
        tools=[search], 
        system_prompt="You are a helpful assistant. Be concise and accurate.",
    )


def main():
    print("Hello World!")
    result = agent.invoke({"messages":HumanMessage(content="search for 3 tourist attracted places in Ha Giang and list their details")})
    print(result)


if __name__ == "__main__":
    main()
