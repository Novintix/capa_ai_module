# Policy-Driven Detection Score Agent

**Agent Type**: Hybrid (Deterministic Routing + LLM-Based Reasoning)

A production-ready FMEA Detection Score Agent that combines deterministic workflow orchestration with LLM-powered intelligent reasoning to calculate detection scores (1-10) based on policy documents and complaint data.

---

## Agent Architecture

### Agent Classification

This is a **Hybrid Agent** that combines:

1. **Deterministic Components**:
   - State management (TypedDict-based structured state)
   - Workflow routing (predictable conditional edges)
   - File validation and extraction
   - Error handling and fallback logic

2. **LLM-Based Components**:
   - Policy rule extraction from documents
   - Intelligent complaint-to-rule matching
   - Detection score calculation with reasoning
   - Confidence scoring

### Why Hybrid?

- **Deterministic routing** ensures predictable, testable workflow execution
- **LLM reasoning** provides flexible, intelligent interpretation of policies and complaints
- **Best of both worlds**: Reliability + Intelligence

---

## Features

✅ **Policy-Driven** - Extracts scoring rules from any policy document  
✅ **Multi-Format Support** - PDF, Word, Excel, Images (OCR)  
✅ **LangGraph Orchestration** - Structured state management with 7 focused nodes  
✅ **Intelligent Fallback** - Works with or without policy documents  
✅ **Confidence Scoring** - Transparency in decision quality  
✅ **Comprehensive Logging** - All operations logged to logs/process.log  
✅ **Error Recovery** - Automatic fallback to default FMEA rules  
✅ **Industry Agnostic** - No hardcoded business logic  

---

## Project Structure

```
detection-v2/
├── logs/                    # Process logs
│   └── process.log
├── tools/                   # Document extractors
│   ├── pdf_extractor.py
│   ├── word_extractor.py
│   ├── excel_extractor.py
│   └── ocr_extractor.py
├── agent.py                 # LangGraph agent + routing logic
├── nodes.py                 # 7 focused node functions
├── state.py                 # AgentState TypedDict
├── schemas.py               # Pydantic schemas (input/output)
├── prompt.py                # All LLM prompts
├── model_config.py          # Model configuration
├── logger.py                # Logging utility
├── router.py                # FastAPI routes
├── requirements.txt         # Dependencies
├── .env                     # Environment variables
└── README.md                # This file
```

---

