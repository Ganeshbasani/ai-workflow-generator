import streamlit as st
import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader

# --- 1. INDUSTRY-SPECIFIC LOGIC ---
def generate_workflow(text, sector):
    """
    In a production app, this would be an API call to an LLM with a 
    system prompt tailored to the 'sector'. For this demo, it simulates 
    industry-specific step generation.
    """
    # Simulated logic: Splitting text and adding industry context
    raw_steps = [line.strip() for line in text.replace('.', '\n').split('\n') if len(line.strip()) > 5]
    
    industry_prefixes = {
        "Educational Institute": "Academic Phase",
        "Business Org": "Operational Step",
        "Real Estate": "Property Milestone",
        "Software Industry": "Sprint/Dev Task",
        "Software Project": "SDLC Phase",
        "Hospital/Healthcare": "Clinical Protocol"
    }
    
    prefix = industry_prefixes.get(sector, "Step")
    return [f"[{prefix}] {step}" for step in raw_steps]

# --- 2. FLOWCHART GENERATOR ---
def generate_mermaid(steps):
    mermaid_code = "graph TD\n"
    for i in range(len(steps)):
        short_text = (steps[i][:35] + '...') if len(steps[i]) > 35 else steps[i]
        short_text = short_text.replace('"', "'")
        if i < len(steps) - 1:
            mermaid_code += f'    step{i}["{short_text}"] --> step{i+1}\n'
        else:
            mermaid_code += f'    step{i}["{short_text}"]\n'
    return mermaid_code

# --- 3. PDF EXPORT ---
def create_pdf(steps, sector):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, txt=f"Architect AI - {sector} Report", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    for i, step in enumerate(steps, start=1):
        pdf.set_x(10)
        pdf.multi_cell(190, 8, txt=f"{i}. {step.strip()}")
        pdf.ln(2)
    return bytes(pdf.output())

# --- 4. UI CONFIG & DESIGN ---
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

/* Selectbox Styling */
div[data-baseweb="select"] > div {
    background-color: #0f172a !important;
    border-color: #1e293b !important;
    color: white !important;
}

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

<div class="badge"><div class="badge-content">⚙️ Multi-Industry AI Workflows</div></div>
<div class="main-title"><span class="architect-text">Architect</span> AI</div>
<div class="main-subtitle">Select your industry and transform ideas into structured pipelines.</div>
""", unsafe_allow_html=True)

# --- 5. APP INTERACTION ---
# NEW: Industry Selection
selected_industry = st.selectbox(
    "Select Industry Domain",
    ["Educational Institute", "Business Org", "Real Estate", "Software Industry", "Software Project", "Hospital/Healthcare"]
)

uploaded_file = st.file_uploader("", type=["pdf", "txt"])
user_input = st.text_area("", placeholder=f"Describe your {selected_industry} process...", height=120)

if st.button("⚡ Generate Workflow"):
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
        with st.spinner(f"Architecting {selected_industry} workflow..."):
            # Pass selected industry to the logic
            st.session_state['steps'] = generate_workflow(final_text, selected_industry)
            st.session_state['current_industry'] = selected_industry

# --- 6. DISPLAY RESULTS ---
if 'steps' in st.session_state:
    steps = st.session_state['steps']
    industry = st.session_state.get('current_industry', 'General')
    
    st.markdown(f"### 📊 {industry} Workflow Diagram")
    m_code = generate_mermaid(steps)
    st.markdown(f"```mermaid\n{m_code}\n```")

    st.markdown("### Process Breakdown")
    for i, step in enumerate(steps, start=1):
        st.markdown(f'<div class="step-container"><b style="color:#6366f1">{i}.</b> {step}</div>', unsafe_allow_html=True)

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        csv = pd.DataFrame(steps, columns=["Steps"]).to_csv(index=False).encode('utf-8')
        st.download_button("📂 Export as CSV", data=csv, file_name=f"{industry}_workflow.csv", use_container_width=True)
    with c2:
        pdf_data = create_pdf(steps, industry)
        st.download_button("📄 Generate PDF Report", data=pdf_data, file_name=f"{industry}_report.pdf", use_container_width=True)

st.markdown('<div class="footer">Built by Ganesh Basani — AI Workflow Automation Project</div>', unsafe_allow_html=True)
