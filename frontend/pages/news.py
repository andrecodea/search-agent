import os
from datetime import datetime

import httpx
import streamlit as st

API_URL: str = os.getenv("API_URL", "http://localhost:8000/news")

st.title("News")
st.caption("Search any topic and optionally filter by category. The agent covers the last 2 days.")

# ----------------------
# |     UTILITIES      |
# ----------------------


_UTC_OFFSET_MINUTES: int = int(
    (datetime.now().astimezone().utcoffset().total_seconds()) / 60
)


def call_api(category: str | None, topic: str | None) -> dict:
    """POST to the news endpoint and return the parsed JSON response."""
    payload: dict = {"utc_offset_minutes": _UTC_OFFSET_MINUTES}
    if category:
        payload["category"] = category
    if topic:
        payload["topic"] = topic
    response = httpx.post(API_URL, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


# ----------------------
# |      INPUT         |
# ----------------------

topic_input: str = st.text_input(
    "Topic",
    placeholder="e.g. artificial intelligence, inflation, elections…",
)
topic_value: str | None = topic_input.strip() or None

CATEGORY_OPTIONS: list[str] = ["General", "Tech", "Economics", "Politics"]

selected_category: str = st.selectbox("Category (optional)", options=CATEGORY_OPTIONS, index=0)
category_value: str | None = None if selected_category == "General" else selected_category.lower()

run_button = st.button("Get News", type="primary", icon=":material/newspaper:")

st.divider()

# ----------------------
# |     SESSION        |
# ----------------------

if "summary" not in st.session_state:
    st.session_state.summary = ""
    st.session_state.sources = []

# ----------------------
# |     RESULTS        |
# ----------------------

if run_button:
    st.session_state.summary = ""
    st.session_state.sources = []
    with st.spinner("Searching for the latest news..."):
        try:
            data = call_api(category_value, topic_value)
            st.session_state.summary = data.get("summary", "")
            st.session_state.sources = data.get("sources", [])
        except httpx.ConnectError:
            st.error(f"Could not reach the backend at {API_URL}. Is the server running?")
        except httpx.TimeoutException:
            st.error("Request timed out (120s). The agent may be overloaded — try again.")
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail", exc.response.text)
            except Exception:
                detail = exc.response.text
            st.error(f"Server error {exc.response.status_code}: {detail}")
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")

if st.session_state.summary:
    st.subheader("Summary")
    st.markdown(st.session_state.summary)

    if st.session_state.sources:
        st.subheader("Sources")
        for source_url in st.session_state.sources:
            st.link_button(source_url, source_url, icon=":material/open_in_new:")
