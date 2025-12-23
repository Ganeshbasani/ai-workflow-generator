import streamlit as st
from workflow import generate_workflow

st.set_page_config(page_title="AI Workflow Generator", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: 'Inter', sans-serif;
    background: #0f172a;
    color: #e5e7eb;
}

.app-container {
    max-width: 900px;
    margin: 40px auto;
    padding: 20px;
}

.header {
    text-align: center;
    margin-bottom: 40px;
}

.header h1 {
    font-size: 38px;
    font-weight: 700;
    margin-bottom: 10px;
}

.header p {
    font-size: 16px;
    color: #9ca3af;
}

.input-section label {
    display: block;
    font-weight: 600;
    margin-bottom: 8px;
}

.input-section textarea {
    width: 100%;
    height: 160px;
    padding: 14px;
    font-size: 15px;
    border-radius: 10px;
    border: none;
    background: #111827;
    color: #e5e7eb;
    resize: none;
}

.input-section textarea::placeholder {
    color: #6b7280;
}

.input-section button {
    margin-top: 20px;
    padding: 14px 24px;
    background: #6366f1;
    color: #fff;
    font-size: 16px;
    font-weight: 600;
    border: none;
    border-radius: 10px;
    cursor: pointer;
}

.input-section button:hover {
    background: #4f46e5;
}

.output-section {
    margin-top: 50px;
}

.output-section h2 {
    font-size: 22px;
    margin-bottom: 20px;
}

.workflow-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.workflow-card {
    display: flex;
    align-items: center;
    background: #111827;
    padding: 16px;
    border-radius: 12px;
    border-left: 5px solid #6366f1;
}

.step-number {
    font-weight: 700;
    font-size: 18px;
    color: #6366f1;
    margin-right: 14px;
}

.step-text {
    font-size: 15px;
    line-height: 1.5;
}

.footer {
    margin-top: 60px;
    text-align: center;
    font-size: 13px;
    color: #9ca3af;
}
</style>

<div class="app-container">

    <header class="header">
        <h1>AI-Driven Dynamic Workflow Generator</h1>
        <p>Convert natural language into structured workflows</p>
    </header>
""", unsafe_allow_html=True)

user_input = st.text_area(
    "Describe your process",
    placeholder="Customer registers.\nPlaces order.\nMakes payment.\nGenerate invoice.",
    height=160
)

if st.button("Generate Workflow"):
    steps = generate_workflow(user_input)

    if steps:
        st.markdown("""
        <section class="output-section">
            <h2>Generated Workflow</h2>
            <div class="workflow-list">
        """, unsafe_allow_html=True)

        for i, step in enumerate(steps, start=1):
            clean_step = step.split(":", 1)[1] if ":" in step else step
            st.markdown(f"""
                <div class="workflow-card">
                    <span class="step-number">{i}</span>
                    <span class="step-text">{clean_step}</span>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("</div></section>", unsafe_allow_html=True)

st.markdown("""
    <footer class="footer">
        Built by Basani Ganesh · AI Workflow Automation Project
    </footer>

</div>
""", unsafe_allow_html=True)
