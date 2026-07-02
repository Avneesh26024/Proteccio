import os
import yaml

# 1. Load config once at module level
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")

try:
    with open(CONFIG_PATH, "r") as f:
        CONFIG = yaml.safe_load(f)
except FileNotFoundError:
    print(f"[WARNING] config.yaml not found at {CONFIG_PATH}. Using fallback defaults.")
    CONFIG = {}

SEVERITY_WEIGHTS = CONFIG.get("severity_weights", {})
THRESHOLDS = CONFIG.get("thresholds", {"low": 10, "medium": 30, "high": 31})

def score(detection_dict: dict) -> dict:
    """
    Calculates the risk score based on detection counts and configurable weights,
    then assigns a risk level. Mutates the dictionary in-place.
    """
    total_score = 0
    counts = detection_dict.get("_counts", {})
    
    # 2. Calculate total risk score with min(count, 5) cap
    for entity, count in counts.items():
        if count > 0 and entity in SEVERITY_WEIGHTS:
            capped_count = min(count, 5)
            total_score += (capped_count * SEVERITY_WEIGHTS[entity])
            
    detection_dict["_score"] = total_score
    
    # 3. Determine risk level
    if total_score <= THRESHOLDS.get("low", 10):
        detection_dict["_risk_level"] = "Low"
    elif total_score <= THRESHOLDS.get("medium", 30):
        detection_dict["_risk_level"] = "Medium"
    else:
        detection_dict["_risk_level"] = "High"
        
    # 4. Return updated dictionary
    return detection_dict


if __name__ == "__main__":
    print("Testing Phase 4: Risk Scorer...\n")
    
    # Case 1 - Expected: High Risk
    # Expected Score calculation (based on config): 
    # aadhaar(10) + pan(10) + credit_card(10) + email(3*2) + bank_details(9) + api_key(9) = 54
    case_1 = {
        "aadhaar": ["[Aadhaar Redacted]"],
        "pan": ["ABCDE1234F"],
        "credit_card": ["4111 1111 1111 1111"],
        "email": ["a@b.com", "c@d.com"],
        "phone": [],
        "bank_details": ["SBIN0001234"],
        "api_key": ["sk-abc123"],
        "employee_id": [],
        "_counts": {"aadhaar": 1, "pan": 1, "credit_card": 1, 
                    "email": 2, "phone": 0, "bank_details": 1, 
                    "api_key": 1, "employee_id": 0}
    }
    
    # Case 2 - Expected: Low Risk
    # Expected Score calculation: email(3*1) = 3
    case_2 = {
        "aadhaar": [],
        "pan": [],
        "credit_card": [],
        "email": ["a@b.com"],
        "phone": [],
        "bank_details": [],
        "api_key": [],
        "employee_id": [],
        "_counts": {"aadhaar": 0, "pan": 0, "credit_card": 0,
                    "email": 1, "phone": 0, "bank_details": 0,
                    "api_key": 0, "employee_id": 0}
    }
    
    result_1 = score(case_1)
    print("--- Case 1 ---")
    print(f"Score: {result_1['_score']}")
    print(f"Risk Level: {result_1['_risk_level']}\n")
    
    result_2 = score(case_2)
    print("--- Case 2 ---")
    print(f"Score: {result_2['_score']}")
    print(f"Risk Level: {result_2['_risk_level']}\n")
    
    assert result_1["_risk_level"] == "High", "Case 1 should be High Risk"
    assert result_2["_risk_level"] == "Low", "Case 2 should be Low Risk"
    
    print("Status: Tests passed!")