# Similar Cases Agent

**Agent Type**: Hybrid (Vector Search + LangGraph Orchestration)

A production-ready agent that finds semantically similar complaint cases using MongoDB Atlas Vector Search and sentence-transformers embeddings.

---

## Agent Architecture

### Agent Classification

This is a **Hybrid Agent** that combines:

1. **Deterministic Components**:
   - State management (Pydantic-based structured state)
   - Workflow routing (linear graph execution)
   - MongoDB connection management
   - Error handling and logging

2. **ML-Based Components**:
   - Sentence-transformers for text embeddings
   - MongoDB Atlas Vector Search for similarity matching
   - Cosine similarity scoring

### Why Hybrid?

- **Deterministic workflow** ensures predictable, testable execution
- **ML embeddings** provide semantic understanding of complaint text
- **Vector search** enables efficient similarity matching at scale
- **Best of both worlds**: Reliability + Intelligence

---

## Features

✅ **Semantic Search** - Finds similar cases based on meaning, not just keywords  
✅ **MongoDB Atlas Vector Search** - Scalable vector similarity search  
✅ **Sentence Transformers** - State-of-the-art text embeddings  
✅ **LangGraph Orchestration** - Structured state management with 3 focused nodes  
✅ **Configurable Threshold** - Adjustable similarity threshold via environment variables  
✅ **Comprehensive Logging** - All operations logged to logs/similar_cases.log  
✅ **Singleton Pattern** - Efficient resource management (model + DB connection)  
✅ **FastAPI Integration** - RESTful API endpoints with health checks  

---

## Project Structure

```
similar_cases/
├── tools/                      # External connectors
│   ├── mongodb_connector.py    # MongoDB Atlas connection & vector search
│   └── embedding_model.py      # Sentence-transformers model wrapper
├── agent.py                    # Main agent class
├── graph.py                    # LangGraph workflow definition
├── nodes.py                    # 3 node functions (embed, search, format)
├── state.py                    # Pydantic state models
├── router.py                   # FastAPI routes
├── logger.py                   # Logging utility
└── README.md                   # This file
```

---

## Workflow

```
User Query → embed_query → vector_search → format_results → Output
```

### Node Details

1. **embed_query**: Converts user query text to 384-dim embedding vector
2. **vector_search**: Searches MongoDB for similar cases above threshold
3. **format_results**: Formats results with metadata and similarity scores

---

## Configuration

Add these variables to your `.env` file:

```env
# MongoDB Configuration
MONGODB_URI=mongodb://user:password@host:port/...
DATABASE_NAME=Capa
COLLECTION_NAME=Complaints

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Search Configuration
SIMILARITY_THRESHOLD=0.70
VECTOR_SEARCH_LIMIT=5000
VECTOR_INDEX_NAME=complaint_vector_index
```

---

## API Usage

### Find Similar Cases

```bash
POST /similar-cases/
Content-Type: application/json

{
  "query": "Device overheating during normal use with burn marks on casing"
}
```

### Response

```json
{
  "query": "Device overheating during normal use...",
  "similarityThreshold": 0.70,
  "similarCount": 15,
  "message": "Found 15 similar case(s) above the 70% similarity threshold.",
  "topMatches": [
    {
      "complaintId": "C-2024-001",
      "descriptionOfIssue": "Device became extremely hot...",
      "similarity": 0.8542,
      "severity": "High",
      "productFamily": "Medical Device X",
      ...
    }
  ]
}
```

### Health Check

```bash
GET /similar-cases/health
```

---

## Dependencies

- `langgraph` - Workflow orchestration
- `pymongo` - MongoDB connection
- `sentence-transformers` - Text embeddings
- `pydantic` - Data validation
- `fastapi` - API framework
- `python-dotenv` - Environment configuration

---

## MongoDB Atlas Setup

1. Create a vector search index on your collection:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "descriptionEmbedding",
      "numDimensions": 384,
      "similarity": "cosine"
    }
  ]
}
```

2. Ensure your documents have `descriptionEmbedding` field with 384-dim vectors

---

## Error Handling

- Connection failures are logged and raised as exceptions
- Empty results return structured response with `similarCount: 0`
- All errors include detailed messages for debugging

---

## Logging

All operations are logged to `Agents/logs/similar_cases.log`:

- Node execution start/end
- Embedding operations
- Vector search results
- API requests/responses
- Errors with stack traces

---

## Performance

- **Singleton pattern** ensures model and DB connection are loaded once
- **Lazy loading** defers initialization until first use
- **Batch processing** supported via multiple API calls
- **Scalable** via MongoDB Atlas vector search indexing

---

## Future Enhancements

- [ ] Multi-field embeddings (product family, severity, etc.)
- [ ] Hybrid search (vector + keyword)
- [ ] Result re-ranking
- [ ] Caching for frequent queries
- [ ] Batch search endpoint
