import argparse
import os
import sys
from dotenv import load_dotenv

from core import analyzer
from core import report_generator
from core import chatbot
from core.providers.factory import get_provider

def main():
    # 1. Load .env
    load_dotenv()

    # 2. Parse arguments
    parser = argparse.ArgumentParser(description="Sensitive Data Detection & Compliance Assistant")
    parser.add_argument("--version", action="version", version="Sensitive Data Detector v1.0")
    parser.add_argument("--file", required=True, help="Path to the input file (pdf, txt, csv)")
    parser.add_argument("--provider", default="gemini", help="Which LLM provider to use (default: gemini)")
    parser.add_argument("--chat", action="store_true", help="After analysis, start interactive chatbot loop")
    parser.add_argument("--no-save", action="store_true", help="Skip saving report files to outputs/")
    
    args = parser.parse_args()

    # File validation
    if not os.path.exists(args.file):
        print(f"Error: File not found at '{args.file}'")
        sys.exit(1)

    # 3. Initialize provider
    try:
        provider = get_provider(args.provider)
    except NotImplementedError as ne:
        print(f"Error: {ne}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error initializing provider: {e}")
        sys.exit(1)

    print(f"Analyzing {os.path.basename(args.file)}...")

    # 4 & 5. Run Analyzer
    try:
        result = analyzer.analyze(args.file)
    except ValueError as ve:
        # Clean user-facing errors
        print(f"\nError: {ve}")
        sys.exit(1)
    except Exception as e:
        # Generic exceptions
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

    # 6. Print detection summary
    detections = result.get("detections", {})
    risk_level = detections.get("_risk_level", "Unknown")
    score = detections.get("_score", 0)
    counts = detections.get("_counts", {})

    emoji_map = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}
    risk_emoji = emoji_map.get(risk_level, "")

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("ANALYSIS COMPLETE")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"File: {args.file}")
    print(f"Risk Level: {risk_emoji} {risk_level}")
    print(f"Risk Score: {score}")
    print("DETECTIONS:")
    
    found_any = False
    for k, v in counts.items():
        if v > 0:
            print(f"  {k}: {v}")
            found_any = True
            
    if not found_any:
        print("  (No sensitive data detected)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 7. Generate compliance report
    print("\nGenerating compliance report...")
    try:
        report = report_generator.generate(result, provider)
    except Exception as e:
        print(f"\nUnexpected error generating report: {e}")
        sys.exit(1)

    # 8. Print compliance report
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("COMPLIANCE REPORT")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(report.get("compliance_report", "No report generated."))
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 9. Save files unless skipped
    if not args.no_save:
        try:
            paths = report_generator.save(report)
            print("\nReports saved:")
            print(f"  → {paths['report_path']}")
            print(f"  → {paths['masked_path']}")
        except Exception as e:
            print(f"\nUnexpected error saving reports: {e}")
            sys.exit(1)

    # 10. Run chatbot if flag is passed
    if args.chat:
        print("\nStarting chatbot. Type 'exit' to quit.")
        try:
            bot = chatbot.Chatbot(result, report, provider)
            chatbot.run_loop(bot)
        except Exception as e:
            print(f"\nUnexpected error in chatbot: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()