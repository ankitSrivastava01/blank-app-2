import streamlit as st

from stock_explorer import render_app

st.set_page_config(page_title="India & US Stock Explorer", page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #081a2d 0%, #102c43 42%, #0b2e2a 100%);
        color: #edf7ff;
    }
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .panel {
        background: rgba(9, 23, 36, 0.8);
        border: 1px solid rgba(84, 200, 191, 0.35);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
    }
    .hero {
        background: linear-gradient(135deg, rgba(9, 65, 90, 0.9), rgba(6, 117, 107, 0.85));
        border: 1px solid rgba(121, 216, 194, 0.5);
        border-radius: 18px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 1rem;
    }
    .badge {
        display: inline-block;
        background: rgba(83, 187, 177, 0.16);
        color: #d9fffb;
        border: 1px solid rgba(113, 220, 206, 0.45);
        border-radius: 999px;
        padding: 0.28rem 0.7rem;
        font-size: 0.8rem;
        margin-bottom: 0.7rem;
    }
    .metric-box {
        background: rgba(8, 25, 36, 0.9);
        border: 1px solid rgba(98, 168, 200, 0.4);
        border-radius: 14px;
        padding: 0.8rem 0.9rem;
    }
    div[data-testid="stMetric"] {
        background: rgba(8, 25, 36, 0.9);
        border: 1px solid rgba(98, 168, 200, 0.4);
        border-radius: 14px;
        padding: 0.8rem;
    }
    .stButton > button {
        background: linear-gradient(135deg, #0d7f84, #17a29a);
        color: #edf7ff;
        border: none;
        border-radius: 10px;
        font-weight: 600;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #0ca1a1, #24c9b8);
    }
    .stSelectbox > div,
    .stTextInput > div,
    .stNumberInput > div,
    .stMultiSelect > div {
        background: rgba(5, 18, 27, 0.8);
        border: 1px solid rgba(98, 168, 200, 0.35);
        color: #edf7ff;
    }
    .stDataFrame, .stTable {
        background: rgba(3, 16, 24, 0.7);
        color: #edf7ff;
    }
    [data-testid="stSidebar"] {
        background-color: #102c43;
        color: #edf7ff;
    }
    h1, h2, h3 {
        color: #d9fffb;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {
        color: #b9cede;
    }
    [data-testid="stMarkdownContainer"] a {
        color: #79e2d5;
    }
    input::placeholder {
        color: #b9cede;
        opacity: 1;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


render_app()
