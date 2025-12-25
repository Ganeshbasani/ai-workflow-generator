import streamlit as st
import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader
from workflow import generate_workflow

# --- NEW FEATURE FUNCTIONS ---

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

# --- ORIGINAL UI CODE & DESIGN ---

st.set_page_config(page_title="AI Workflow Generator", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

body {
    font-family: 'Inter', sans-serif;
    background: radial-gradient(circle at top, #1f2933, #020617);
    color: #e5e7eb;
}

/* Added: Smooth Fade-in Animation for Steps */
@keyframes fadeIn {
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
    animation: fadeIn 0.5s ease forwards; /* Animation added here */
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
    text-align: center;
    padding-bottom: 20px;
}
</style>

<div class="container">
    <div class="title">AI-Driven Dynamic Workflow Generator</div>
    <div class="subtitle">Convert natural language into structured workflows</div>
</div>
""", unsafe_allow_html=True)

# --- FEATURE: FILE UPLOAD ---
uploaded_file = st.file_uploader("Upload PDF or Text File", type=["pdf", "txt"])

user_input = st.text_area(
    "Describe your process",
    placeholder="Customer registers.\nPlaces order.\nMakes payment.\nGenerate invoice.",
    height=140
)

# --- LOGIC ---
if st.button("⚡ Generate Workflow"):
    # Determine input source
    final_input = ""
    if uploaded_file:
        final_input = extract_text(uploaded_file)
    else:
        final_input = user_input

    if final_input:
        steps = generate_workflow(final_input)
        st.session_state['steps'] = steps

# Display Results
if 'steps' in st.session_state:
    steps = st.session_state['steps']
    st.markdown("<div class='section-title'>Generated Workflow</div>", unsafe_allow_html=True)

    for i, step in enumerate(steps, start=1):
        clean = step.split(":", 1)[1] if ":" in step else step
        st.markdown(f"""
        <div class="step">
            <div class="step-no">{i}</div>
            <div>{clean}</div>
        </div>
        """, unsafe_allow_html=True)

    # --- FEATURE: DOWNLOAD OPTIONS ---
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        csv = pd.DataFrame(steps, columns=["Workflow"]).to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", data=csv, file_name="workflow.csv", mime="text/csv")
    with col2:
        pdf_data = create_pdf(steps)
        st.download_button("Download PDF", data=pdf_data, file_name="workflow.pdf", mime="application/pdf")

st.markdown("""
<div class="footer">
Built by : Ganesh Basani -- AI Workflow Automation Project
</div>
""", unsafe_allow_html=True)
