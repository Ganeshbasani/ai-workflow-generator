import streamlit as st
import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader

# --- 1. PAGE CONFIG (STRICTLY FIRST) ---
st.set_page_config(page_title="Architect AI", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS FOR PAGE FITTING & STYLING ---
st.markdown("""
<style>
    /* Force the app to use the full width and remove top padding */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }
    
    /* Global Background */
    .stApp {
        background-color: #020617;
        color: #f8fafc;
    }

    /* Glassmorphism Card */
    .glass-card {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 15px;
    }

    /* Scrollable Output Box */
    .scroll-box {
        height: 500px;
        overflow-y: auto;
        padding: 15px;
        background: rgba(15, 23, 42, 0.5);
        border-radius: 10px;
        border: 1px solid rgba(99, 102, 241, 0.2);
    }

    .step-box {
        background: rgba(30, 41, 59, 0.6);
        border-left: 4px solid #6366f1;
        padding: 12px;
        margin-bottom: 10px;
        border-radius: 5px;
    }

    .hero-title {
        font-size: 40px; 
        font-weight: 800; 
        background: linear-gradient(to right, #fff, #6366f1);
        -webkit-background-clip: text; 
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
def generate_workflow_logic(text, sector):
    raw_steps = [line.strip() for line in text.replace('.', '\n').split('\n') if len(line.strip()) > 10]
    blueprints = {
        "Educational Institutes": "Academic", "Business Organizations": "Ops",
        "Real Estate": "Property", "Software Industries": "Dev",
        "Software Projects": "SDLC", "Hospitals": "Clinical"
    }
    prefix = blueprints.get(sector, "Process")
    return [f"[{prefix}] {step}" for step in raw_steps]

def generate_mermaid(steps):
    mermaid_code = "graph TD\n"
    for i in range(len(steps)):
        clean_text = steps[i].replace('"', "'")
        short_text = (clean_text[:25] + '...') if len(clean_text) > 25 else clean_text
        if i < len(steps) - 1:
            mermaid_code += f'    step{i}["{short_text}"] --> step{i+1}\n'
        else:
            mermaid_code += f'    step{i}["{short_text}"]\n'
    return mermaid_code

def create_pdf(steps, sector):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, txt=f"Architect AI - {sector} Workflow", ln=True, align='C')
    pdf.set_font("Arial", size=11)
    for i, step in enumerate(steps, start=1):
        pdf.multi_cell(190, 8, txt=f"{i}. {step.strip()}")
    return bytes(pdf.output())

# --- 4. MAIN UI ---
st.markdown('<h1 class="hero-title">Architect AI</h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#94a3b8; margin-bottom:20px;">v2.5 Professional Workflow Engine</p>', unsafe_allow_html=True)

# Main Column Layout
col_input, col_output = st.columns([1, 1.5], gap="medium")

with col_input:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    industry = st.selectbox("Select Industry", ["Educational Institutes", "Business Organizations", "Real Estate", "Software Industries", "Software Projects", "Hospitals"])
    uploaded_file = st.file_uploader("Upload Context (PDF/TXT)", type=["pdf", "txt"])
    user_text = st.text_area("Process Description", height=200, placeholder="Paste your workflow details here...")
    
    if st.button("⚡ GENERATE ARCHITECTURE", use_container_width=True):
        if user_text or uploaded_file:
            full_context = user_text
            if uploaded_file:
                if uploaded_file.type == "application/pdf":
                    pdf_reader = PdfReader(uploaded_file)
                    full_context += " " + " ".join([page.extract_text() for page in pdf_reader.pages])
                else:
                    full_context += " " + str(uploaded_file.read(), "utf-8")
            
            st.session_state['results'] = generate_workflow_logic(full_context, industry)
            st.session_state['industry'] = industry
    st.markdown('</div>', unsafe_allow_html=True)

with col_output:
    if 'results' in st.session_state:
        st.subheader(f"Project Blueprint: {st.session_state['industry']}")
        
        tab_flow, tab_list = st.tabs(["📊 Flow Diagram", "📝 Step Details"])
        
        with tab_flow:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            mm = generate_mermaid(st.session_state['results'])
            st.mermaid(mm)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with tab_list:
            st.markdown('<div class="scroll-box">', unsafe_allow_html=True)
            for i, step in enumerate(st.session_state['results'], 1):
                st.markdown(f'<div class="step-box"><b>Phase {i:02d}:</b><br>{step}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Action Buttons
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            csv = pd.DataFrame(st.session_state['results'], columns=["Workflow"]).to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "workflow.csv", "text/csv", use_container_width=True)
        with btn_col2:
            pdf_data = create_pdf(st.session_state['results'], st.session_state['industry'])
            st.download_button("Download PDF", pdf_data, "report.pdf", "application/pdf", use_container_width=True)
    else:
        st.info("Awaiting parameters from the left panel to begin construction.")

st.markdown('<div style="text-align:center; color:#475569; padding-top:20px;">Developed by Ganesh Basani</div>', unsafe_allow_html=True)
