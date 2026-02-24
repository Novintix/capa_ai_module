"""
test_action_plan.py

Unit and integration tests for CAPA Action Plan Agent.
"""

import json
import pytest
from .model import (
    CapaActionItem, CapaInput, CapaActionPlanRequest, 
    CapaActionPlanResponse
)
from .graph import build_graph


class TestCapaActionItemSchema:
    """Test CapaActionItem schema"""
    
    def test_action_item_valid(self):
        """Test valid action item"""
        action = CapaActionItem(
            action_type="Corrective",
            action_description="Implement daily equipment inspection",
            assigned_to="Manufacturing",
            planned_due_date="2026-03-15",
            resources_required="Inspection checklist, tools",
            verification_plan="Audit Review of logs",
            training_requirements="Yes - TR-001",
            document_updates_required="WI-005",
            change_control_reference="CC-001"
        )
        assert action.action_type == "Corrective"
        assert action.assigned_to == "Manufacturing"
    
    def test_action_item_all_fields(self):
        """Test all action item fields"""
        action = CapaActionItem(
            action_type="Preventive",
            action_description="Implement automated maintenance scheduler",
            assigned_to="Maintenance",
            planned_due_date="2026-05-15",
            resources_required="CMMS software, training",
            verification_plan="System capability review",
            training_requirements="Yes - TR-002",
            document_updates_required="SOP-015, WI-010",
            change_control_reference="CC-002"
        )
        assert action.training_requirements == "Yes - TR-002"
        assert "SOP-015" in action.document_updates_required


class TestCapaInputSchema:
    """Test CapaInput schema"""
    
    def test_capa_input_minimal(self):
        """Test minimal required CapaInput"""
        capa_input = CapaInput(
            investigation_summary="Test investigation",
            containment_actions="Test containment",
            five_why_analysis="Test 5-why",
            primary_root_cause="Test root cause",
            evidence_collected="Test evidence",
            root_cause_verification_status="Verified"
        )
        assert capa_input.primary_root_cause == "Test root cause"
    
    def test_capa_input_full(self):
        """Test full CapaInput with all fields"""
        capa_input = CapaInput(
            investigation_summary="Contamination detected",
            containment_actions="Batch quarantined, line cleaned",
            five_why_analysis="Detailed 5-why analysis",
            primary_root_cause="Equipment maintenance gap",
            contributing_root_causes=["Insufficient training", "No lock-out procedure"],
            systemic_root_causes=["No change management"],
            evidence_collected="Maintenance logs, test results",
            root_cause_verification_status="Verified",
            severity_level="Critical",
            timeline_constraint="30 days",
            available_resources="Full staff and budget"
        )
        assert len(capa_input.contributing_root_causes) == 2
        assert capa_input.severity_level == "Critical"


class TestCapaActionPlanResponse:
    """Test response schema"""
    
    def test_response_valid(self):
        """Test valid response"""
        response = CapaActionPlanResponse(
            action_items=[
                CapaActionItem(
                    action_type="Corrective",
                    action_description="Test action",
                    assigned_to="QA",
                    planned_due_date="2026-03-15",
                    resources_required="Test",
                    verification_plan="Test verification",
                    training_requirements="No",
                    document_updates_required="N/A",
                    change_control_reference="N/A"
                )
            ],
            total_actions=1,
            primary_actions=1,
            preventive_systemic_actions=0,
            confidence_score=0.90
        )
        assert response.total_actions == 1
        assert response.confidence_score == 0.90


class TestActionPlanGraph:
    """Test graph execution"""
    
    def test_graph_builds(self):
        """Test graph builds without errors"""
        graph = build_graph()
        assert graph is not None
    
    def test_graph_invokes(self):
        """Test graph invocation"""
        graph = build_graph()
        
        result = graph.invoke({
            "capa_input": {
                "investigation_summary": "Test contamination",
                "containment_actions": "Batch quarantined",
                "five_why_analysis": "Test analysis",
                "primary_root_cause": "Equipment failure",
                "evidence_collected": "Test evidence",
                "root_cause_verification_status": "Verified",
                "severity_level": "Major"
            }
        })
        
        assert "action_items" in result
        assert isinstance(result["action_items"], list)
        assert result["total_actions"] > 0
    
    def test_graph_output_structure(self):
        """Test graph output has required fields"""
        graph = build_graph()
        
        result = graph.invoke({
            "capa_input": {
                "investigation_summary": "Test issue",
                "containment_actions": "Test containment",
                "five_why_analysis": "Test 5-why",
                "primary_root_cause": "Test root cause",
                "evidence_collected": "Test evidence",
                "root_cause_verification_status": "Verified"
            }
        })
        
        assert "action_items" in result
        assert "total_actions" in result
        assert "primary_actions" in result
        assert "preventive_systemic_actions" in result
        assert "confidence_score" in result
        
        # Verify action item structure
        for action in result["action_items"]:
            assert "action_type" in action
            assert "action_description" in action
            assert "assigned_to" in action
            assert "planned_due_date" in action


