import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8100")
HEADERS = {"X-API-Key": os.getenv("API_KEY", "demo-key")}

st.set_page_config(page_title="Request Triage AI", page_icon="🧭", layout="wide")
st.markdown(
    """<style>
    .hero {padding:1.8rem;border-radius:20px;background:linear-gradient(120deg,#172554,#0f766e);}
    .hero h1,.hero p {color:white;margin:.2rem 0}.stButton button{border-radius:10px}
    </style><div class="hero"><h1>Request Triage AI</h1>
    <p>Local, review-first routing for professional-services requests</p></div>""",
    unsafe_allow_html=True,
)


def api(method: str, path: str, **kwargs):
    """Call the backend and surface its safe error detail to the operator."""
    response = httpx.request(method, f"{API_URL}{path}", headers=HEADERS, timeout=70, **kwargs)
    response.raise_for_status()
    return response.json()


def show_result(result: dict, location: str) -> None:
    """Render one decision with rationale, draft, warnings and audit trace."""
    st.subheader(result["summary"])
    left, middle, right = st.columns(3)
    left.metric("Category", result["category"])
    middle.metric("Priority", result["priority"])
    right.metric("Owner", result["owner"])
    st.write("**Why this priority:**", result["priority_reason"])
    st.write("**Draft first response — review before sending**")
    st.info(result["draft_response"])
    if result.get("warnings"):
        for warning in result["warnings"]:
            st.warning(warning)
    with st.expander("Decision trace and guardrails"):
        st.json({"confidence": result["confidence"], "risk_flags": result["risk_flags"],
                 "decision_source": result["decision_source"], "trace": result["trace"]})

    if result["request_id"] in st.session_state.reviewed:
        st.success("Human review already submitted for this request.")
        return
    # A result may be visible in session history and the durable queue in one Streamlit run.
    # The location prefix keeps both widget trees unique without changing the request ID.
    with st.form(f"{location}-review-{result['request_id']}"):
        outcome = st.radio("Human decision", ["approved", "corrected", "rejected"], horizontal=True)
        notes = st.text_area("Review notes (optional)")
        if st.form_submit_button("Submit review"):
            try:
                api("POST", f"/v1/triage/{result['request_id']}/review",
                    json={"outcome": outcome, "notes": notes})
                st.session_state.reviewed.add(result["request_id"])
                st.success("Review submitted successfully.")
                st.rerun()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 409:
                    st.session_state.reviewed.add(result["request_id"])
                    st.rerun()
                st.error(f"Review failed: {exc.response.json().get('detail', 'Unexpected error')}")


if "history" not in st.session_state:
    st.session_state.history = []
if "reviewed" not in st.session_state:
    st.session_state.reviewed = set()

try:
    health = api("GET", "/health/ready")
    st.sidebar.success("All local services ready")
    st.sidebar.json(health["dependencies"])
except (httpx.HTTPError, ValueError):
    st.sidebar.error("Backend is not ready. Check Docker and Ollama.")

triage_tab, queue_tab, evaluation_tab, design_tab = st.tabs(
    ["Triage", "Review queue", "Evaluation", "How it works"]
)
with triage_tab:
    mock_data = json.loads(Path("data/mock_requests.json").read_text(encoding="utf-8"))
    edge_data = json.loads(Path("data/edge_case_requests.json").read_text(encoding="utf-8"))
    examples = {"Custom request": ""} | {
        f"Request {row['id']}": row["text"] for row in mock_data
    } | {
        f"Edge case {row['id']} · {row['name']}": row["text"] for row in edge_data
    }
    selected = st.selectbox("Try a challenge scenario", examples)
    with st.form("triage-form", clear_on_submit=False):
        text = st.text_area("Client request", value=examples[selected], height=150,
                            placeholder="Paste a mock request—never real confidential client data.")
        submitted = st.form_submit_button("Analyse request", type="primary")
    if submitted:
        with st.spinner("Agents are analysing, validating policy, and drafting a response…"):
            try:
                result = api("POST", "/v1/triage", json={
                    "request_text": text, "source": "web",
                    "idempotency_key": str(uuid4()),
                })
                st.session_state.history.append(result)
            except httpx.HTTPStatusError as exc:
                st.error(exc.response.json().get("detail", "Request failed safely"))
            except httpx.HTTPError:
                st.error("The API is temporarily unavailable. Your request was not submitted.")
    for result in reversed(st.session_state.history):
        st.divider()
        show_result(result, "history")

with queue_tab:
    st.caption("Durable results from PostgreSQL; newest first.")
    if st.button("Refresh queue"):
        st.rerun()
    try:
        records = api("GET", "/v1/triage?limit=50")
        for record in records:
            with st.expander(f"{record['priority']} · {record['category']} · {record['summary']}"):
                show_result(record, "queue")
    except httpx.HTTPError:
        st.info("The queue becomes available when the API is ready.")

with evaluation_tab:
    st.subheader("Reproducible golden set")
    st.caption("All six assessment requests are checked for category, priority, and owner.")
    st.dataframe(json.loads(Path("data/evaluation.json").read_text(encoding="utf-8")),
                 use_container_width=True)
    result_path = Path("output/evaluation-results.json")
    if result_path.exists():
        report = json.loads(result_path.read_text(encoding="utf-8"))
        st.metric("Last run", f"{report['passed']} / {report['total']} passed")
        st.json(report)
    else:
        st.info("Run `docker compose exec api python scripts/evaluate.py` to create evidence.")

with design_tab:
    st.markdown("""
    **Workflow:** input validation → PII redaction → analysis agent → deterministic policy guardrails →
    response-drafting agent → PostgreSQL audit record → human review.

    **Local stack:** Ollama runs both AI roles; LangGraph makes state transitions explicit; FastAPI serves
    typed contracts; Redis enforces distributed rate limits; PostgreSQL stores decisions and reviews.

    AI output is always a draft. The system detects prompt injection, validates strict enums, repairs malformed
    JSON once, elevates security/outage cases deterministically, redacts contact/payment identifiers before
    inference, and degrades to safe templates if Ollama is unavailable.
    """)
