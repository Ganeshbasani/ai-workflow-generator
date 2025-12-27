import streamlit as st
import pandas as pd
import json
import re
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
        # Safe encoding for Latin-1 PDF standard
        safe_text = text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 8, safe_text)
        pdf.ln(2)

    # FIXED: fpdf2 returns bytes directly with dest='S'
    return pdf.output(dest='S')

def generate_mermaid_code(steps):
    mermaid_code = "graph TD\n"
    for i, step in enumerate(steps):
        label = step["step"].replace('"', "'").replace('\n', ' ')
        mermaid_code += f'    step{i}["{i+1}. {label}"]\n'
        if i > 0:
            mermaid_code += f"    step{i-1} --> step{i}\n"
    return mermaid_code

# -------------------- STYLING --------------------

st.markdown("""
<style>
    .step-card {
        background-color: #111827;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #6366f1;
        margin-bottom: 15px;
    }
    .step-header {
        font-weight: bold;
        color: #6366f1;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------- SESSION STATE --------------------

if "generated_steps" not in st.session_state:
    st.session_state.generated_steps = []

# -------------------- SIDEBAR --------------------

with st.sidebar:
    st.title("🛠️ Workflow Settings")
    uploaded_file = st.file_uploader("Upload PDF or TXT", type=["pdf", "txt"])
    user_input = st.text_area("Describe process manually", height=150)

    if st.button("⚡ Generate Workflow", use_container_width=True):
        content = ""
        if uploaded_file:
            if uploaded_file.type == "application/pdf":
                content = extract_text_from_pdf(uploaded_file)
            else:
                content = uploaded_file.read().decode("utf-8", errors="replace")
        else:
            content = user_input

        if content:
            raw_steps = generate_workflow(content)
            st.session_state.generated_steps = [{"step": s} for s in raw_steps]
        else:
            st.warning("Please provide an input first.")

    if st.button("➕ Add Manual Approval Step", use_container_width=True):
        st.session_state.generated_steps.append({"step": "Review and Approve Workflow Results"})

# -------------------- MAIN CONTENT --------------------

st.title("AI-Driven Dynamic Workflow Generator")

if st.session_state.generated_steps:
    st.subheader("Edit Your Steps")
    
    updated_steps = []
    
    # Loop through steps for editing
    for i, step_data in enumerate(st.session_state.generated_steps):
        with st.container():
            st.markdown(f"<div class='step-header'>Step {i+1}</div>", unsafe_allow_html=True)
            new_text = st.text_input(f"Description", step_data["step"], key=f"input_{i}", label_visibility="collapsed")
            
            col1, col2, col3 = st.columns([1, 1, 4])
            if col1.button("⬆️", key=f"up_{i}") and i > 0:
                st.session_state.generated_steps[i], st.session_state.generated_steps[i-1] = st.session_state.generated_steps[i-1], st.session_state.generated_steps[i]
                st.rerun()
            if col2.button("⬇️", key=f"down_{i}") and i < len(st.session_state.generated_steps) - 1:
                st.session_state.generated_steps[i], st.session_state.generated_steps[i+1] = st.session_state.generated_steps[i+1], st.session_state.generated_steps[i]
                st.rerun()
            
            updated_steps.append({"step": new_text})
            st.markdown("---")

    st.session_state.generated_steps = updated_steps

    # Approval Button
    if st.button("✅ FINAL APPROVAL", type="primary", use_container_width=True):
        st.balloons()
        st.success("Workflow Approved Successfully!")

    # -------------------- VISUALIZATION (BOTTOM) --------------------
    st.divider()
    st.subheader("📊 Visualization & Export")
    
    tab1, tab2 = st.tabs(["Diagram View", "Download Files"])
    
    with tab1:
        mermaid_code = generate_mermaid_code(st.session_state.generated_steps)
        st.markdown(f"```mermaid\n{mermaid_code}\n```")

    with tab2:
        metadata = {
            "created_by": "Ganesh Basani",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_steps": len(st.session_state.generated_steps)
        }
        
        pdf_data = create_pdf_bytes(st.session_state.generated_steps, metadata)
        
        st.download_button("Download PDF Report", pdf_data, "workflow.pdf", "application/pdf")
        
        json_data = json.dumps({"metadata": metadata, "steps": st.session_state.generated_steps}, indent=4)
        st.download_button("Download JSON", json_data, "workflow.json", "application/json")
else:
    st.info("Upload a document or type a process in the sidebar to begin.")
