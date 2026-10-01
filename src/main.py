from dotenv import load_dotenv
load_dotenv()

from langchain.agents import create_agent
from langchain.tools import tool
from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.chat_models import init_chat_model
from langsmith import traceable

MAX_ITERATIONS=10
model="openai:gpt-5"

#Tool decorator (langchain)
@tool
def get_ticket_price(plane: str) -> float:
    """look up the plane ticket """
    print(f">> execute the get_ticket_price(plane: {plane})")
    prices = {
        "Vietnam_Airline": 1_000_000,
        "Vietjet_Air": 750_000,
        "Bamboo_Airway": 950_000,
        "Phu_Quoc_Air": 900_000, 
    }
    return prices.get(plane, 0)

@tool
def apply_the_discount(price: float, discount_tier: str) -> float:
    """Apply the discount tier to a price and return the discounted price"""
    print(f">> execute the apply_the_discount(price={price}, discount_tier={discount_tier})")
    discount_percentages = {
        "bronze": 5,
        "silver": 12,
        "gold": 25
    }
    discount = discount_percentages.get(discount_tier, 0)
    return round(price * (1 - discount / 100), 2)

# Agent loop
@traceable("Langchain Agent loop")
def run_agent(question: str):
    pass


if __name__=="__main__":
    run_agent()