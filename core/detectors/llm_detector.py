import json
from core.providers.factory import get_provider

# Maximum characters sent to the LLM to prevent context overflow
_MAX_CHARS = 20_000

# Prompt template — instructs the LLM to return strictly valid JSON
_PROMPT_TEMPLATE = """\
You are a senior data security analyst performing a probabilistic PII and \
confidential-information scan.

Analyze the document text below and identify ONLY the following two categories \
of risk that cannot be caught by simple pattern matching:

1. **Confidential Business Information** — unreleased product/project code names, \
internal financial metrics, merger/acquisition hints, strategy terms, or any phrase \
indicating the document is classified (e.g. "Company Confidential", "Do not share").

2. **Ambiguous Sensitive Numbers** — short numeric strings (4–8 digits) that could \
plausibly be a PIN, password, OTP, or internal access code based on surrounding \
context (e.g. "vault PIN is 4928", "passcode: 8821").

OUTPUT RULES (strictly follow these — violations will break the system):
- Output ONLY a valid JSON array. No markdown, no backticks, no prose.
- If nothing is found, output an empty array: []
- Each element must match this exact schema:
  {{"value": "<exact substring found>", "type": "<Confidential Business Info | Ambiguous Number>", "confidence": "<High | Medium | Low>", "reason": "<one sentence>"}}

DOCUMENT TEXT:
{text}
"""


def detect(text: str, provider=None) -> dict:
    """Scan text for probabilistic PII risks using an LLM.

    Handles two categories that regex cannot reliably catch:

    * **Confidential Business Information** — code names, internal metrics,
      classification markings (e.g. "Company Confidential").
    * **Ambiguous Sensitive Numbers** — short numeric strings whose surrounding
      context suggests a PIN, OTP, or access code.

    Args:
        text: The document text to analyse.  Truncated to 20,000 characters
            internally to keep token usage bounded.
        provider: An :class:`core.providers.base.LLMProvider` instance.
            If ``None``, a default ``GeminiProvider`` is instantiated
            automatically.

    Returns:
        ``{"potential_flags": list[dict]}`` where each dict contains
        ``value``, ``type``, ``confidence``, and ``reason`` keys.
        Returns ``{"potential_flags": []}`` on any parsing failure so the
        upstream pipeline is never blocked.
    """
    # ------------------------------------------------------------------
    # Lazy provider instantiation
    # ------------------------------------------------------------------
    if provider is None:
        provider = get_provider("gemini")

    # ------------------------------------------------------------------
    # Truncate to keep token usage predictable
    # ------------------------------------------------------------------
    truncated_text = text[:_MAX_CHARS]

    # ------------------------------------------------------------------
    # Build prompt
    # ------------------------------------------------------------------
    prompt = _PROMPT_TEMPLATE.format(text=truncated_text)

    # ------------------------------------------------------------------
    # Call LLM (text is already embedded in prompt; pass "" as 2nd arg)
    # ------------------------------------------------------------------
    response = provider.complete(prompt, "")

    # ------------------------------------------------------------------
    # Parse JSON response — strip markdown fences just in case the LLM
    # ignores the "no backticks" instruction
    # ------------------------------------------------------------------
    try:
        cleaned = response.strip()

        # Strip ```json ... ``` or ``` ... ``` wrappers
        if cleaned.startswith("```"):
            # Remove the opening fence (with optional language tag)
            cleaned = cleaned.split("\n", 1)[-1]
            # Remove the closing fence
            if cleaned.endswith("```"):
                cleaned = cleaned[: cleaned.rfind("```")]

        cleaned = cleaned.strip()
        parsed = json.loads(cleaned)

        # Validate: must be a list
        if not isinstance(parsed, list):
            raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")

        return {"potential_flags": parsed}

    except Exception as exc:
        # Silent debug warning — never crash the upstream pipeline
        print(f"[llm_detector] JSON parse failed ({type(exc).__name__}: {exc}). "
              f"Returning empty flags. Raw response (first 300 chars): "
              f"{response[:300]!r}")
        return {"potential_flags": []}


if __name__ == "__main__":
    print("=== LLM Detector Smoke Test ===\n")

    test_text = (
        "Meeting notes: Project Titan is delayed. "
        "The vault PIN might be 4928. "
        "Do not share this outside the company."
    )

    print(f"Input text:\n  {test_text}\n")
    print("Calling detect()…")

    result = detect(test_text)

    print("\nResult:")
    print(json.dumps(result, indent=2))

    # Basic structural assertions
    assert "potential_flags" in result, "Missing 'potential_flags' key"
    assert isinstance(result["potential_flags"], list), "potential_flags must be a list"

    for flag in result["potential_flags"]:
        assert "value"      in flag, f"Flag missing 'value': {flag}"
        assert "type"       in flag, f"Flag missing 'type': {flag}"
        assert "confidence" in flag, f"Flag missing 'confidence': {flag}"
        assert "reason"     in flag, f"Flag missing 'reason': {flag}"
        assert flag["confidence"] in {"High", "Medium", "Low"}, \
            f"Invalid confidence value: {flag['confidence']}"

    print(f"\n✓ {len(result['potential_flags'])} flag(s) returned — all assertions passed.")
