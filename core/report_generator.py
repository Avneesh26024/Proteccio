import os
import yaml
from core.providers.base import LLMProvider
from core import audit_logger

# Load config at module level
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
try:
    with open(CONFIG_PATH, "r") as f:
        CONFIG = yaml.safe_load(f)
except Exception:
    CONFIG = {"llm_settings": {"max_chars_for_llm": 50000}}

MAX_CHARS = CONFIG.get("llm_settings", {}).get("max_chars_for_llm", 50000)

def generate(result: dict, provider: LLMProvider) -> dict:
    """Generate a compliance report using pre-masked text from the analyzer.

    ``masked_text`` is sourced directly from ``result`` (produced by
    :func:`core.analyzer.analyze`) so no masking logic lives here.
    """
    
    # 1. Pull pre-computed values from the analyzer result
    detections  = result.get("detections", {})
    masked_text = result.get("masked_text", result.get("text", ""))

    # 2. Build prompt — send masked text so no raw PII reaches the LLM
    prompt = f"""
You are a data compliance expert. Analyze the following document 
and its detected sensitive data summary.

DETECTION SUMMARY:
- Risk Level: {detections.get('_risk_level', 'N/A')}
- Risk Score: {detections.get('_score', 0)}
- Detections: {detections.get('_counts', {})}

DOCUMENT TEXT (redacted, truncated if large):
{masked_text[:MAX_CHARS]}

Generate a structured report with exactly these three sections:
1. Compliance Observations
2. Security Risks
3. Suggested Remediation Steps

Be specific and reference the actual detected entity types found.
"""

    # 3. Audit-log what we are about to send to the LLM
    audit_logger.log_event(
        "llm_compliance_report_generation",
        {"masked_text_sent": masked_text[:500] + "..."},
    )

    # 4. Call LLM
    compliance_report = provider.complete(prompt, "")

    return {
        "risk_level":        detections.get("_risk_level", "Low"),
        "score":             detections.get("_score", 0),
        "counts":            detections.get("_counts", {}),
        "compliance_report": compliance_report,
        "masked_text":       masked_text,
    }

def save(report: dict, output_dir: str = "outputs") -> dict:
    """Writes reports to files."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    report_path = os.path.join(output_dir, "report.txt")
    masked_path = os.path.join(output_dir, "masked_document.txt")
    
    # Format counts
    counts_str = "\n".join([f"- {k}: {v}" for k, v in report['counts'].items() if v > 0])
    
    # Write report
    with open(report_path, "w") as f:
        f.write(f"SENSITIVE DATA DETECTION REPORT\n================================\n")
        f.write(f"Risk Level: {report['risk_level']}\n")
        f.write(f"Risk Score: {report['score']}\n\n")
        f.write(f"DETECTION COUNTS:\n{counts_str}\n\n")
        f.write(f"================================\nCOMPLIANCE REPORT:\n{report['compliance_report']}")
        
    # Write masked doc
    with open(masked_path, "w") as f:
        f.write(f"MASKED DOCUMENT\n================================\n")
        f.write(f"Note: All detected sensitive data has been redacted.\n")
        f.write(f"================================\n\n{report['masked_text']}")
        
    return {"report_path": report_path, "masked_path": masked_path}


if __name__ == "__main__":
    from core.analyzer import analyze
    from core.providers.gemini import GeminiProvider
    
    print("Testing Phase 6: Report Generator...")
    
    # 1. Analyze a dummy file
    test_file = "test_gen.txt"
    with open(test_file, "w") as f:
        f.write("Contact: john@example.com. PAN: ABCDE1234F.")
        
    analysis = analyze(test_file)
    
    # 2. Generate Report
    provider = GeminiProvider()
    report_data = generate(analysis, provider)
    
    # 3. Save Report
    paths = save(report_data)
    
    print(f"\nFiles saved at: {paths}")
    print("\n--- First 500 chars of report.txt ---")
    with open(paths['report_path'], 'r') as f:
        print(f.read(500))
        
    print("\n--- Verify Redaction in masked_document.txt ---")
    with open(paths['masked_path'], 'r') as f:
        print(f.read())
        
    os.remove(test_file)