import streamlit as st
import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Architect AI", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS FOR FULL-SCREEN FIT ---
st.markdown("""
<style>
    /* Remove all default Streamlit padding */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0rem !important;
        max-width: 98% !important;
    }
    
    .stApp {
        background: #020617;
        color: #f8fafc;
    }

    /* Fixed Height Dashboard Layout */
    .main-container {
        display: flex;
        gap: 20px;
        height: 80vh;
    }

    .glass-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 20px;
        height: 100%;
        overflow-y: auto;
    }

    /* Custom Scrollbar */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }

    .step-box {
        background: rgba(30, 41, 59, 0.5);
        border-left: 4px solid #6366f1;
        padding: 15px;
        margin-bottom: 10px;
        border-radius: 10px;
    }

    .hero-title {
        font-size: 42px; font-weight: 800;
        background: linear-gradient(90deg, #fff, #6366f1);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. CORE LOGIC ---
def generate_workflow_logic(text, sector):
    raw_steps = [line.strip() for line in text.replace('.', '\n').split('\n') if len(line.strip()) > 10]
    blueprints = {
        "Educational Institutes": "Academic", "Business Organizations": "Ops",
        "Real Estate": "Property", "Software Industries": "Dev",
        "Software Projects": "SDLC", "Hospitals": "Clinical"
    }
    prefix = blueprints.get(sector, "Process")
    return [f"[{prefix}] {step}" for step in raw_steps[:15]] # Limit to 15 for UI fit

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
    pdf.cell(190, 10, txt=f"Architect AI - {sector}", ln=True, align='C')
    pdf.set_font("Arial", size=11)
    for i, step in enumerate(steps, 1):
        pdf.multi_cell(190, 8, txt=f"{i}. {step}")
    return bytes(pdf.output())

# --- 4. UI LAYOUT ---
st.markdown('<h1 class="hero-title">Architect AI</h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#64748b; margin-bottom:20px;">v2.5 Industry Synthesis Engine</p>', unsafe_allow_html=True)

col_input, col_output = st.columns([1, 1.4], gap="large")

with col_input:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🛠 Parameters")
    industry = st.selectbox("Industry Sector", ["Educational Institutes", "Business Organizations", "Real Estate", "Software Industries", "Software Projects", "Hospitals"])
    file = st.file_uploader("Upload Context", type=["pdf", "txt"])
    raw_input = st.text_area("Process Description", height=200, placeholder="Describe your workflow...")
    
    if st.button("⚡ CONSTRUCT WORKFLOW", use_container_width=True):
        if raw_input or file:
            content = raw_input
            if file:
                if file.type == "application/pdf":
                    reader = PdfReader(file)
                    content += " " + " ".join([p.extract_text() for p in reader.pages])
                else:
                    content += " " + str(file.read(), "utf-8")
            
            st.session_state['active_steps'] = generate_workflow_logic(content, industry)
            st.session_state['active_industry'] = industry
    st.markdown('</div>', unsafe_allow_html=True)

with col_output:
    if 'active_steps' in st.session_state:
        st.markdown(f"### 📋 {st.session_state['active_industry']} Blueprint")
        
        tab1, tab2 = st.tabs(["📊 Flowchart Diagram", "📝 Step Details"])
        
        with tab1:
            # FIX: Use markdown code block for Mermaid
            mm_code = generate_mermaid(st.session_state['active_steps'])
            st.markdown(f"```mermaid\n{mm_code}\n```")
            
        with tab2:
            st.markdown('<div style="max-height: 400px; overflow-y: auto;">', unsafe_allow_html=True)
            for i, step in enumerate(st.session_state['active_steps'], 1):
                st.markdown(f'<div class="step-box"><small style="color:#818cf8;">PHASE {i:02d}</small><br>{step}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        st.markdown("---")
        d1, d2 = st.columns(2)
        with d1:
            csv = pd.DataFrame(st.session_state['active_steps']).to_csv(index=False).encode('utf-8')
            st.download_button("📂 CSV", csv, "workflow.csv", use_container_width=True)
        with d2:
            pdf_bytes = create_pdf(st.session_state['active_steps'], st.session_state['active_industry'])
            st.download_button("📄 PDF", pdf_bytes, "report.pdf", use_container_width=True)
    else:
        st.markdown("""
        <div style="height: 500px; display: flex; align-items: center; justify-content: center; border: 2px dashed rgba(99, 102, 241, 0.2); border-radius: 20px;">
            <p style="color: #475569;">Awaiting input parameters to generate architecture...</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<p style="text-align:center; color:#334155; margin-top:30px;">Developed by Ganesh Basani</p>', unsafe_allow_html=True)
