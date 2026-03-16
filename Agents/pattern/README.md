# Pattern Agent

The Pattern Agent analyzes historical complaint data from MongoDB Atlas to identify trends and patterns for a given complaint input. It uses LLM reasoning to classify the trend on a scale of 1 to 10.

## Trend Scale Definitions

1: **No trend**; stable flat data
2: **Minor fluctuation** but no upward trend
3: **One short-term spike**, not repeated
4: **Weak increasing tendency**
5: **Small but noticeable trend signal**
6: **Clear visible upward trend**
7: **Strong accelerating trend**
8: **Recurring trend peaks**
9: **Persistent accelerating trend**
10: **Uncontrolled exponential trend**

## Architecture

- `agent.py`: Main entry point class.
- `graph.py`: LangGraph workflow definition.
- `nodes.py`: Implementation of workflow nodes (data fetching, analysis, etc.).
- `schemas.py`: Input/Output data schemas (Pydantic).
- `state.py`: internal state definition for the agent.
- `prompt.py`: LLM prompts for trend analysis.
- `router.py`: FastAPI router for API integration.

## Setup

1. Ensure `MONGODB_URI` is set in your `.env` file.
2. Install dependencies: `pip install pymongo`
