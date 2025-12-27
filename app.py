import streamlit as st
import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader
import base64

# --- 1. PAGE CONFIG (Must be first) ---
st.set_page_config(page_title="Architect AI | Workflow Automation", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CORE LOGIC ---
def generate_workflow_logic(text, sector):
    raw_steps = [line.strip() for line in text.replace('.', '\n').split('\n') if len(line.strip()) > 10]
    blueprints = {
        "Educational Institutes": "Academic Phase",
        "Business Organizations": "Ops Milestone",
        "Real Estate": "Property Stage",
        "Software Industries": "Dev Sprint",
        "Software Projects": "SDLC Step",
        "Hospitals": "Clinical Protocol"
    }
    prefix = blueprints.get(sector, "Process")
    return [f"[{prefix}] {step}" for step in raw_steps]

def generate_mermaid(steps):
    mermaid_code = "graph TD\n"
    for i in range(len(steps)):
        clean_text = steps[i].replace('"', "'")
        short_text = (clean_text[:30] + '...') if len(clean_text) > 30 else clean_text
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
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    for i, step in enumerate(steps, start=1):
        pdf.multi_cell(190, 8, txt=f"{i}. {step.strip()}")
        pdf.ln(2)
    return bytes(pdf.output())

# --- 3. ADVANCED UI ADJUSTMENTS ---
st.markdown("""
<style>
    /* Remove Streamlit default padding for 'Full Bleed' look */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0rem !important;
        max-width: 95% !important;
    }
    
    .stApp {
        background-color: #020617;
        background-image: radial-gradient(circle at 2px 2px, rgba(255,255,255,0.05) 1px, transparent 0);
        background-size: 40px 40px;
    }

    /* Professional Glass Card */
    .glass-card {
        background: rgba(15, 23, 42, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 25px;
        margin-bottom: 20px;
    }

    .hero-title {
        font-size: 52px; font-weight: 800; letter-spacing: -1.5px;
        background: linear-gradient(90deg, #ffffff, #6366f1);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
    }

    /* Scrollable Results Area to keep page height fixed */
    .scroll-area {
        max-height: 70vh;
        overflow-y: auto;
        padding-right: 10px;
    }
    
    .step-box {
        background: rgba(30, 41, 59, 0.4);
        border-left: 3px solid #6366f1;
        padding: 15px;
        margin-bottom: 12px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 4. LAYOUT DESIGN ---

# Title
st.markdown('<h1 class="hero-title">Architect <span style="color:#6366f1; -webkit-text-fill-color:#6366f1;">AI</span></h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#94a3b8; margin-bottom:30px;">Professional Industrial Workflow Synthesis</p>', unsafe_allow_html=True)

main_left, main_right = st.columns([1, 1.2], gap="medium")

with main_left:
    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        industry = st.selectbox("Industry Sector", ["Educational Institutes", "Business Organizations", "Real Estate", "Software Industries", "Software Projects", "Hospitals"])
        file = st.file_uploader("Context Document", type=["pdf", "txt"])
        raw_input = st.text_area("Process Description", height=150, placeholder="Describe your workflow requirements...")
        generate_btn = st.button("⚡ CONSTRUCT WORKFLOW", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

with main_right:
    if generate_btn and (raw_input or file):
        with st.spinner("Processing..."):
            combined_text = raw_input
            if file:
                if file.type == "application/pdf":
                    reader = PdfReader(file)
                    combined_text += " " + " ".join([p.extract_text() for p in reader.pages])
                else:
                    combined_text += " " + str(file.read(), "utf-8")
            
            steps = generate_workflow_logic(combined_text, industry)
            st.session_state['active_steps'] = steps
            st.session_state['active_industry'] = industry

    if 'active_steps' in st.session_state:
        st.markdown(f"#### 📋 {st.session_state['active_industry']} Output")
        
        tab1, tab2 = st.tabs(["📊 Logic Flow", "📝 Detailed Steps"])
        
        with tab1:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            mm_code = generate_mermaid(st.session_state['active_steps'])
            st.mermaid(mm_code) # Updated to use native streamlit mermaid support if available or markdown
            st.markdown('</div>', unsafe_allow_html=True)
            
        with tab2:
            # Wrap steps in a scrollable div
            st.markdown('<div class="scroll-area">', unsafe_allow_html=True)
            for i, step in enumerate(st.session_state['active_steps'], start=1):
                st.markdown(f'<div class="step-box"><small style="color:#6366f1;">PHASE {i:02d}</small><br>{step}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        # Action Bar
        col1, col2 = st.columns(2)
        with col1:
            csv = pd.DataFrame(st.session_state['active_steps']).to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "workflow.csv", use_container_width=True)
        with col2:
            pdf = create_pdf(st.session_state['active_steps'], st.session_state['active_industry'])
            st.download_button("Download PDF", pdf, "report.pdf", use_container_width=True)
    else:
        st.markdown('<div style="height:450px; border:1px dashed #334155; border-radius:20px; display:flex; align-items:center; justify-content:center; color:#475569;">Ready for input analysis...</div>', unsafe_allow_html=True)

st.markdown('<p style="text-align:center; color:#334155; margin-top:50px;">Architect AI v2.5 | Ganesh Basani</p>', unsafe_allow_html=True)
