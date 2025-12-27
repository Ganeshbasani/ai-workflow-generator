import streamlit as st
import pandas as pd
import json
import re  # For validation
from fpdf import FPDF
from pypdf import PdfReader
from workflow import generate_workflow
from datetime import datetime

st.set_page_config(page_title="AI Workflow Generator", layout="wide")

# -------------------- FUNCTIONS --------------------

def extract_text_from_pdf(file):
    try:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error extracting text from PDF: {e}")
        return ""

def create_pdf_bytes(steps, metadata):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "AI Generated Workflow", ln=True, align='C')
    pdf.ln(5)

    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 8, f"Created By: {metadata['created_by']}\nDate: {metadata['date']}\nTotal Steps: {metadata['total_steps']}")
    pdf.ln(5)

    pdf.set_font("Arial", size=12)
    for i, step in enumerate(steps, start=1):
        text = f"{i}. {step['step']}"
        safe = text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(180, 8, safe)
        pdf.ln(2)

    # FIX: pdf.output('S') returns bytes in fpdf2; no need for .encode('latin-1')
    return pdf.output(dest='S')

def generate_mermaid_code(steps):
    mermaid_code = "graph TD\n"
    for i, step in enumerate(steps):
        label = step["step"].replace('"', "'").replace('\n', ' ').replace('`', "'").replace('{', '').replace('}', '')
        mermaid_code += f'    step{i}["{i+1}. {label}"]\n'
        if i > 0:
            mermaid_code += f"    step{i-1} --> step{i}\n"
    return mermaid_code

# -------------------- UI CONFIG --------------------

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
}

.subtitle {
    margin-top: 10px;
    color: #9ca3af;
}

.section-title {
    margin-top: 40px;
    font-size: 20px;
    font-weight: 600;
}

.step {
    background: linear-gradient(145deg, #020617, #111827);
    border-radius: 12px;
    padding: 14px 18px;
    border-left: 4px solid #6366f1;
    margin-top: 12px;
}

.step-no {
    font-weight: 700;
    margin-bottom: 6px;
}

.footer {
    margin-top: 60px;
    padding: 20px;
    font-size: 13px;
    color: #9ca3af;
    border-top: 1px solid #1f2937;
    text-align: center;
}
</style>

<div class="container">
    <div class="title">AI-Driven Dynamic Workflow Generator</div>
    <div class="subtitle">Convert natural language or documents into structured workflows</div>
</div>
""", unsafe_allow_html=True)

# -------------------- SESSION STATE --------------------

if "generated_steps" not in st.session_state:
    st.session_state.generated_steps = []

if "history" not in st.session_state:
    st.session_state.history = []

# -------------------- SIDEBAR --------------------

with st.sidebar:
    st.title("🛠️ Workflow Settings")
    st.selectbox("Quick Start Templates", ["Custom", "E-commerce Refund", "User Onboarding", "Software Bug Fix"])

    uploaded_file = st.file_uploader("Upload PDF or TXT", type=["pdf", "txt"])
    user_input = st.text_area("Describe process manually", height=140)

    if st.button("➕ Add Approval Step", use_container_width=True):
        if st.session_state.generated_steps:
            st.session_state.generated_steps.append({"step": "Review and approve the workflow"})
            st.success("Approval step added!")
        else:
            st.warning("Generate a workflow first.")

    if st.button("⚡ Generate Workflow", use_container_width=True):
        if uploaded_file:
            if uploaded_file.type == "application/pdf":
                content = extract_text_from_pdf(uploaded_file)
            else:
                try:
                    content = uploaded_file.read().decode("utf-8")
                except UnicodeDecodeError:
                    content = uploaded_file.read().decode("utf-8", errors="replace")
        else:
            content = user_input

        if content:
            steps = generate_workflow(content)
            if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
                st.error("Invalid workflow output from generate_workflow.")
            else:
                st.session_state.generated_steps = [{"step": s} for s in steps]
                st.session_state.history.append(st.session_state.generated_steps.copy())
                st.session_state.history = st.session_state.history[-3:]
        else:
            st.error("Please provide input.")

# -------------------- MAIN LAYOUT --------------------

# FIX: Changed to single column for vertical layout (steps first, then viz below)
st.markdown("<div class='section-title'>Generated Workflow</div>", unsafe_allow_html=True)

if st.session_state.generated_steps:
    updated = []
    texts = []
    move_actions = []

    for i, step in enumerate(st.session_state.generated_steps, start=1):
        st.markdown("<div class='step'>", unsafe_allow_html=True)
        st.markdown(f"<div class='step-no'>Step {i}</div>", unsafe_allow_html=True)

        text = st.text_input("Step", step["step"], key=f"step_{i}", label_visibility="collapsed")

        if text.lower() in texts:
            st.warning("⚠ Possible duplicate step detected")
        texts.append(text.lower())

        col_up, col_down = st.columns(2)
        if col_up.button("⬆ Move Up", key=f"up_{i}") and i > 1:
            move_actions.append((i-1, "up"))
        if col_down.button("⬇ Move Down", key=f"down_{i}") and i < len(st.session_state.generated_steps):
            move_actions.append((i-1, "down"))

        st.markdown("</div>", unsafe_allow_html=True)

        updated.append({"step": text})

    for idx, direction in move_actions:
        if direction == "up" and idx > 0:
            updated[idx], updated[idx-1] = updated[idx-1], updated[idx]
        elif direction == "down" and idx < len(updated) - 1:
            updated[idx], updated[idx+1] = updated[idx+1], updated[idx]

    st.session_state.generated_steps = updated

    summary = " → ".join([s["step"] for s in updated[:3]])
    st.caption(f"📌 Summary: {summary}...")

    all_text = " ".join([s["step"].lower() for s in updated])
    if not re.search(r'approv', all_text):
        st.info("ℹ No approval step detected")

    if len(updated) < 3:
        st.warning("⚠ Workflow seems too short")

    # FIX: Added approval button below steps
    if st.button("✅ Approve Workflow", use_container_width=True):
        st.success("Workflow approved! (You can extend this to save or notify.)")

# FIX: Moved visualization below steps
if st.session_state.generated_steps:
    st.markdown("<div class='section-title'>Visualization & Export</div>", unsafe_allow_html=True)
    tabs = st.tabs(["📊 Diagram View", "📥 Export Suite"])

    with tabs[0]:
        mermaid = generate_mermaid_code(st.session_state.generated_steps)  # No filtering since "enabled" is removed
        st.markdown(f"```mermaid\n{mermaid}\n```")

    with tabs[1]:
        metadata = {
            "created_by": "Ganesh Basani",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_steps": len(st.session_state.generated_steps)
        }

        pdf_bytes = create_pdf_bytes(st.session_state.generated_steps, metadata)
        st.download_button("Download PDF", pdf_bytes, "workflow.pdf", "application/pdf", use_container_width=True)

        st.download_button("Download JSON",
            json.dumps({"metadata": metadata, "workflow": st.session_state.generated_steps}, indent=4),
            "workflow.json", "application/json", use_container_width=True)

        df = pd.DataFrame(st.session_state.generated_steps)
        st.download_button("Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            "workflow.csv", "text/csv", use_container_width=True)

# -------------------- FOOTER --------------------

st.markdown("""
<div class="footer">
<b>Built by: Ganesh Basani</b><br>
AI Workflow Automation Project © 2025
</div>
""", unsafe_allow_html=True)
