import streamlit as st
import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader

# Attempt to import your custom logic
try:
    from workflow import generate_workflow
except ImportError:
    def generate_workflow(text):
        return [line.strip() for line in text.replace('.', '\n').split('\n') if len(line.strip()) > 5]

# --- 1. NEW FEATURE: FLOWCHART GENERATOR ---
def generate_mermaid(steps):
    """Creates a flowchart diagram based on the steps."""
    mermaid_code = "graph TD\n"
    for i in range(len(steps)):
        # Shorten text for the boxes
        short_text = (steps[i][:35] + '...') if len(steps[i]) > 35 else steps[i]
        short_text = short_text.replace('"', "'")
        if i < len(steps) - 1:
            mermaid_code += f'    step{i}["{short_text}"] --> step{i+1}\n'
        else:
            mermaid_code += f'    step{i}["{short_text}"]\n'
    return mermaid_code

# --- 2. NEW FEATURE: PDF EXPORT ---
def create_pdf(steps):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, txt="Architect AI - Workflow Report", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    for i, step in enumerate(steps, start=1):
        pdf.set_x(10)
        pdf.multi_cell(190, 8, txt=f"{i}. {step.strip()}")
        pdf.ln(2)
    return bytes(pdf.output())

# --- 3. UI CONFIG & ORIGINAL DESIGN ---
st.set_page_config(page_title="Architect AI", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
.stApp { background: #020617; font-family: 'Inter', sans-serif; }
.badge { display: flex; justify-content: center; margin-bottom: 20px; }
.badge-content {
    background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.3);
    color: #818cf8; padding: 5px 15px; border-radius: 20px; font-size: 14px; font-weight: 500;
}
.main-title {
    text-align: center; font-size: 56px; font-weight: 800;
    background: linear-gradient(to bottom, #ffffff, #94a3b8);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px;
}
.architect-text { color: #6366f1; -webkit-text-fill-color: #6366f1; }
.main-subtitle { text-align: center; color: #94a3b8; font-size: 18px; margin-bottom: 40px; }

/* Input Styling */
[data-testid="stFileUploader"] { background: rgba(30, 41, 59, 0.4); border: 1px dashed rgba(99, 102, 241, 0.3); border-radius: 12px; }
.stTextArea textarea { background: rgba(15, 23, 42, 0.8) !important; border: 1px solid #1e293b !important; color: #e2e8f0 !important; border-radius: 12px !important; }

/* Generate Button */
.stButton button {
    width: 100%; background: #6366f1 !important; color: white !important;
    border: none !important; padding: 14px !important; font-weight: 600 !important;
    border-radius: 12px !important; box-shadow: 0 0 20px rgba(99, 102, 241, 0.4);
}

/* Step Cards */
.step-container {
    background: rgba(15, 23, 42, 0.6); border: 1px solid #1e293b;
    border-left: 4px solid #6366f1; border-radius: 12px; padding: 18px; margin-bottom: 12px;
}
.footer { text-align: center; color: #64748b; margin-top: 60px; font-size: 14px; }
</style>

<div class="badge"><div class="badge-content">⚙️ AI-Powered Workflows</div></div>
<div class="main-title"><span class="architect-text">Architect</span> AI</div>
<div class="main-subtitle">Transform your ideas into structured, actionable workflows.</div>
""", unsafe_allow_html=True)

# --- 4. APP INTERACTION ---
uploaded_file = st.file_uploader("", type=["pdf", "txt"])
user_input = st.text_area("", placeholder="Describe your process...", height=120)

if st.button("⚡ Generate Workflow"):
    # File extraction logic
    final_text = ""
    if uploaded_file:
        if uploaded_file.type == "application/pdf":
            reader = PdfReader(uploaded_file)
            final_text = " ".join([p.extract_text() for p in reader.pages])
        else:
            final_text = str(uploaded_file.read(), "utf-8")
    else:
        final_text = user_input

    if final_text:
        with st.spinner("Processing..."):
            st.session_state['steps'] = generate_workflow(final_text)

# --- 5. DISPLAY RESULTS ---
if 'steps' in st.session_state:
    steps = st.session_state['steps']
    
    # NEW VISUAL FEATURE: The Diagram
    st.markdown("### 📊 Workflow Diagram")
    m_code = generate_mermaid(steps)
    # Using markdown with mermaid block for better compatibility
    st.markdown(f"```mermaid\n{m_code}\n```")

    # The Step List (Original Design)
    st.markdown("### Process Breakdown")
    for i, step in enumerate(steps, start=1):
        st.markdown(f'<div class="step-container"><b style="color:#6366f1">{i}.</b> {step}</div>', unsafe_allow_html=True)

    # NEW FEATURE: Download Suite
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        csv = pd.DataFrame(steps, columns=["Steps"]).to_csv(index=False).encode('utf-8')
        st.download_button("📂 Export as CSV", data=csv, file_name="workflow.csv", use_container_width=True)
    with c2:
        pdf_data = create_pdf(steps)
        st.download_button("📄 Generate PDF Report", data=pdf_data, file_name="workflow.pdf", use_container_width=True)

st.markdown('<div class="footer">Built by Ganesh Basani — AI Workflow Automation Project</div>', unsafe_allow_html=True)
