# The Task
---
Build a Newspaper Delivery AI Agent. When the agent is triggered, it should go out and find the latest and most important news from the last 2 days (counting from the moment the request is made), then return a short summary written in plain simple English, along with the source links it used.

The agent must run behind a FastAPI service exposed through a POST endpoint, be built with LangChain (or LangGraph), and use OpenRouter as the LLM provider. To search the web for news, the agent must use the Tavily API, connected to the agent as a LangChain tool.
## Input
The endpoint accepts a JSON body with one optional field: category.
category is an enum with three possible values:
-  `tech`
- `economics`
- `politics`

If no category is sent, the agent should return general top news.

## Output
The endpoint returns a JSON response with:
-  A `summary` field: a plain English text explaining the latest news for today. Keep it clear and easy to read, no jargon.
- A sources field: a list of https links to the original articles the agent used. One response must not contain more than 5 source links.

## Requirements
1. FastAPI backend with a POST endpoint that triggers the agent.
2. Pydantic schemas for both the request and the response. The category input must be a Pydantic enum. All inputs and outputs must be validated.
3. LangChain or LangGraph agent with the Tavily search API connected as a tool.
4. OpenRouter as the LLM provider, using the model google/gemma-4-31b-it.
5. News window: the agent should focus on news from the last 2 days only.
6. Max 5 source links in the response.
7. Swagger docs should work out of the box (FastAPI gives this for free at /docs).
8. Clean Python. Use type hints on functions, keep files organized, and write code that is easy to read.
9. Async is preferred but not required.
10. A short README explaining how to run the project, how to set the API keys, and an example request.

## Documentation Links
- Tavily — https://docs.tavily.com/welcome#search-the-web
- LangChain Agents — https://docs.langchain.com/oss/python/langchain/agents
- FastAPI — https://fastapi.tiangolo.com/
- Model on OpenRouter — https://openrouter.ai/google/gemma-4-31b-it

## What We Will Look At
- Code quality and structure (software engineering side)
- How you set up the agent, the Tavily tool, and the prompt (AI engineering side)
- Correct use of Pydantic for validation, including the category enum
- Whether the agent actually returns recent, relevant news with valid source links
- Whether the endpoint works end to end through Swagger
- Bonus: an attached Claude Code /export session if you used one