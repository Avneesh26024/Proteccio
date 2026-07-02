import re


def detect(text: str) -> dict:
    """Scan input text with regular expressions to identify standard PII.

    Each detected entity is returned as a list of span dictionaries::

        {"value": <matched_string>, "start": <int>, "end": <int>}

    The ``_counts`` key contains the number of **unique string values** per
    entity type (not the raw match count) so that the downstream risk scorer
    behaviour is unchanged.

    Returns:
        A dict with one key per entity type (list of span dicts) plus a
        ``_counts`` dict with unique-value counts per entity type.
    """

    # Initialize the base structure
    detection_dict = {
        "aadhaar":     [],
        "pan":         [],
        "email":       [],
        "phone":       [],
        "credit_card": [],
        "bank_details": [],
        "api_key":     [],
        "employee_id": [],
        "_counts": {
            "aadhaar": 0, "pan": 0, "email": 0, "phone": 0,
            "credit_card": 0, "bank_details": 0, "api_key": 0, "employee_id": 0
        }
    }

    # Define regex patterns
    patterns = {
        "aadhaar":     r"(?<![\d -])\d{4}[- ]?\d{4}[- ]?\d{4}(?![- ]?\d)",
        "pan":         r"\b[A-Z]{5}\d{4}[A-Z]\b",
        "email":       r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "phone":       r"\b(?:\+91[- ]?|0)?[6-9]\d{9}\b",
        "credit_card": r"\b(?:\d{4}[- ]?){3}\d{4}\b",
        "ifsc":        r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
        # Matches specific prefixes OR any 32+ char alphanumeric string
        "api_key":     r"\b(?:sk-|pk-|api_|key_|token_)[A-Z0-9]{20,}\b|\b[A-Z0-9]{32,}\b",
        "employee_id": r"\b[A-Z]{2,4}-?\d{3,6}\b",
    }

    # -------------------------------------------------------------------------
    # 1. Standard extraction via finditer — returns span dicts
    # -------------------------------------------------------------------------
    for entity in ["aadhaar", "pan", "email", "phone", "credit_card", "api_key", "employee_id"]:
        seen_values: set[str] = set()
        spans: list[dict] = []

        for match in re.finditer(patterns[entity], text, flags=re.IGNORECASE):
            value = match.group().strip()
            spans.append({"value": value, "start": match.start(), "end": match.end()})
            seen_values.add(value)

        detection_dict[entity] = spans
        # _counts = number of UNIQUE string values (not raw match count)
        detection_dict["_counts"][entity] = len(seen_values)

    # -------------------------------------------------------------------------
    # 2. Bank details extraction (IFSC + contextual account numbers)
    # -------------------------------------------------------------------------
    bank_spans: list[dict] = []
    seen_bank_values: set[str] = set()

    # Extract IFSC codes
    for match in re.finditer(patterns["ifsc"], text, flags=re.IGNORECASE):
        value = match.group().strip().upper()
        bank_spans.append({"value": value, "start": match.start(), "end": match.end()})
        seen_bank_values.add(value)

    # Extract account numbers using a 50-character context window
    acc_pattern = r"\b\d{9,18}\b"
    context_keywords = ["account", "a/c", "acc", "bank"]

    for match in re.finditer(acc_pattern, text):
        acc_no = match.group().strip()
        start_ctx = max(0, match.start() - 50)
        end_ctx   = min(len(text), match.end() + 50)
        context_window = text[start_ctx:end_ctx].lower()

        if any(keyword in context_window for keyword in context_keywords):
            bank_spans.append({"value": acc_no, "start": match.start(), "end": match.end()})
            seen_bank_values.add(acc_no)

    detection_dict["bank_details"] = bank_spans
    detection_dict["_counts"]["bank_details"] = len(seen_bank_values)

    return detection_dict


if __name__ == "__main__":
    print("Testing Regex Detector (span-dict output)...\n")

    # REMINDER: Replace '[Aadhaar Redacted]' with a real 12-digit number to
    # exercise the Aadhaar pattern locally.
    sample = """
    Contact: john.doe@example.com, phone: +91-9876543210
    Aadhaar: [Aadhaar Redacted], PAN: ABCDE1234F
    Credit Card: 4111 1111 1111 1111
    Bank account no: 123456789012, IFSC: SBIN0001234
    API Key: sk-abc123def456ghi789jkl012mno345pqr
    Employee ID: EMP-001
    """

    results = detect(sample)

    import json
    print("Extraction Results:")
    print(json.dumps(results, indent=2))

    # ------------------------------------------------------------------
    # Assertions — verify new span-dict shape and backward-compat counts
    # ------------------------------------------------------------------
    print("\nRunning Assertions...")

    # Shape: every non-metadata value must be a list of dicts
    for key, val in results.items():
        if key.startswith("_"):
            continue
        assert isinstance(val, list), f"{key} should be a list"
        for item in val:
            assert isinstance(item, dict),               f"{key}: item should be a dict, got {type(item)}"
            assert "value" in item,                      f"{key}: missing 'value' key"
            assert "start" in item,                      f"{key}: missing 'start' key"
            assert "end"   in item,                      f"{key}: missing 'end' key"
            assert isinstance(item["start"], int),       f"{key}: 'start' should be int"
            assert isinstance(item["end"],   int),       f"{key}: 'end' should be int"
            assert item["start"] < item["end"],          f"{key}: start must be < end"

    # _counts still reflects unique string values (risk scorer compat)
    assert results["_counts"]["email"]       == 1, "Failed email count"
    assert results["_counts"]["phone"]       == 1, "Failed phone count"
    assert results["_counts"]["pan"]         == 1, "Failed PAN count"
    assert results["_counts"]["credit_card"] == 1, "Failed credit card count"
    assert results["_counts"]["bank_details"] == 2, \
        "Failed bank details count (1 account no + 1 IFSC)"
    assert results["_counts"]["api_key"]      == 1, "Failed API key count"
    assert results["_counts"]["employee_id"]  == 1, "Failed employee ID count"

    # Spot-check a value and its span
    email_spans = results["email"]
    assert len(email_spans) == 1
    assert email_spans[0]["value"].lower() == "john.doe@example.com"
    assert email_spans[0]["start"] < email_spans[0]["end"]

    # To test Aadhaar locally, insert your 12 digits in the sample string and
    # uncomment the line below:
    # assert results["_counts"]["aadhaar"] == 1, "Failed Aadhaar count"

    print("Status: All active assertions passed successfully!")