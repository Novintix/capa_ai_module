import sys
import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Dict, Any, List

from .compiler import build_dynamic_graph

router = APIRouter()

def _now():
    return datetime.datetime.now().isoformat()

@router.websocket("/events/{thread_id}")
async def dynamic_event_stream(websocket: WebSocket, thread_id: str):
    """
    100% n8n-style WebSocket endpoint.
    Expects input like: 
    {
      "command": "start",
      "raw_input": "...",
      "graph": {
        "nodes": [{"id": ..., "data": {"id": "A1_similar_cases_agent"}}],
        "edges": [{"source": "...", "target": "..."}]
      }
    }
    """
    await websocket.accept()
    print(f"WS (Dynamic Builder) connected: {thread_id}")
    
    try:
        while True:
            msg = await websocket.receive_json()
            cmd = msg.get("command")
            
            if cmd == "start":
                raw_input = msg.get("raw_input", "")
                graph_data = msg.get("graph", {"nodes": [], "edges": []})
                
                await websocket.send_json({"type": "status", "status": "started"})
                
                # 1. Compile exactly what UI sent
                try:
                    workflow = build_dynamic_graph(graph_data["nodes"], graph_data["edges"])
                    if not workflow:
                        await websocket.send_json({"type": "error", "message": "No valid nodes provided in graph blueprint."})
                        continue
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": f"Graph Compilation Logic Error: {e}"})
                    continue
                
                # 2. Execute that custom graph dynamically!
                try:
                    config = {"configurable": {"thread_id": thread_id}}
                    
                    # Because we aren't passing Checkpointer to this mock, we just use astream simply.
                    async for event in workflow.astream_events({"raw_input": raw_input, "results": {}}, version="v2"):
                        kind = event["event"]
                        name = event["name"]   # This is the actual React Flow node 'id' string!
                        metadata = event.get("metadata", {})
                        
                        # In our dynamic graph, the node names match the React Flow unique IDs exactly!
                        is_node = (metadata.get("langgraph_node") == name and name != "__start__")
                        
                        if kind == "on_chain_start" and name == "LangGraph":
                            await websocket.send_json({"type": "graph_start"})
                        elif kind == "on_chain_start" and is_node:
                            # 'name' is the React Flow node ID, not just "A1"
                            await websocket.send_json({"type": "node_start", "node_id": name, "timestamp": _now()})
                        elif kind == "on_chain_end" and is_node:
                            out = event["data"].get("output")
                            # Extract specific result
                            final_str = ""
                            if out and "results" in out:
                                final_str = list(out["results"].values())[-1]
                            
                            await websocket.send_json({"type": "node_end", "node_id": name, "data": {"summary": final_str}, "timestamp": _now()})
                        elif kind == "on_chain_end" and name == "LangGraph":
                            final_out = event["data"].get("output")
                            await websocket.send_json({"type": "completed", "data": {"results": final_out.get("results"), "message": "Custom Pipeline Finished"}})
                except Exception as exc:
                    import traceback
                    print(traceback.format_exc())
                    await websocket.send_json({"type": "error", "message": f"Graph Execution Error: {str(exc)}"})
                    
            elif cmd == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        print(f"WS disconnected: {thread_id}")
    except Exception as exc:
        pass
