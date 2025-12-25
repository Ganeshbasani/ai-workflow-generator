import streamlit as st
import pandas as pd
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
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="AI Generated Workflow", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    for i, step in enumerate(steps, start=1):
        pdf.multi_cell(0, 10, txt=f"{i}. {step}")
    return pdf.output(dest='S').encode('latin-1')

# --- UI CONFIG & ORIGINAL DESIGN ---
st.set_page_config(page_title="AI Workflow Generator", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

body {
    font-family: 'Inter', sans-serif;
    background: radial-gradient(circle at top, #1f2933, #020617);
    color: #e5e7eb;
}

/* Added Animation for Steps */
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
    animation: fadeInUp 0.4s ease-out forwards; /* Applied animation */
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

# --- INPUT SECTION ---
# Adding file upload feature
uploaded_file = st.file_uploader("Upload a Process Document (PDF or TXT)", type=["pdf", "txt"])

user_input = st.text_area(
    "Describe your process manually",
    placeholder="Customer registers.\nPlaces order.\nMakes payment.\nGenerate invoice.",
    height=140
)

# Process text from file or text area
final_input = ""
if uploaded_file:
    if uploaded_file.type == "application/pdf":
        final_input = extract_text_from_pdf(uploaded_file)
    else:
        final_input = str(uploaded_file.read(), "utf-8")
else:
    final_input = user_input

# --- GENERATION LOGIC ---
if st.button("⚡ Generate Workflow"):
    if final_input:
        steps = generate_workflow(final_input)
        st.session_state['generated_steps'] = steps
    else:
        st.error("Please provide an input description or upload a file.")

# --- DISPLAY & DOWNLOAD SECTION ---
if 'generated_steps' in st.session_state:
    steps = st.session_state['generated_steps']
    
    st.markdown("<div class='section-title'>Generated Workflow</div>", unsafe_allow_html=True)

    for i, step in enumerate(steps, start=1):
        clean = step.split(":", 1)[1] if ":" in step else step
        st.markdown(f"""
        <div class="step">
            <div class="step-no">{i}</div>
            <div>{clean}</div>
        </div>
        """, unsafe_allow_html=True)

    # Download Options
    st.markdown("### 📥 Download Results")
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV Export
        df = pd.DataFrame(steps, columns=["Workflow Steps"])
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download as CSV", data=csv, file_name="workflow.csv", mime="text/csv")
        
    with col2:
        # PDF Export
        pdf_bytes = create_pdf_bytes(steps)
        st.download_button("Download as PDF", data=pdf_bytes, file_name="workflow.pdf", mime="application/pdf")

# --- FOOTER ---
st.markdown("""
<div class="footer">
    <b>Built by: Ganesh Basani</b><br>
    AI Workflow Automation Project &copy; 2025
</div>
""", unsafe_allow_html=True)
