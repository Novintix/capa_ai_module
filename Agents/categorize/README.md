# Categorization Agent

## Overview
The Categorization Agent classifies root causes into the 6M categories used in Fishbone (Ishikawa) Diagrams for root cause analysis.

## 6M Categories

1. **Man (People)** - Human errors, training gaps, operator mistakes
2. **Machine (Equipment)** - Equipment failures, calibration issues, automation problems
3. **Method (Process/SOP)** - Process design flaws, inadequate procedures, setup errors
4. **Material** - Raw material defects, wrong grades, supplier issues
5. **Measurement (Inspection)** - Detection failures, inspection gaps, calibration problems
6. **Environment** - Temperature, humidity, cleanliness, external factors

## API Endpoint

### POST `/categorize/analyze`

**Request Body:**
```json
{
  "question": "Why was the syringe marking incorrect?",
  "causes": [
    {
      "cause_id": "C001",
      "cause_text": "Excess ink, insufficient drying time",
      "process_step": "Syringe Marking",
      "failure_mode": "Smudged markings",
      "potential_effects": "Poor readability",
      "current_controls": "Optimize ink viscosity",
      "source": "FMEA"
    }
  ],
  "additional_context": "Optional context"
}
```

**Response:**
```json
{
  "categorized_causes": [
    {
      "cause_id": "C001",
      "cause_text": "Excess ink, insufficient drying time",
      "category": "Method",
      "confidence": 0.9,
      "reasoning": "Process parameter issue related to ink application and curing"
    }
  ],
  "summary": {
    "Man": 0,
    "Machine": 2,
    "Method": 5,
    "Material": 1,
    "Measurement": 1,
    "Environment": 0
  }
}
```

## Architecture

- **state.py** - Pydantic models for input/output
- **prompts.py** - LLM prompt templates
- **utils.py** - Helper functions for prompt building
- **nodes.py** - Graph node implementations
- **graph.py** - LangGraph workflow definition
- **router.py** - FastAPI endpoint
- **logger.py** - Logging utilities

## Usage Example

```python
from Agents.categorize.state import CategorizeInput, Cause

input_data = CategorizeInput(
    question="Why was the syringe marking incorrect?",
    causes=[
        Cause(
            cause_id="C001",
            cause_text="Ink nozzle clogging",
            process_step="Marking",
            failure_mode="Missing markings",
            potential_effects="Dosing error",
            current_controls="Vision inspection",
            source="FMEA"
        )
    ]
)

# Call via API or directly invoke graph
from Agents.categorize.graph import categorize_graph
result = categorize_graph.invoke({"input": input_data, "iteration": 0})
```
