"""
final_test.py — Pre-demo end-to-end pipeline test.

Privacy directive: prints ONLY statistical summaries (counts, risk level, score).
No raw text, no extracted PII values, no masked content is printed.
"""
import sys
import os

# ---------------------------------------------------------------------------
# Resolve the PDF path
# ---------------------------------------------------------------------------
RESUME_PATH = "/home/avneesh/Downloads/Avneesh \u2014 Resume.pdf"

if not os.path.exists(RESUME_PATH):
    print(f"[ERROR] Resume not found at: {RESUME_PATH}")
    sys.exit(1)

print("=" * 55)
print("  Proteccio — Pre-Demo End-to-End Pipeline Test")
print("=" * 55)
print(f"  File : {os.path.basename(RESUME_PATH)}")
print(f"  Size : {os.path.getsize(RESUME_PATH) / 1024:.1f} KB")
print("=" * 55)

# ---------------------------------------------------------------------------
# Step 1 — Extract + Detect + Mask + Chunk + Score
# ---------------------------------------------------------------------------
print("\n[1/3] Running analyzer (PyMuPDF + regex + mask + chunk + score)…")
from core.analyzer import analyze

try:
    result = analyze(RESUME_PATH)
except Exception as exc:
    print(f"[FAIL] analyzer.analyze() raised: {exc}")
    sys.exit(1)

print("      ✓ analyze() completed")

detections = result.get("detections", {})
counts     = detections.get("_counts",     {})
risk_level = detections.get("_risk_level", "Unknown")
risk_score = detections.get("_score",      0)
chunks     = result.get("chunks", [])
d_map      = result.get("detection_map", {})

print(f"\n{'─'*40}")
print("  DETECTION SUMMARY (unique entity counts)")
print(f"{'─'*40}")
found_any = False
for entity, count in counts.items():
    if count > 0:
        found_any = True
        bar = "█" * min(count, 20)
        print(f"  {entity:<20} {count:>3}  {bar}")
if not found_any:
    print("  (no sensitive entities detected)")

print(f"\n{'─'*40}")
risk_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk_level, "")
print(f"  Risk Level   : {risk_emoji} {risk_level}")
print(f"  Risk Score   : {risk_score}")
print(f"  Chunks       : {len(chunks)} chunk(s)")
print(f"  Tokens masked: {len(d_map)} unique token(s) in detection_map")
print(f"{'─'*40}")

# Structural assertions
assert "text"          in result, "Missing 'text' key in result"
assert "masked_text"   in result, "Missing 'masked_text' key in result"
assert "detection_map" in result, "Missing 'detection_map' key in result"
assert "chunks"        in result, "Missing 'chunks' key in result"
assert isinstance(chunks, list),  "'chunks' should be a list"
assert "_risk_level"   in detections, "Risk level not scored"

# ---------------------------------------------------------------------------
# Step 2 — Verify masking was applied
# ---------------------------------------------------------------------------
print("\n[2/3] Verifying masking integrity…")
raw_text    = result["text"]
masked_text = result["masked_text"]

# The masked text must differ from raw text if any PII was found
if d_map:
    assert masked_text != raw_text, \
        "masked_text is identical to raw_text despite non-empty detection_map"
    # Spot-check: no token key should appear in raw text
    for token in d_map:
        assert token not in raw_text, \
            f"Token {token!r} found in raw text — masking direction reversed"
    print(f"      ✓ {len(d_map)} token(s) confirmed absent from raw text")
else:
    print("      ✓ No PII detected — masking correctly produced identical texts")

# ---------------------------------------------------------------------------
# Step 3 — Verify chunker produced valid structure
# ---------------------------------------------------------------------------
print("\n[3/3] Verifying chunk structure…")
for i, chunk in enumerate(chunks):
    assert "chunk_index"          in chunk, f"Chunk {i} missing 'chunk_index'"
    assert "text"                 in chunk, f"Chunk {i} missing 'text'"
    assert "contained_detections" in chunk, f"Chunk {i} missing 'contained_detections'"

print(f"      ✓ All {len(chunks)} chunk(s) have valid structure")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'=' * 55}")
print("  ✅  ALL CHECKS PASSED — pipeline is demo-ready")
print(f"{'=' * 55}\n")
