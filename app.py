import streamlit as st
import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader
from workflow import generate_workflow

# --- FUNCTIONS ---
def extract_text(uploaded_file):
    if uploaded_file.type == "application/pdf":
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    else:
        return str(uploaded_file.read(), "utf-8")

def create_pdf(steps):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, txt="Generated Workflow", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    for i, step in enumerate(steps, start=1):
        clean = step.split(":", 1)[1] if ":" in step else step
        pdf.set_x(10)
        pdf.multi_cell(190, 10, txt=f"Step {i}: {clean.strip()}")
    return bytes(pdf.output())

# --- UI CONFIG ---
st.set_page_config(page_title="Architect AI", layout="centered")

# --- CUSTOM MODERN CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

/* Main Background */
.stApp {
    background: #020617;
    font-family: 'Inter', sans-serif;
}

/* Badge */
.badge {
    display: flex;
    justify-content: center;
    margin-bottom: 20px;
}
.badge-content {
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #818cf8;
    padding: 5px 15px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 500;
}

/* Titles */
.main-title {
    text-align: center;
    font-size: 56px;
    font-weight: 800;
    background: linear-gradient(to bottom, #ffffff, #94a3b8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 10px;
}
.architect-text {
    color: #6366f1;
    -webkit-text-fill-color: #6366f1;
}

.main-subtitle {
    text-align: center;
    color: #94a3b8;
    font-size: 18px;
    margin-bottom: 40px;
    line-height: 1.6;
}

/* File Upload & Input Area */
[data-testid="stFileUploader"] {
    background: rgba(30, 41, 59, 0.4);
    border: 1px dashed rgba(99, 102, 241, 0.3);
    border-radius: 12px;
    padding: 20px;
}

.stTextArea textarea {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid #1e293b !important;
    color: #e2e8f0 !important;
    border-radius: 12px !important;
}

/* Glowing Button */
.stButton button {
    width: 100%;
    background: #6366f1 !important;
    color: white !important;
    border: none !important;
    padding: 12px !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    box-shadow: 0 0 20px rgba(99, 102, 241, 0.4);
    transition: 0.3s;
}
.stButton button:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 30px rgba(99, 102, 241, 0.6);
}

/* Workflow Steps */
.step-container {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid #1e293b;
    border-left: 4px solid #6366f1;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
    animation: fadeIn 0.6s ease forwards;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.footer {
    text-align: center;
    color: #64748b;
    margin-top: 50px;
    font-size: 14px;
}
</style>

<div class="badge"><div class="badge-content">⚙️ AI-Powered Workflows</div></div>
<div class="main-title"><span class="architect-text">Architect</span> AI</div>
<div class="main-subtitle">Transform your ideas into structured, actionable workflows<br>with the power of artificial intelligence.</div>
""", unsafe_allow_html=True)

# --- APP CONTENT ---
uploaded_file = st.file_uploader("", type=["pdf", "txt"])

user_input = st.text_area(
    "",
    placeholder="Describe the workflow you want to generate (e.g. 'Customer onboarding for SaaS analytics')",
    height=100
)

if st.button("⚡ Generate Workflow"):
    final_input = ""
    if uploaded_file:
        final_input = extract_text(uploaded_file)
    else:
        final_input = user_input

    if final_input:
        with st.spinner("Thinking..."):
            steps = generate_workflow(final_input)
            st.session_state['steps'] = steps

# --- RESULTS ---
if 'steps' in st.session_state:
    steps = st.session_state['steps']
    st.write("---")
    
    for i, step in enumerate(steps, start=1):
        clean = step.split(":", 1)[1] if ":" in step else step
        st.markdown(f"""
        <div class="step-container">
            <span style="color: #6366f1; font-weight: 700; margin-right: 10px;">{i}.</span>
            {clean.strip()}
        </div>
        """, unsafe_allow_html=True)

    # Export Buttons (Side by Side)
    col1, col2 = st.columns(2)
    with col1:
        csv = pd.DataFrame(steps, columns=["Workflow"]).to_csv(index=False).encode('utf-8')
        st.download_button("📂 Export as CSV", data=csv, file_name="workflow.csv", use_container_width=True)
    with col2:
        pdf_data = create_pdf(steps)
        st.download_button("📄 Generate PDF Report", data=pdf_data, file_name="workflow.pdf", use_container_width=True)

# Footer
st.markdown("""
<div class="footer">
    Built by Ganesh Basani — AI Workflow Automation Project
</div>
""", unsafe_allow_html=True)
