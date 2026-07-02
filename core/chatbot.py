import os
from core.providers.base import LLMProvider
from core import audit_logger

# Stop-words filtered out during keyword extraction for chunk retrieval
_STOP_WORDS = {
    "what", "is", "the", "in", "document", "a", "an", "of", "to",
    "and", "or", "are", "there", "any", "how", "many", "was", "were",
    "this", "that", "it", "its", "for", "with", "about", "can", "do",
    "does", "did", "has", "have", "had", "be", "been", "being",
}


class Chatbot:
    def __init__(self, result: dict, report: dict, provider: LLMProvider):
        self.result   = result
        self.report   = report
        self.provider = provider
        self.history  = []

        # Build context string safely
        detections = result.get("detections", {})
        counts     = detections.get("_counts", {})

        counts_str = "\n".join([f"- {k}: {v}" for k, v in counts.items() if v > 0])

        # Extract plain string values from span-dicts for display
        detected_vals = []
        for k, v in detections.items():
            if k.startswith("_") or not isinstance(v, list) or not v:
                continue
            # Each item in v is {"value": str, "start": int, "end": int}
            value_strings = [
                item["value"] if isinstance(item, dict) else str(item)
                for item in v
            ]
            if value_strings:
                detected_vals.append(f"- {k}: {', '.join(value_strings)}")
        detected_vals_str = "\n".join(detected_vals)

        compliance_rep = report.get("compliance_report", "")

        self.context_string = f"""
DOCUMENT ANALYSIS CONTEXT:

File: {result.get('file_path', 'Unknown')}
Risk Level: {detections.get('_risk_level', 'Unknown')}
Risk Score: {detections.get('_score', 0)}

DETECTION SUMMARY:
{counts_str}

DETECTED VALUES (for reference):
{detected_vals_str}

COMPLIANCE REPORT SUMMARY:
{compliance_rep[:1000]}
"""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_keywords(self, question: str) -> list[str]:
        """Return meaningful words from ``question`` after stop-word removal."""
        words = question.lower().split()
        return [w.strip("?.,!") for w in words if w.strip("?.,!") not in _STOP_WORDS]

    def _retrieve_top_chunks(self, keywords: list[str], top_n: int = 3) -> list[str]:
        """Return the text of the top ``top_n`` chunks by keyword hit-count.

        Both chunk ``"text"`` and, if present, ``"masked_text"`` are searched
        so the retrieval is not dependant on whether the chunk stores raw or
        redacted content.
        """
        chunks = self.result.get("chunks", [])
        if not chunks or not keywords:
            return []

        scored: list[tuple[int, str]] = []
        for chunk in chunks:
            chunk_body = chunk.get("text", "") + " " + chunk.get("masked_text", "")
            chunk_body_lower = chunk_body.lower()
            hits = sum(1 for kw in keywords if kw in chunk_body_lower)
            if hits > 0:
                scored.append((hits, chunk.get("text", "")))

        # Sort by descending hit count, then take top_n
        scored.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in scored[:top_n]]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(self, question: str) -> str:
        q_lower = question.lower()

        # Step 1 — Statistical router
        stat_keywords = [
            "how many", "count", "number of", "total", "how much",
            "list all", "show all", "what are all",
        ]
        is_stat = any(kw in q_lower for kw in stat_keywords)

        if is_stat:
            entity_map = {
                "aadhaar":    "aadhaar",
                "pan":        "pan",
                "email":      "email",
                "phone":      "phone",
                "credit card":"credit_card",
                "credit_card":"credit_card",
                "bank":       "bank_details",
                "api key":    "api_key",
                "api_key":    "api_key",
                "employee":   "employee_id",
            }

            found_entity = None
            for kw, dict_key in entity_map.items():
                if kw in q_lower:
                    found_entity = dict_key
                    break

            detections = self.result.get("detections", {})
            counts     = detections.get("_counts", {})

            if found_entity:
                count = counts.get(found_entity, 0)
                if count == 0:
                    return f"No {found_entity} detected in the document."
                # Extract plain strings from span-dicts for display
                raw_spans = detections.get(found_entity, [])
                values = [
                    item["value"] if isinstance(item, dict) else str(item)
                    for item in raw_spans
                ]
                return f"Found {count} {found_entity} in the document: {values}"
            else:
                summary = [f"- {k}: {v}" for k, v in counts.items() if v > 0]
                if not summary:
                    return "No sensitive entities detected in the document."
                return "Here is the detection summary:\n" + "\n".join(summary)

        # Step 2 — Qualitative LLM call with pseudo-RAG chunk injection
        keywords      = self._extract_keywords(question)
        top_chunks    = self._retrieve_top_chunks(keywords, top_n=3)

        # Format retrieved excerpts for the prompt
        if top_chunks:
            excerpts_block = "\n\n".join(
                f"[Excerpt {i+1}]\n{chunk}" for i, chunk in enumerate(top_chunks)
            )
            relevant_section = f"\nRELEVANT EXCERPTS FROM THE DOCUMENT:\n{excerpts_block}\n"
        else:
            relevant_section = ""

        prompt = f"""
You are a data compliance assistant. Answer the user's question 
based only on the document context provided below.
Be concise and specific.

{self.context_string}
{relevant_section}
User Question: {question}
"""
        print("\n[DEBUG: LLM called]")

        # Audit log the chatbot query
        audit_logger.log_event("chatbot_query", {"question": question})

        response = self.provider.complete(prompt, "")

        # Update history
        self.history.append({"role": "user",      "content": question})
        self.history.append({"role": "assistant", "content": response})

        return response


def run_loop(chatbot: Chatbot) -> None:
    print("\nChatbot ready. Type 'exit' or 'quit' to quit.")
    while True:
        try:
            question = input("You: ").strip()
            if question.lower() in ["exit", "quit"]:
                print("Exiting chatbot...")
                break
            if not question:
                continue

            response = chatbot.ask(question)
            print(f"Assistant: {response}\n")

        except KeyboardInterrupt:
            print("\nExiting chatbot...")
            break


if __name__ == "__main__":
    from core.analyzer import analyze
    from core.report_generator import generate
    from core.providers.gemini import GeminiProvider

    print("Testing Phase 7: Chatbot integration...\n")

    # Create sample document
    test_file = "test_chat.txt"
    with open(test_file, "w") as f:
        f.write(
            "Contact us at support@example.com or admin@example.com. "
            "Aadhaar: [Aadhaar Redacted]. "
            "We are tracking project Titan internally."
        )

    print("Running background pipeline (Analyze → Generate)...")
    try:
        analysis = analyze(test_file)
        provider = GeminiProvider()
        report   = generate(analysis, provider)

        print("\nStarting Chatbot...")
        bot = Chatbot(analysis, report, provider)

        # Manually run the loop so you can test the questions
        run_loop(bot)

    finally:
        if os.path.exists(test_file):
            os.remove(test_file)