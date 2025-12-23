import streamlit as st
from workflow import generate_workflow

st.set_page_config(page_title="AI Workflow Generator", layout="centered")

st.markdown("""
<style>
body {
    background-color: #0f172a;
}
.container {
    max-width: 900px;
    margin: auto;
}
.title {
    text-align: center;
    font-size: 36px;
    font-weight: 700;
    color: #e5e7eb;
    margin-bottom: 10px;
}
.subtitle {
    text-align: center;
    color: #9ca3af;
    margin-bottom: 30px;
}
.card {
    background: #111827;
    padding: 16px;
    border-radius: 12px;
    margin-bottom: 12px;
    border-left: 5px solid #6366f1;
    color: #e5e7eb;
}
</style>

<div class="container">
    <div class="title">AI-Driven Dynamic Workflow Generator</div>
    <div class="subtitle">Convert natural language into structured workflows</div>
</div>
""", unsafe_allow_html=True)

user_input = st.text_area(
    "Describe your process",
    height=160,
    placeholder="Customer registers. Places order. Makes payment."
)

if st.button("Generate Workflow"):
    steps = generate_workflow(user_input)
    for step in steps:
        st.markdown(f"<div class='card'>{step}</div>", unsafe_allow_html=True)
