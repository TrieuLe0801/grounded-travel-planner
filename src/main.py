from dotenv import load_dotenv

load_dotenv()

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langsmith import traceable

MAX_ITERATIONS = 10
model = "openai:gpt-5"


# Tool decorator (langchain)
@tool
def get_ticket_price(plane: str) -> float:
    """look up the plane ticket"""
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
    print(
        f">> execute the apply_the_discount(price={price}, discount_tier={discount_tier})"
    )
    discount_percentages = {"bronze": 5, "silver": 12, "gold": 25}
    discount = discount_percentages.get(discount_tier, 0)
    return round(price * (1 - discount / 100), 2)


# Agent loop
@traceable(name="Langchain Agent loop")
def run_agent(question: str) -> str | None:
    tools = [get_ticket_price, apply_the_discount]
    tools_dict = {t.name: t for t in tools}

    llm = init_chat_model(model=model, temperature=0)
    llm_with_tools = llm.bind_tools(tools)

    print(f"Question: {question}")
    print("=" * 60)

    messages = [
        SystemMessage(
            content=(
                "You are a helpful plane ticket hunter. "
                "You have access to a plane ticket price tool and a discount tool.\n\n"
                "There are some STRICT RULES - you must follow them:\n\n"
                "1. NEVER guess or assume any ticket price. "
                "You must call the get_ticket_price tool first and get the real price.\n"
                "2. You only call the apply_the_discount AFTER you have received a price "
                "from get_ticket_price. Pass the exact price "
                "returned by the get_ticket_price - DO NOT make up any number.\n"
            )
        ),
        HumanMessage(content=question),
    ]

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- Iteration {iteration} ---")

        ai_message = llm_with_tools.invoke(messages)

        tool_calls = ai_message.tool_calls

        # If no tool calls, this is the final answer
        if not tool_calls:
            print(f"\nFinal Answer: {ai_message.content}")
            return ai_message.content

        # Process only the FIRST tool call — force one tool per iteration
        tool_call = tool_calls[0]
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})
        tool_call_id = tool_call.get("id")

        print(f"  [Tool Selected] {tool_name} with args: {tool_args}")

        tool_to_use = tools_dict.get(tool_name)
        if tool_to_use is None:
            raise ValueError(f"Tool '{tool_name}' not found")

        observation = tool_to_use.invoke(tool_args)

        print(f"  [Tool Result] {observation}")

        messages.append(ai_message)
        messages.append(
            ToolMessage(content=str(observation), tool_call_id=tool_call_id)
        )

    print("ERROR: Max iterations reached without a final answer")
    return None


if __name__ == "__main__":
    print("Hello LangChain Agent (.bind_tools)!")
    print()
    result = run_agent(
        "What is the price of a Vietnam_Airline ticket after applying a gold discount?"
    )
    print(result)