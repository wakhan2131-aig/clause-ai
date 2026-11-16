
import sqlite3
from typing import Any, Iterator

from app.services.chat import RAGService

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain.tools import tool

from langgraph.checkpoint.sqlite import SqliteSaver


SYSTEM = """
You are a helpful Clause AI customer support assistant.

Rules:
1. Answer using the handbook information whenever relevant.
2. Be accurate and concise.
3. Do not invent information.
4. If the handbook does not contain the answer, say:
   I don't know based on the available handbook information.
5. Maintain conversation context.
"""


class ClauseAgent:

    def __init__(self) -> None:

        # Initialize RAG service
        self.rag = RAGService()

        # SQLite persistent memory
        self.conn = sqlite3.connect(
            "memory.db",
            check_same_thread=False
        )

        self.checkpointer = SqliteSaver(self.conn)
        self.checkpointer.setup()

        # Initialize Ollama model
        self.llm = init_chat_model(
            model="gemma3:4b",
            model_provider="ollama",
            temperature=0.1
        )

        # Handbook search tool
        @tool(response_format="content_and_artifact")
        def search_handbook(query: str) -> tuple[str, list]:

            """Search the Clause customer handbook for relevant information."""

            results = self.rag.store.similarity_search_with_score(
                query=query,
                k=self.rag.settings.top_k
            )

            if not results:
                return "Nothing found in the handbook.", []

            texts = []
            sources = []

            for doc, score in results:

                texts.append(doc.page_content)

                sources.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score)
                })

            content = "\n\n".join(texts)

            return content, sources

        # Create LangGraph agent
        self.agent = create_agent(
            model=self.llm,
            tools=[search_handbook],
            system_prompt=SYSTEM,
            checkpointer=self.checkpointer
        )

    # Normal response
    def ask(
        self,
        question: str,
        thread_id: str = "default"
    ) -> str:

        result = self.agent.invoke(
            {
                "messages": [
                    HumanMessage(content=question)
                ]
            },
            config={
                "configurable": {
                    "thread_id": thread_id
                }
            }
        )

        messages = result["messages"]

        return messages[-1].content

    # Streaming response
    def stream(
        self,
        question: str,
        thread_id: str = "default"
    ) -> Iterator[str]:

        for message, metadata in self.agent.stream(
            {
                "messages": [
                    HumanMessage(content=question)
                ]
            },
            config={
                "configurable": {
                    "thread_id": thread_id
                }
            },
            stream_mode="messages"
        ):

            # Only display model response chunks
            if metadata.get("langgraph_node") != "model":
                continue

            if isinstance(message.content, str):
                if message.content:
                    yield message.content

            elif isinstance(message.content, list):
                for block in message.content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "text"
                    ):
                        yield block.get("text", "")

    # Close SQLite connection
    def close(self) -> None:
        self.conn.close()


# Run agent directly
if __name__ == "__main__":

    agent = ClauseAgent()

    try:
        while True:

            query = input("\nQuery: ")

            if query.lower() in ["exit", "quit"]:
                break

            print("\nAssistant: ", end="", flush=True)

            for chunk in agent.stream(query):
                print(chunk, end="", flush=True)

            print()

    finally:
        agent.close()
