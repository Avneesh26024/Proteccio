import os
import tempfile
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # In cloud environments (like Streamlit Cloud), environment variables/secrets are natively injected

from core import analyzer, report_generator
from core.chatbot import Chatbot
from core.providers.factory import get_provider
from core.extractors import router

# ---------------------------------------------------------------------------
# 1. Setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Proteccio — Sensitive Data Detector",
    page_icon="🔍",
    layout="wide",
)

# Initialize LLM Provider once
try:
    provider = get_provider("groq")
except Exception as e:
    st.error(f"Failed to initialize AI Provider: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# 2. Session State Initialization
# ---------------------------------------------------------------------------
defaults = {
    "analysis_done": False,
    "result":        None,
    "report":        None,
    "chatbot":       None,
    "chat_history":  [],
    "text_preview":  None,
    "tmp_file_path": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset_session():
    """Wipe all state and clean up any lingering temp file."""
    tmp = st.session_state.get("tmp_file_path")
    if tmp and os.path.exists(tmp):
        os.remove(tmp)
    for key, val in defaults.items():
        st.session_state[key] = val
    st.rerun()


# ---------------------------------------------------------------------------
# 3. Header
# ---------------------------------------------------------------------------
st.title("🔍 Sensitive Data Detection & Compliance Assistant")
st.markdown(
    "Upload a document to detect sensitive information, assess compliance risk, "
    "and interactively ask questions — all with zero raw PII sent to the LLM."
)
st.divider()

col1, col2 = st.columns([4, 6])

# ===========================================================================
# LEFT COLUMN — Upload & Two-Step Extraction Flow
# ===========================================================================
with col1:
    st.header("1. Document Upload")

    # -----------------------------------------------------------------------
    # PHASE A: Not yet analyzed
    # -----------------------------------------------------------------------
    if not st.session_state.analysis_done:

        uploaded_file = st.file_uploader(
            "Upload Document", type=["pdf", "txt", "csv"]
        )

        if uploaded_file:
            st.info(f"📄 {uploaded_file.name} — {uploaded_file.size / 1024:.1f} KB")

        # -------------------------------------------------------------------
        # Step 1: Quick Preview Extraction
        # -------------------------------------------------------------------
        if st.button(
            "1. Preview Extraction",
            disabled=not uploaded_file,
            type="secondary",
            help="Runs a fast lightweight extraction so you can verify the text quality.",
        ):
            # Save to a persistent temp file (NOT deleted in finally — kept for Step 2)
            ext = os.path.splitext(uploaded_file.name)[1]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            tmp.write(uploaded_file.getvalue())
            tmp.close()

            # Clean up any previous temp file before storing the new one
            prev = st.session_state.tmp_file_path
            if prev and os.path.exists(prev):
                os.remove(prev)

            st.session_state.tmp_file_path = tmp.name
            st.session_state.text_preview  = None  # reset on new upload

            try:
                with st.spinner("Running quick extraction…"):
                    preview_result = router.route(tmp.name)
                st.session_state.text_preview = preview_result.get("text", "")
            except Exception as e:
                st.error(f"Extraction failed: {e}")

            st.rerun()

        # -------------------------------------------------------------------
        # Step 2: Show preview + Full Analysis button
        # -------------------------------------------------------------------
        if st.session_state.text_preview is not None:

            with st.expander("👀 View Extraction Preview", expanded=True):
                st.text_area(
                    "Extracted Text (first 1000 chars)",
                    value=st.session_state.text_preview[:1000],
                    height=200,
                    disabled=True,
                    label_visibility="collapsed",
                )

            if st.button(
                "2. Run Full Analysis ✨",
                type="primary",
                help="Runs the full PII detection, masking, scoring, and LLM compliance report.",
            ):
                tmp_path = st.session_state.tmp_file_path
                try:
                    with st.spinner(
                        "Running full compliance analysis (this may take a minute)…"
                    ):
                        result = analyzer.analyze(
                            tmp_path, ocr_provider=None
                        )

                    with st.spinner("Generating LLM compliance report…"):
                        report = report_generator.generate(result, provider)

                    bot = Chatbot(result, report, provider)

                    st.session_state.result        = result
                    st.session_state.report        = report
                    st.session_state.chatbot       = bot
                    st.session_state.analysis_done = True
                    # Keep tmp_file_path alive (reset_session handles cleanup)
                    st.rerun()

                except ValueError as ve:
                    st.error(f"❌ {ve}")
                except Exception as e:
                    st.error(f"❌ Unexpected error: {e}")

    # -----------------------------------------------------------------------
    # PHASE B: Analysis complete — show results summary in left column
    # -----------------------------------------------------------------------
    if st.session_state.analysis_done:
        st.button("🔄 Analyze Another Document", on_click=reset_session)

        result     = st.session_state.result
        report     = st.session_state.report
        detections = result.get("detections", {})
        counts     = detections.get("_counts", {})
        risk_level = detections.get("_risk_level", "Unknown")
        risk_score = detections.get("_score", 0)

        st.subheader("Risk Summary")
        if risk_level == "High":
            st.error(f"### 🔴 {risk_level} Risk")
        elif risk_level == "Medium":
            st.warning(f"### 🟡 {risk_level} Risk")
        else:
            st.success(f"### 🟢 {risk_level} Risk")

        st.metric("Risk Score", risk_score)
        st.divider()

        st.subheader("Detections Found")
        found_any   = False
        metric_cols = st.columns(2)
        col_idx     = 0

        for entity, count in counts.items():
            if count > 0:
                found_any = True
                label = entity.replace("_", " ").title()
                metric_cols[col_idx % 2].metric(label, count)
                col_idx += 1

        if not found_any:
            st.info("No sensitive data detected.")

        st.divider()
        st.subheader("Downloads")

        counts_str = "\n".join([f"- {k}: {v}" for k, v in counts.items() if v > 0])
        report_txt = (
            "SENSITIVE DATA DETECTION REPORT\n================================\n"
            f"Risk Level: {risk_level}\nRisk Score: {risk_score}\n\n"
            f"DETECTION COUNTS:\n{counts_str}\n\n"
            f"================================\nCOMPLIANCE REPORT:\n"
            f"{report['compliance_report']}"
        )
        masked_txt = (
            "MASKED DOCUMENT\n================================\n"
            "Note: All detected sensitive data has been redacted.\n"
            f"================================\n\n{report['masked_text']}"
        )

        st.download_button(
            "📄 Download Compliance Report",
            data=report_txt,
            file_name="report.txt",
            mime="text/plain",
        )
        st.download_button(
            "🔒 Download Masked Document",
            data=masked_txt,
            file_name="masked_document.txt",
            mime="text/plain",
        )

# ===========================================================================
# RIGHT COLUMN — Three Tabs
# ===========================================================================
with col2:
    st.header("2. Analysis & Interactive QA")
    tab1, tab2, tab3 = st.tabs(
        ["📋 Compliance Report", "⚖️ Document Diff", "💬 Ask Questions"]
    )

    # -----------------------------------------------------------------------
    # TAB 1: Compliance Report
    # -----------------------------------------------------------------------
    with tab1:
        if not st.session_state.analysis_done:
            st.info("Upload and analyze a document to see the report here.")
        else:
            st.info("✅ This analysis has been securely logged to `outputs/audit_log.jsonl`.")

            rpt        = st.session_state.report
            detections = st.session_state.result.get("detections", {})

            st.markdown(f"**Risk Level:** `{rpt['risk_level']}`")
            st.markdown(rpt["compliance_report"])
            st.divider()

            with st.expander("🔍 View Detected Values"):
                has_values = False
                for entity, spans in detections.items():
                    if entity.startswith("_") or not isinstance(spans, list) or not spans:
                        continue
                    has_values = True
                    st.markdown(f"**{entity.replace('_', ' ').title()}**")
                    for item in spans:
                        # Handle both span-dicts and plain strings
                        display_val = item["value"] if isinstance(item, dict) else str(item)
                        st.code(display_val, language="text")
                if not has_values:
                    st.write("No values to display.")

            with st.expander("📄 View Masked Document"):
                st.text_area(
                    "Redacted Content",
                    value=rpt["masked_text"],
                    height=300,
                    disabled=True,
                )

    # -----------------------------------------------------------------------
    # TAB 2: Document Diff (NEW)
    # -----------------------------------------------------------------------
    with tab2:
        if not st.session_state.analysis_done:
            st.info("Upload and analyze a document to see the diff view here.")
        else:
            st.markdown(
                "Compare the **original document** with the **redacted version** "
                "that was sent to the LLM — zero raw PII leaves the system."
            )
            st.divider()

            diff_left, diff_right = st.columns(2)

            with diff_left:
                st.subheader("Original Text")
                st.text_area(
                    "Raw",
                    value=st.session_state.result["text"],
                    height=500,
                    disabled=True,
                    label_visibility="collapsed",
                )

            with diff_right:
                st.subheader("Masked Text")
                st.text_area(
                    "Redacted",
                    value=st.session_state.result["masked_text"],
                    height=500,
                    disabled=True,
                    label_visibility="collapsed",
                )
                st.caption(
                    "🔒 This is **exactly** what was sent to the LLM — no raw PII included."
                )

    # -----------------------------------------------------------------------
    # TAB 3: Chatbot (unchanged logic)
    # -----------------------------------------------------------------------
    with tab3:
        if not st.session_state.analysis_done:
            st.info("Upload and analyze a document first to use the Chatbot.")
        else:
            chat_container = st.container(height=400)
            with chat_container:
                for msg in st.session_state.chat_history:
                    st.chat_message(msg["role"]).write(msg["content"])

            st.markdown("**Suggested Questions:**")
            sc1, sc2, sc3, sc4 = st.columns(4)
            q1 = sc1.button("Sensitive data?")
            q2 = sc2.button("How many emails?")
            q3 = sc3.button("Main risks?")
            q4 = sc4.button("Summarize doc")

            prompt = st.chat_input("Ask about the document…")

            active_prompt = None
            if prompt:   active_prompt = prompt
            elif q1:     active_prompt = "What sensitive data was found?"
            elif q2:     active_prompt = "How many emails are present?"
            elif q3:     active_prompt = "What are the main compliance risks?"
            elif q4:     active_prompt = "Summarize this document"

            if active_prompt:
                st.session_state.chat_history.append(
                    {"role": "user", "content": active_prompt}
                )
                with st.spinner("Thinking…"):
                    response = st.session_state.chatbot.ask(active_prompt)
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": response}
                )
                st.rerun()