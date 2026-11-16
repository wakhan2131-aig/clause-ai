from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from app.services.chat import RAGService

SYSTEM ="YOU are a helpful clause ai customer support assistant"

class ClauseAgent:
    def __init__(self) ->None:
        self.rag= RAGService()

llm = init_chat_model(
    model = "gemma4:31b-cloud",
    model_provider="ollama",
    temperature = 0.1
)

agent = create_agent(
    model = llm, 
    tools = [], 
    system_prompt=SYSTEM
)

query = input("Query: ")

result = agent.invoke(input={"messages": [HumanMessage(content=query)]})
print(result["messages"][-1].text)