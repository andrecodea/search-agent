import re
from math import ceil
from pathlib import Path

import streamlit as st

HISTORY_DIR: Path = Path(__file__).parent.parent.parent / "history"
CARDS_PER_PAGE: int = 9

st.title("History")
st.caption("Past news summaries retrieved by the agent.")

# ----------------------
# |     UTILITIES      |
# ----------------------


def parse_history_file(file_path: Path) -> dict:
    """Parse a history markdown file into its frontmatter metadata and body text."""
    content = file_path.read_text(encoding="utf-8")
    parts = content.split("---\n", 2)
    frontmatter: dict[str, str] = {}
    if len(parts) >= 2:
        for line in parts[1].strip().splitlines():
            key, _, value = line.partition(": ")
            frontmatter[key.strip()] = value.strip()
    body = parts[2].strip() if len(parts) > 2 else ""
    return {
        "timestamp": frontmatter.get("timestamp", ""),
        "category": frontmatter.get("category", "general"),
        "body": body,
    }


def extract_summary_preview(body: str, max_chars: int = 120) -> str:
    """Return a short preview of the summary section, truncated to max_chars."""
    match = re.search(r"## Summary\n\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if not match:
        return ""
    text = match.group(1).strip()
    return text[:max_chars] + "..." if len(text) > max_chars else text


def extract_sources(body: str) -> list[str]:
    """Return all HTTPS URLs from the sources section of the body."""
    match = re.search(r"## Sources\n\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if not match:
        return []
    return re.findall(r"https://\S+", match.group(1))


def format_timestamp(iso_timestamp: str) -> str:
    """Convert an ISO timestamp to a human-readable display string."""
    return iso_timestamp[:19].replace("T", " ") + " UTC"


# ----------------------
# |     SESSION        |
# ----------------------

if "history_page" not in st.session_state:
    st.session_state.history_page = 0
if "selected_history_file" not in st.session_state:
    st.session_state.selected_history_file = None

# ----------------------
# |      GRID          |
# ----------------------

if not HISTORY_DIR.exists() or not list(HISTORY_DIR.glob("*.md")):
    st.info("No history yet. Run a news query on the News page to see results here.")
    st.stop()

history_files: list[Path] = sorted(HISTORY_DIR.glob("*.md"), reverse=True)
total_pages: int = ceil(len(history_files) / CARDS_PER_PAGE)
current_page: int = min(st.session_state.history_page, total_pages - 1)
page_files: list[Path] = history_files[current_page * CARDS_PER_PAGE : (current_page + 1) * CARDS_PER_PAGE]

grid_columns = st.columns(3)
for card_index, file_path in enumerate(page_files):
    entry = parse_history_file(file_path)
    preview = extract_summary_preview(entry["body"])
    timestamp_display = format_timestamp(entry["timestamp"])

    with grid_columns[card_index % 3]:
        with st.container(border=True):
            st.caption(f"📅 {timestamp_display}  🏷 {entry['category'].capitalize()}")
            st.markdown(preview)
            if st.button("View", key=f"view_{file_path.name}"):
                st.session_state.selected_history_file = file_path.name
                st.rerun()

st.divider()

# ----------------------
# |    PAGINATION      |
# ----------------------

col_prev, col_info, col_next = st.columns([1, 2, 1])
with col_prev:
    if st.button("← Prev", disabled=current_page == 0):
        st.session_state.history_page -= 1
        st.rerun()
with col_info:
    st.caption(f"Page {current_page + 1} of {total_pages}")
with col_next:
    if st.button("Next →", disabled=current_page == total_pages - 1):
        st.session_state.history_page += 1
        st.rerun()

# ----------------------
# |    SELECTED        |
# ----------------------

if st.session_state.selected_history_file:
    selected_path = HISTORY_DIR / st.session_state.selected_history_file
    if selected_path.exists():
        entry = parse_history_file(selected_path)
        sources = extract_sources(entry["body"])

        st.divider()
        st.subheader(
            f"{entry['category'].capitalize()} — {format_timestamp(entry['timestamp'])}"
        )

        summary_match = re.search(r"## Summary\n\n(.*?)(?=\n## |\Z)", entry["body"], re.DOTALL)
        if summary_match:
            st.markdown(summary_match.group(1).strip())

        if sources:
            st.subheader("Sources")
            for source_url in sources:
                st.link_button(source_url, source_url, icon=":material/open_in_new:")
