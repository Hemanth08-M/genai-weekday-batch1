from fastapi import FastAPI
from pydantic import BaseModel
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def multiply(a:float, b:float) -> float:
    """Multiply two numbers"""
    return a*b

@tool
def word_count(text: str) -> int:
    """Count the number of words in a text"""
    return len(text.split())

model = ChatOpenAI(
    model="gpt-5-nano"
)

agent = create_agent(
    model = model,
    tools=[multiply, word_count],
    system_prompt="You are a helpful assistant. Use tools to answer the user's query"
)

app = FastAPI()

class Query(BaseModel):
    question: str

@app.get("/health")
def health():
    return {"status":"OK"}

@app.post("/ask")
def ask(q: Query):
    result = agent.invoke({"messages": [{"role": "user", "content": q.question}]})
    return result
