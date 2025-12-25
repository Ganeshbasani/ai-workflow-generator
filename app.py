import streamlit as st
import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader

# Attempt to import your logic; if missing, use this placeholder
try:
    from workflow import generate_workflow
except ImportError:
    def generate_workflow(text):
        # A simple placeholder split logic for testing
        return [line.strip() for line in text.replace('.', '\n').split('\n') if len(line.strip()) > 5]

# --- PDF GENERATION FIX ---
def create_pdf_bytes(steps):
    """Generates a PDF and returns raw bytes for Streamlit download."""
    pdf = FPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, txt="AI Generated Workflow", ln=True, align='C')
    pdf.ln(10)
    
    # Workflow Steps
    pdf.set_font("Arial", size=11)
    for i, step in enumerate(steps, start=1):
        clean_text = step.split(":", 1)[1] if ":" in step else step
        
        # Reset X to left margin to prevent "No horizontal space" error
        pdf.set_x(10)
        
        # Use 190mm width (Standard A4 width - margins)
        pdf.multi_cell(190, 8, txt=f"{i}. {clean_text.strip()}", border=0)
        pdf.ln(3) # Space between steps
        
    # output() in fpdf2 returns a bytearray; bytes() converts it for Streamlit
    return bytes(pdf.output())

# --- FILE EXTRACTION LOGIC ---
def extract_text(file):
    if file.type == "application/pdf":
        reader = PdfReader(file)
        return " ".join([page.extract_text() for page in reader.pages])
    else:
        return str(file.read(), "utf-8")

# --- UI DESIGN (STRICTLY ORIGINAL) ---
st.set_page_config(page_title="AI Workflow Generator", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

body {
    font-family: 'Inter', sans-serif;
    background: radial-gradient(circle at top, #1f2933, #020617);
    color: #e5e7eb;
}

/* New Animation */
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

.step {
    display: flex;
    align-items: center;
    margin-top: 14px;
    background: linear-gradient(145deg, #020617, #111827);
    border-radius: 12px;
    padding: 14px 18px;
    border-left: 4px solid #6366f1;
    animation: fadeInUp 0.4s ease forwards;
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
    margin-top: 80px;
    padding: 20px;
    font-size: 13px;
    color: #9ca3af;
    text-align: center;
    border-top: 1px solid #1f2937;
}
</style>

<div class="container">
    <div class="title">AI-Driven Dynamic Workflow Generator</div>
    <div class="subtitle">Convert natural language or documents into structured workflows</div>
</div>
""", unsafe_allow_html=True)

# --- APP INTERACTION ---

# File Upload Option
uploaded_file = st.file_uploader("Upload a PDF or Text file", type=["pdf", "txt"])

user_input = st.text_area(
    "Describe your process manually",
    placeholder="Customer registers.\nPlaces order.\nMakes payment.\nGenerate invoice.",
    height=140
)

if st.button("⚡ Generate Workflow"):
    final_text = ""
    if uploaded_file:
        final_text = extract_text(uploaded_file)
    elif user_input:
        final_text = user_input
        
    if final_text:
        with st.spinner("Processing..."):
            st.session_state['steps'] = generate_workflow(final_text)
    else:
        st.warning("Please provide an input first!")

# Display and Download
if 'steps' in st.session_state:
    steps = st.session_state['steps']
    
    st.markdown("### Generated Workflow")
    for i, step in enumerate(steps, start=1):
        clean = step.split(":", 1)[1] if ":" in step else step
        st.markdown(f"""
        <div class="step">
            <div class="step-no">{i}</div>
            <div>{clean}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Download Buttons
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        csv_data = pd.DataFrame(steps, columns=["Steps"]).to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", data=csv_data, file_name="workflow.csv", mime="text/csv", use_container_width=True)
        
    with col2:
        pdf_data = create_pdf_bytes(steps)
        st.download_button("📄 Download PDF", data=pdf_data, file_name="workflow.pdf", mime="application/pdf", use_container_width=True)

# Footer
st.markdown(f"""
<div class="footer">
Built by : Ganesh Basani -- AI Workflow Automation Project
</div>
""", unsafe_allow_html=True)
