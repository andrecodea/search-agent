"""
AlphaCorp AI Newspaper Delivery Agent — Streamlit frontend.

Pages:
  - Home:    product overview and quick-start link
  - News:    query the agent by category
  - History: paginated card grid of past summaries
"""

import streamlit as st
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


def main() -> None:
    """Configure the page and register the navigation structure."""
    st.set_page_config(
        page_title="AlphaCorp AI Newspaper Agent",
        page_icon=":material/newspaper:",
        layout="wide",
    )

    pages = [
        st.Page("pages/home.py", title="Home", icon=":material/home:"),
        st.Page("pages/news.py", title="News", icon=":material/newspaper:"),
        st.Page("pages/history.py", title="History", icon=":material/history:"),
    ]

    page = st.navigation(pages)
    page.run()

    st.sidebar.caption(
        "Built with [LangChain](https://langchain.com) + [Tavily](https://tavily.com). "
        "Powered by [OpenRouter](https://openrouter.ai)."
    )


if __name__ == "__main__":
    main()
