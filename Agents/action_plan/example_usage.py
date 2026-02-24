"""
example_usage.py

Example CAPA action plan generation from real manufacturing scenarios.
"""

import json
from Agents.action_plan.graph import build_graph
from Agents.action_plan.model import CapaInput


def example_1_contamination():
    """Example 1: Environmental contamination in sterile manufacturing"""
    
    graph = build_graph()
    
    capa_input = CapaInput(
        investigation_summary="Contamination detected in batch X-001 during water testing. Results exceeded microbial limits (>100 CFU/mL). Investigation launched immediately.",
        containment_actions="Batch quarantined. Manufacturing line shut down. Complete cleaning and sanitization performed. Environmental monitoring initiated with increased frequency.",
        five_why_analysis="""
        Why 1: How did contamination enter manufacturing? 
            A: Water storage tank lid was not properly sealed.
        Why 2: Why was the lid not properly sealed?
            A: Maintenance technician did not follow equipment lock-out procedure.
        Why 3: Why did technician not follow lock-out?
            A: Training outdated - procedure updated 6 months ago.
        Why 4: Why was training not provided?
            A: No training trigger defined for SOP updates.
        Why 5: Why is there no training trigger system?
            A: No formal process for linking document updates to training requirements.
        """,
        primary_root_cause="Lack of formal training trigger system for SOP updates",
        contributing_root_causes=[
            "Equipment lock-out SOP not followed",
            "Water storage tank monitoring insufficient"
        ],
        systemic_root_causes=[
            "No document-training linkage process",
            "Insufficient change management integration"
        ],
        evidence_collected="Water testing results, cleaning logs, maintenance records, training database review, SOP revision dates",
        root_cause_verification_status="Verified",
        severity_level="Critical",
        timeline_constraint="30 days for corrective; 90 days for preventive",
        available_resources="$150,000 budget, full staff support"
    )
    
    result = graph.invoke({
        "capa_input": capa_input.dict()
    })
    
    print("\n" + "="*120)
    print("EXAMPLE 1: Environmental Contamination - Water Storage")
    print("="*120)
    
    print(f"\nTotal Actions: {result['total_actions']}")
    print(f"Primary Actions: {result['primary_actions']}")
    print(f"Preventive/Systemic: {result['preventive_systemic_actions']}")
    print(f"Confidence: {result['confidence_score']}\n")
    
    # Print action plan table
    headers = [
        "Action Type", "Description", "Assigned To", "Due Date", "Resources",
        "Verification", "Training", "Documents", "Change Control"
    ]
    
    print(f"{'Action Type':<12} | {'Assigned To':<15} | {'Due Date':<12} | {'Verification':<25}")
    print("-"*80)
    
    for action in result["action_items"]:
        print(
            f"{action['action_type']:<12} | "
            f"{action['assigned_to']:<15} | "
            f"{action['planned_due_date']:<12} | "
            f"{action['verification_plan'][:25]:<25}"
        )
    
    print("\nNotes:", result.get("notes", "N/A"))


def example_2_out_of_spec():
    """Example 2: Out-of-specification (OOS) test results"""
    
    graph = build_graph()
    
    capa_input = CapaInput(
        investigation_summary="Product ABC batch 2026-001 failed assay specification (target 95-105%, result 87%). Root cause investigation initiated.",
        containment_actions="Release withheld pending investigation. Stability data reviewed. No material distributed to customers.",
        five_why_analysis="""
        Why 1: Why did assay fall below specification?
            A: Raw material potency was 8% below specification.
        Why 2: Why was subpotent material accepted?
            A: Supplier testing showed 98%, but independent verification lacked sensitivity.
        Why 3: Why was independent verification insufficient?
            A: Analytical method qualification incomplete - not validated for low-potency detection.
        Why 4: Why was method not fully qualified?
            A: Validation protocol did not include potency stress testing.
        Why 5: Why was stress testing omitted?
            A: R&D did not follow validation SOP - used legacy protocol from previous method.
        """,
        primary_root_cause="Insufficient analytical method validation for raw material qualification",
        contributing_root_causes=[
            "Supplier controls inadequate",
            "Legacy validation protocol used instead of current SOP"
        ],
        systemic_root_causes=[
            "Inadequate documentation of method transfer",
            "No verification of protocol updates across all functions"
        ],
        evidence_collected="Supplier test reports, in-house test data, analytical method files, validation reports, raw material lot history",
        root_cause_verification_status="Verified",
        severity_level="Major",
        timeline_constraint="45 days for corrective; 120 days for preventive",
        available_resources="$80,000 budget, R&D and Supplier Quality departments"
    )
    
    result = graph.invoke({
        "capa_input": capa_input.dict()
    })
    
    print("\n" + "="*120)
    print("EXAMPLE 2: Out-of-Specification Test Results - Analytical Method Validation")
    print("="*120)
    
    print(f"\nTotal Actions: {result['total_actions']}")
    print(f"Primary Actions: {result['primary_actions']}")
    print(f"Preventive/Systemic: {result['preventive_systemic_actions']}")
    print(f"Confidence: {result['confidence_score']}\n")
    
    print(f"{'Action Type':<12} | {'Assigned To':<15} | {'Due Date':<12} | {'Change Control':<15}")
    print("-"*60)
    
    for action in result["action_items"]:
        print(
            f"{action['action_type']:<12} | "
            f"{action['assigned_to']:<15} | "
            f"{action['planned_due_date']:<12} | "
            f"{action['change_control_reference']:<15}"
        )
    
    print("\nNotes:", result.get("notes", "N/A"))


