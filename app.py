import streamlit as st
import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader

# Attempt to import your custom workflow logic
try:
    from workflow import generate_workflow
except ImportError:
    # Fallback for testing if workflow.py isn't present
    def generate_workflow(text):
        return [f"Processed: {line.strip()}" for line in text.split('.') if line.strip()]

# --- HELPER FUNCTIONS ---

def extract_text_from_file(uploaded_file):
    """Extracts text from uploaded PDF or TXT files."""
    if uploaded_file.type == "application/pdf":
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    else:
        return str(uploaded_file.read(), "utf-8")

def create_pdf_bytes(steps):
    """Generates a PDF file from the workflow steps."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, txt="AI Generated Workflow", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    
    for i, step in enumerate(steps, start=1):
        clean_text = step.split(":", 1)[1] if ":" in step else step
        pdf.set_x(10)
        pdf.multi_cell(190, 10, txt=f"{i}. {clean_text.strip()}", border=0)
        pdf.ln(2)
        
    return pdf.output().encode('latin-1')

# --- UI CONFIG & DESIGN ---

st.set_page_config(page_title="AI Workflow Generator", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

body {
    font-family: 'Inter', sans-serif;
    background: radial-gradient(circle at top, #1f2933, #020617);
    color: #e5e7eb;
}

/* Fade-in Animation for Steps */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(15px); }
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
    color: white;
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
    animation: fadeInUp 0.5s ease-out forwards;
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
    color: white;
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

# --- INPUT SECTION ---

st.markdown("### 📤 Step 1: Provide Input")
uploaded_file = st.file_uploader("Upload a Process Document (PDF or TXT)", type=["pdf", "txt"])

user_input = st.text_area(
    "Or describe your process manually",
    placeholder="Customer registers.\nPlaces order.\nMakes payment.\nGenerate invoice.",
    height=140
)

# --- EXECUTION ---

if st.button("⚡ Generate Workflow"):
    input_data = ""
    if uploaded_file:
        input_data = extract_text_from_file(uploaded_file)
    elif user_input:
        input_data = user_input
    
    if input_data:
        with st.spinner("Analyzing process..."):
            steps = generate_workflow(input_data)
            st.session_state['generated_steps'] = steps
    else:
        st.error("Please upload a file or enter text.")

# --- OUTPUT SECTION ---

if 'generated_steps' in st.session_state:
    steps = st.session_state['generated_steps']
    
    st.markdown("<div class='section-title'>Generated Workflow</div>", unsafe_allow_html=True)

    for i, step in enumerate(steps, start=1):
        # Cleaning the string if it contains a colon
        clean_text = step.split(":", 1)[1] if ":" in step else step
        st.markdown(f"""
        <div class="step">
            <div class="step-no">{i}</div>
            <div>{clean_text.strip()}</div>
        </div>
        """, unsafe_allow_html=True)

    # Export Options
    st.markdown("---")
    st.markdown("### 📥 Download Your Workflow")
    c1, c2 = st.columns(2)
    
    with c1:
        df = pd.DataFrame(steps, columns=["Workflow Steps"])
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Download CSV", data=csv, file_name="workflow.csv", mime="text/csv", use_container_width=True)
        
    with c2:
        try:
            pdf_bytes = create_pdf_bytes(steps)
            st.download_button("📄 Download PDF", data=pdf_bytes, file_name="workflow.pdf", mime="application/pdf", use_container_width=True)
        except Exception as e:
            st.error(f"PDF Error: {e}")

# --- FOOTER ---

st.markdown(f"""
<div class="footer">
    <b>Built by : Ganesh Basani</b> -- AI Workflow Automation Project<br>
    &copy; 2025 All Rights Reserved
</div>
""", unsafe_allow_html=True)
