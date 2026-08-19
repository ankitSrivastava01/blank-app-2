import streamlit as st

st.set_page_config(page_title="Google Search", layout="centered")

# Purple styling
st.markdown(
    """
    <style>
    * {
        color: purple;
    }
    .stTextInput > label {
        color: purple;
        font-weight: bold;
    }
    .stButton > button {
        color: white;
        background-color: purple;
        border-radius: 5px;
    }
    h1, h2, h3 {
        color: purple;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🔍 Google Search")

query = st.text_input("Search Google:", placeholder="Enter your search query...")

if query:
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    st.markdown(f"[🔗 Click here to search Google]({search_url})", unsafe_allow_html=True)
    st.write(f"Searching for: **{query}**")

st.markdown("---")
st.write("Simple Google search app with purple theme")
