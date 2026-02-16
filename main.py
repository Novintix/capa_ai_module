"""
Main Entry Point
Detection Score Agent
"""

from dotenv import load_dotenv
from detection.agent import DetectionAgentLangGraph
from detection.schemas import ComplaintData

# Load environment variables
load_dotenv()


def main():
    """Main function to demonstrate agent usage."""
    
    # Initialize agent
    print("Initializing Detection Agent...")
    agent = DetectionAgentLangGraph()
    
    # Example complaint
    complaint = ComplaintData(
        complaint_id="C-001",
        source="Service Report",
        description="Seal integrity failure observed after sterilization"
    )
    
    # Process complaint
    print(f"\nProcessing complaint: {complaint.complaint_id}")
    result = agent.process_complaint(complaint, policy_document_path=None)
    
    print(f"\nDetection Score: {result['detection_score']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Decision Source: {result['decision_source']}")
    print(f"Explanation: {result['explanation']}")


if __name__ == "__main__":
    main()
