import streamlit as st

st.title("AlphaCorp AI Newspaper Delivery Agent")
st.caption(
    "Stay informed — get a plain English summary of the most important "
    "news from the last 2 days."
)

st.divider()

col_topic, col_search, col_sources = st.columns(3)

with col_topic:
    st.markdown("#### Pick a Topic")
    st.markdown(
        "Select **Tech**, **Economics**, or **Politics**, "
        "or leave it blank for a general news digest."
    )

with col_search:
    st.markdown("#### AI-Powered Search")
    st.markdown(
        "The agent uses Tavily to search the web for the latest stories "
        "and synthesises a concise summary in plain English."
    )

with col_sources:
    st.markdown("#### Cited Sources")
    st.markdown(
        "Every summary comes with up to 5 HTTPS source links "
        "so you can read the full stories."
    )

st.divider()
st.page_link("pages/news.py", label="Get today's news", icon=":material/arrow_forward:")
