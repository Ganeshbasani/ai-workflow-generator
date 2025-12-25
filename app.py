import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
from pypdf import PdfReader
# Ensure you have a file named workflow.py with generate_workflow function
from workflow import generate_workflow 

# --- FUNCTIONS FOR NEW FEATURES ---
def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def create_pdf_bytes(steps):
    # FIXED: Explicitly set orientation, units, and format
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="AI Generated Workflow", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    
    for i, step in enumerate(steps, start=1):
        # FIXED: Sanitize text to handle special characters that Arial/Latin-1 doesn't support
        safe_step = step.encode('latin-1', 'replace').decode('latin-1')
        # FIXED: Changed 0 to 180 (fixed width) to prevent "Not enough horizontal space" error
        pdf.multi_cell(180, 10, txt=f"{i}. {safe_step}")
        pdf.ln(2)
        
    return pdf.output(dest='S').encode('latin-1')

def generate_mermaid_code(steps):
    """Converts a list of steps into Mermaid.js flowchart syntax."""
    mermaid_code = "graph TD\n"
    for i in range(len(steps)):
        clean_step = steps[i].replace('"', "'") 
        node_id = f"step{i}"
        mermaid_code += f'    {node_id}["{i+1}. {clean_step}"]\n'
        if i > 0:
            mermaid_code += f"    step{i-1} --> step{i}\n"
    return mermaid_code

# --- UI CONFIG & ORIGINAL DESIGN ---
st.set_page_config(page_title="AI Workflow Generator", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

body {
    font-family: 'Inter', sans-serif;
    background: radial-gradient(circle at top, #1f2933, #020617);
    color: #e5e7eb;
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
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
    animation: fadeInUp 0.4s ease-out forwards;
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

# --- SESSION STATE INITIALIZATION ---
if 'generated_steps' not in st.session_state:
    st.session_state['generated_steps'] = []

# --- INPUT SECTION ---
with st.sidebar:
    st.title("🛠️ Workflow Settings")
    template = st.selectbox("Quick Start Templates", ["Custom", "E-commerce Refund", "User Onboarding", "Software Bug Fix"])
    
    uploaded_file = st.file_uploader("Upload a Process Document (PDF or TXT)", type=["pdf", "txt"])
    user_input = st.text_area("Describe your process manually", placeholder="Customer registers...", height=140)

    if st.button("⚡ Generate Workflow", use_container_width=True):
        final_input = ""
        if uploaded_file:
            if uploaded_file.type == "application/pdf":
                final_input = extract_text_from_pdf(uploaded_file)
            else:
                final_input = str(uploaded_file.read(), "utf-8")
        else:
            final_input = user_input

        if final_input:
            st.session_state['generated_steps'] = generate_workflow(final_input)
        else:
            st.error("Please provide an input description or upload a file.")

# --- WORKSPACE LAYOUT ---
col_list, col_viz = st.columns([1, 1])

with col_list:
    if st.session_state['generated_steps']:
        st.markdown("<div class='section-title'>Generated Workflow</div>", unsafe_allow_html=True)
        updated_steps = []
        for i, step in enumerate(st.session_state['generated_steps'], start=1):
            clean = step.split(":", 1)[1] if ":" in step else step
            
            # Interactive Edit Mode
            edited_step = st.text_input(f"Step {i}", clean, key=f"edit_{i}", label_visibility="collapsed")
            updated_steps.append(edited_step)
            
            st.markdown(f"""
            <div class="step">
                <div class="step-no">{i}</div>
                <div>{edited_step}</div>
            </div>
            """, unsafe_allow_html=True)
        st.session_state['generated_steps'] = updated_steps

with col_viz:
    if st.session_state['generated_steps']:
        tabs = st.tabs(["📊 Diagram View", "📥 Export Suite"])
        
        with tabs[0]:
            mermaid_code = generate_mermaid_code(st.session_state['generated_steps'])
            st.markdown(f"```mermaid\n{mermaid_code}\n```")
            
        with tabs[1]:
            st.markdown("### Download Results")
            # PDF Export
            pdf_bytes = create_pdf_bytes(st.session_state['generated_steps'])
            st.download_button("Download as PDF", data=pdf_bytes, file_name="workflow.pdf", mime="application/pdf", use_container_width=True)
            
            # JSON Export
            json_data = json.dumps({"workflow": st.session_state['generated_steps']}, indent=4)
            st.download_button("Download as JSON", data=json_data, file_name="workflow.json", mime="application/json", use_container_width=True)
            
            # CSV Export
            df = pd.DataFrame(st.session_state['generated_steps'], columns=["Workflow Steps"])
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download as CSV", data=csv, file_name="workflow.csv", mime="text/csv", use_container_width=True)

# --- FOOTER ---
st.markdown("""
<div class="footer">
    <b>Built by: Ganesh Basani</b><br>
    AI Workflow Automation Project &copy; 2025
</div>
""", unsafe_allow_html=True)