def example_3_equipment_failure():
    """Example 3: Equipment failure leading to process deviation"""
    
    graph = build_graph()
    
    capa_input = CapaInput(
        investigation_summary="Tablet press stopped unexpectedly during production run. 500 tablets produced before stoppage were discarded. Investigation revealed bearing failure.",
        containment_actions="Equipment removed from service. All produced tablets destroyed per quality hold. Preventive maintenance audit performed on all six presses.",
        five_why_analysis="""
        Why 1: Why did bearing fail?
            A: Lubrication frequency insufficient for operating conditions.
        Why 2: Why was lubrication interval inadequate?
            A: Maintenance schedule based on manufacturer recommended intervals, not actual equipment usage.
        Why 3: Why was actual usage not considered?
            A: Equipment utilization increased 150% over past 18 months, but maintenance schedule not updated.
        Why 4: Why was schedule not updated?
            A: No trigger for maintenance review when equipment usage changes.
        Why 5: Why is there no usage-trigger process?
            A: Maintenance planning system is manual with no change notification system.
        """,
        primary_root_cause="Inadequate predictive/preventive maintenance program not linked to equipment utilization changes",
        contributing_root_causes=[
            "Manual maintenance scheduling without automation",
            "Insufficient equipment monitoring"
        ],
        systemic_root_causes=[
            "No integrated ERP/CMMS system",
            "Missing linkage between production capacity changes and maintenance planning"
        ],
        evidence_collected="Maintenance logs, bearing analysis report, equipment usage data (18-month history), manufacturer specifications, production schedule data",
        root_cause_verification_status="Verified",
        severity_level="Critical",
        timeline_constraint="60 days for corrective; 180 days for preventive/systemic",
        available_resources="$250,000 budget, can include CMMS implementation"
    )
    
    result = graph.invoke({
        "capa_input": capa_input.dict()
    })
    
    print("\n" + "="*120)
    print("EXAMPLE 3: Equipment Failure - Preventive Maintenance")
    print("="*120)
    
    print(f"\nTotal Actions: {result['total_actions']}")
    print(f"Primary Actions: {result['primary_actions']}")
    print(f"Preventive/Systemic: {result['preventive_systemic_actions']}")
    print(f"Confidence: {result['confidence_score']}\n")
    
    print(f"{'Type':<12} | {'Assigned':<15} | {'Due Date':<12} | {'Training':<10} | {'Doc Update':<15}")
    print("-"*70)
    
    for action in result["action_items"]:
        print(
            f"{action['action_type']:<12} | "
            f"{action['assigned_to']:<15} | "
            f"{action['planned_due_date']:<12} | "
            f"{action['training_requirements'][:10]:<10} | "
            f"{action['document_updates_required'][:15]:<15}"
        )
    
    print("\nNotes:", result.get("notes", "N/A"))


if __name__ == "__main__":
    print("\n" + "="*120)
    print("CAPA ACTION PLAN AGENT - EXAMPLES")
    print("="*120)
    
    try:
        example_1_contamination()
    except Exception as e:
        print(f"\nExample 1 Error: {e}")
    
    try:
        example_2_out_of_spec()
    except Exception as e:
        print(f"\nExample 2 Error: {e}")
    
    try:
        example_3_equipment_failure()
    except Exception as e:
        print(f"\nExample 3 Error: {e}")
    
    print("\n" + "="*120)
    print("Examples completed")
    print("="*120 + "\n")
