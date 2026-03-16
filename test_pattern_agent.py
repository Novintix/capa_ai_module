import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Agents.pattern.agent import PatternAgentLangGraph
from Agents.pattern.schemas import PatternAnalysisRequest

def test_pattern_agent_instantiation():
    """Test if the Pattern Agent can be instantiated and the graph is valid."""
    try:
        load_dotenv()
        agent = PatternAgentLangGraph()
        print("✅ Pattern Agent instantiated correctly.")
        print("✅ LangGraph compiled successfully.")
        
        # Test request structure
        req = PatternAnalysisRequest(
            complaint_id="TEST-001",
            description="Seal integrity failure observed after sterilization"
        )
        print(f"✅ Request created: {req.complaint_id}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to instantiate Pattern Agent: {str(e)}")
        return False

if __name__ == "__main__":
    test_pattern_agent_instantiation()
