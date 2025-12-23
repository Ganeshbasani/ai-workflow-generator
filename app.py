import streamlit as st
from workflow import generate_workflow

st.set_page_config(page_title="AI Workflow Generator", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

body {
    font-family: 'Inter', sans-serif;
    background: radial-gradient(circle at top, #1f2933, #020617);
    color: #e5e7eb;
}

.container {
    max-width: 820px;
    margin: auto;
    padding: 40px 20px;
}

.title {
    font-size: 42px;
    font-weight: 700;
    line-height: 1.2;
}

.subtitle {
    margin-top: 10px;
    color: #9ca3af;
    font-size: 16px;
}

.input-card {
    margin-top: 30px;
    background: linear-gradient(145deg, #111827, #020617);
    padding: 22px;
    border-radius: 14px;
    box-shadow: 0 0 30px rgba(99,102,241,0.12);
}

textarea {
    width: 100%;
    height: 140px;
    background: #020617;
    color: #e5e7eb;
    border-radius: 10px;
    border: 1px solid #1f2937;
    padding: 14px;
    font-size: 15px;
}

.generate-btn {
    margin-top: 16px;
    padding: 12px 18px;
    font-weight: 600;
    border-radius: 10px;
    border: none;
    cursor: pointer;
    color: white;
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
}

.section-title {
    margin-top: 40px;
    font-size: 20px;
    font-weight: 600;
}

.step {
    display: flex;
    align-items: center;
    margin-top: 14px;
    background: linear-gradient(145deg, #020617, #111827);
    border-radius: 12px;
    padding: 14px 18px;
    border-left: 4px solid #6366f1;
}

.step-no {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: #6366f1;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 700;
    margin-right: 14px;
}

.footer {
    margin-top: 40px;
    font-size: 13px;
    color: #9ca3af;
}
</style>

<div class="container">
    <div class="title">AI-Driven Dynamic Workflow Generator</div>
    <div class="subtitle">Convert natural language into structured workflows</div>
</div>
""", unsafe_allow_html=True)

user_input = st.text_area(
    "Describe your process",
    placeholder="Customer registers.\nPlaces order.\nMakes payment.\nGenerate invoice.",
    height=140
)

if st.button("⚡ Generate Workflow"):
    steps = generate_workflow(user_input)

    if steps:
        st.markdown("<div class='section-title'>Generated Workflow</div>", unsafe_allow_html=True)

        for i, step in enumerate(steps, start=1):
            clean = step.split(":", 1)[1] if ":" in step else step
            st.markdown(f"""
            <div class="step">
                <div class="step-no">{i}</div>
                <div>{clean}</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("""
<div class="footer">
Built by Basani Ganesh · AI Workflow Automation Project
</div>
""", unsafe_allow_html=True)