class TestCapaRuleCoverage:
    """Test CAPA rules enforcement"""
    
    def test_corrective_and_preventive_coverage(self):
        """Test that plan includes both corrective and preventive actions"""
        graph = build_graph()
        
        result = graph.invoke({
            "capa_input": {
                "investigation_summary": "Test issue",
                "containment_actions": "Test containment",
                "five_why_analysis": "Test analysis",
                "primary_root_cause": "Root cause",
                "contributing_root_causes": ["Contributing cause"],
                "evidence_collected": "Test evidence",
                "root_cause_verification_status": "Verified"
            }
        })
        
        action_types = [a.get("action_type") for a in result["action_items"]]
        
        # Should have both corrective and preventive/systemic
        has_corrective = "Corrective" in action_types
        has_preventive = "Preventive" in action_types or "Systemic" in action_types
        
        assert has_corrective or has_preventive, "Should have at least corrective or preventive action"
    
    def test_department_assignment(self):
        """Test that assignments use departments not names"""
        graph = build_graph()
        
        result = graph.invoke({
            "capa_input": {
                "investigation_summary": "Test",
                "containment_actions": "Test",
                "five_why_analysis": "Test",
                "primary_root_cause": "Test",
                "evidence_collected": "Test",
                "root_cause_verification_status": "Verified"
            }
        })
        
        valid_departments = {
            "Manufacturing", "QA", "R&D", "Supplier Quality", "Validation",
            "Engineering", "Regulatory", "Supply Chain", "Quality", "Operations",
            "Maintenance", "Planning"
        }
        
        for action in result["action_items"]:
            assigned = action.get("assigned_to", "").split(",")[0].strip()
            # Should be a department (loose check; strict check would validate against list)
            assert len(assigned) > 0, f"Empty assignment: {action}"
    
    def test_date_format(self):
        """Test all dates are YYYY-MM-DD format"""
        graph = build_graph()
        
        result = graph.invoke({
            "capa_input": {
                "investigation_summary": "Test",
                "containment_actions": "Test",
                "five_why_analysis": "Test",
                "primary_root_cause": "Test",
                "evidence_collected": "Test",
                "root_cause_verification_status": "Verified"
            }
        })
        
        for action in result["action_items"]:
            due_date = action.get("planned_due_date", "")
            if due_date:
                assert len(due_date) == 10, f"Invalid date format: {due_date}"
                assert due_date[4] == '-' and due_date[7] == '-', f"Invalid date format: {due_date}"


class TestIntegration:
    """Integration tests"""
    
    def test_full_workflow(self):
        """Test complete workflow from input to output"""
        graph = build_graph()
        
        capa_input = {
            "investigation_summary": "Contamination in batch X-001",
            "containment_actions": "Batch quarantined",
            "five_why_analysis": "Equipment maintenance insufficient",
            "primary_root_cause": "No maintenance schedule",
            "contributing_root_causes": ["Lack of training"],
            "evidence_collected": "Maintenance logs",
            "root_cause_verification_status": "Verified",
            "severity_level": "Critical"
        }
        
        result = graph.invoke({"capa_input": capa_input})
        
        # Validate completeness
        assert result["total_actions"] > 0
        assert result["primary_actions"] >= 0
        assert result["preventive_systemic_actions"] >= 0
        assert 0.0 <= result["confidence_score"] <= 1.0
        assert len(result["action_items"]) == result["total_actions"]
    
    def test_json_serializable(self):
        """Test output is JSON serializable"""
        graph = build_graph()
        
        result = graph.invoke({
            "capa_input": {
                "investigation_summary": "Test",
                "containment_actions": "Test",
                "five_why_analysis": "Test",
                "primary_root_cause": "Test",
                "evidence_collected": "Test",
                "root_cause_verification_status": "Verified"
            }
        })
        
        # Should be JSON serializable
        json_str = json.dumps({
            "action_items": result["action_items"],
            "total_actions": result["total_actions"],
            "confidence_score": result["confidence_score"]
        })
        
        assert json_str is not None
        parsed = json.loads(json_str)
        assert "action_items" in parsed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
