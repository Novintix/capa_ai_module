"""
Verification script for Occurrence Agent with Enhanced History.
Includes the 10 specific occurrence parameters in the similar cases history.
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_enhanced_occurrence():
    # 1. Define the complaint
    complaint = {
        "complaint_id": "C-NEW-9001",
        "product": "Infusion Pump X",
        "description": "Battery overheating during charging. 3rd occurrence in 6 months.",
        "source": "Hospital",
        "date": "2026-02-18",
    }

    # 2. Define Similar Cases with ENHANCED History (The 10 keys)
    similar_cases = [
        {
            "case_id": "CAPA-201",
            "similarity_score": 0.93,
            "issue": "Battery overheating when connected to charger",
            "date": "2024-01-10",
            # This is the new section requested
            "occurrence_factors": {
                "Historical Frequency of Events": "High frequency in 2024, 5 events reported.",
                "Trend Analysis / Pattern Recognition": "Increasing trend observed in Q1 2024.",
                "Process Stability / Cp-Cpk Variability": "Process unstable, Cpk < 1.0 during that period.",
                "Effectiveness of Preventive Controls": "Controls were ineffective; issue passed through.",
                "Effectiveness of Detection / Monitoring": "Detection failed at final QC.",
                "Systemic vs Isolated Issue": "Systemic issue with batch B-77.",
                "Operator / Equipment Factors": "No operator error; Equipment calibration was valid.",
                "CAPA / Past Corrective Actions Effectiveness": "Previous CAPA (CAPA-199) was ineffective.",
                "Supplier / External Factors": "Supplier admitted to insulation defect.",
                "Audit / Compliance Findings": "Major non-conformance cited in 2024 internal audit."
            }
        },
        {
            "case_id": "CAPA-202",
            "similarity_score": 0.90,
            "issue": "Battery temperature alarm",
            "date": "2024-06-05",
            "occurrence_factors": {
                "Historical Frequency of Events": "Moderate frequency, sporadic events.",
                "Trend Analysis / Pattern Recognition": "Flat trend, no sudden spikes.",
                "Process Stability / Cp-Cpk Variability": "Stable process, Cpk > 1.33.",
                "Effectiveness of Preventive Controls": "Preventive maintenance schedule was adhered to.",
                "Effectiveness of Detection / Monitoring": "Detected by field engineer, not manufacturing.",
                "Systemic vs Isolated Issue": "Isolated to specific firmware version.",
                "Operator / Equipment Factors": "Firmware logic error, not equipment.",
                "CAPA / Past Corrective Actions Effectiveness": "Patch deployed, but effectiveness pending long-term.",
                "Supplier / External Factors": "Internal software issue, no supplier factor.",
                "Audit / Compliance Findings": "No specific findings related to this."
            }
        }
    ]

    # 3. Construct Payload
    # Note: similar_cases must be a JSON string for the Form data
    payload = {
        "complaint_id": complaint["complaint_id"],
        "description": complaint["description"],
        "source": complaint["source"],
        "date": complaint["date"],
        "product": complaint["product"],
        "similar_cases_json": json.dumps(similar_cases),
        "additional_context": "Critical medical device. Battery safety is top priority."
    }

    print("\n=== POST /occurrence/analyze (Enhanced History) ===")
    start_time = time.time()
    
    try:
        resp = requests.post(f"{BASE_URL}/occurrence/analyze", data=payload, timeout=120)
        duration = time.time() - start_time
        
        print(f"Status: {resp.status_code}")
        print(f"Time: {duration:.2f}s")
        
        if resp.status_code == 200:
            result = resp.json()
            print("\n=== RESULT ===")
            print(json.dumps(result, indent=2))
            
            # Validation
            ws = result.get("weighted_score")
            print(f"\nWeighted Score: {ws}")
            if isinstance(ws, float):
                print("[PASS] Score is a float")
            else:
                print("[FAIL] Score is NOT a float")
                
        else:
            print("Error Response:")
            print(resp.text)
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_enhanced_occurrence()
