import streamlit as st
import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader
import base64

# --- 1. CORE LOGIC ---
def generate_workflow_logic(text, sector):
    """
    Simulates industry-specific intelligence by mapping the input 
    to architectural blueprints.
    """
    # Simple logic to split sentences; in production, this connects to your LLM
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
    """Generates flowchart code for the right-side visualization."""
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
        pdf.set_x(10)
        pdf.multi_cell(190, 8, txt=f"{i}. {step.strip()}")
        pdf.ln(2)
    return bytes(pdf.output())

# --- 2. PAGE CONFIG ---
st.set_page_config(page_title="Architect AI | Workflow Automation", layout="wide")

# --- 3. ADVANCED CSS & ANIMATIONS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');

/* Base Theme */
.stApp {
    background-color: #020617;
    background-image: 
        radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(30, 41, 59, 0.4) 0px, transparent 50%);
    font-family: 'Inter', sans-serif;
    color: #f8fafc;
}

/* Sidebar/Panel Styling */
.glass-card {
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 24px;
    padding: 30px;
    margin-bottom: 20px;
}

/* Titles */
.hero-title {
    font-size: 64px; font-weight: 800; letter-spacing: -2px;
    background: linear-gradient(to right, #fff, #94a3b8);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 0px;
}
.accent { color: #6366f1; -webkit-text-fill-color: #6366f1; }

/* Result Steps */
.step-box {
    background: rgba(30, 41, 59, 0.5);
    border-left: 4px solid #6366f1;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;
    transition: 0.3s;
    animation: fadeInRight 0.5s ease forwards;
}
.step-box:hover { background: rgba(99, 102, 241, 0.1); transform: translateX(5px); }

@keyframes fadeInRight {
    from { opacity: 0; transform: translateX(20px); }
    to { opacity: 1; transform: translateX(0); }
}

/* Custom Button */
.stButton>button {
    background: linear-gradient(90deg, #6366f1 0%, #4f46e5 100%) !important;
    border: none !important; color: white !important;
    padding: 25px !important; border-radius: 15px !important;
    font-weight: 700 !important; font-size: 18px !important;
    box-shadow: 0 10px 20px rgba(79, 70, 229, 0.3);
}
</style>
""", unsafe_allow_html=True)

# --- 4. LAYOUT DESIGN ---

# Header area
st.markdown('<h1 class="hero-title">Architect <span class="accent">AI</span></h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#94a3b8; font-size:20px; margin-bottom:40px;">Industrial-grade workflow synthesis for professional domains.</p>', unsafe_allow_html=True)

# Main Dashboard columns
left_col, right_col = st.columns([1, 1.4], gap="large")

with left_col:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🚀 Project Parameters")
    
    industry = st.selectbox(
        "Industry Sector",
        ["Educational Institutes", "Business Organizations", "Real Estate", "Software Industries", "Software Projects", "Hospitals"]
    )
    
    file = st.file_uploader("Context File (Optional)", type=["pdf", "txt"])
    
    raw_input = st.text_area("Process Description", 
                           placeholder=f"Outline the {industry} process or goals here...", 
                           height=200)
    
    generate_btn = st.button("⚡ CONSTRUCT WORKFLOW", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Aesthetic Image to fill the side
    st.image("https://images.unsplash.com/photo-1614741118887-7a4ee193a5fa?q=80&w=1000&auto=format&fit=crop", 
             caption="Systematic AI Analysis Engaged", use_container_width=True)

with right_col:
    if generate_btn and (raw_input or file):
        with st.spinner("Synthesizing Architecture..."):
            # Text Extraction logic
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

    # Display Results if they exist
    if 'active_steps' in st.session_state:
        st.markdown(f"### 📋 {st.session_state['active_industry']} Blueprint")
        
        # Tabs for Diagram and List
        tab1, tab2 = st.tabs(["📊 Flowchart Diagram", "📝 Step-by-Step"])
        
        with tab1:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            mm_code = generate_mermaid(st.session_state['active_steps'])
            st.markdown(f"```mermaid\n{mm_code}\n```")
            st.markdown('</div>', unsafe_allow_html=True)
            
        with tab2:
            for i, step in enumerate(st.session_state['active_steps'], start=1):
                st.markdown(f"""
                <div class="step-box">
                    <small style="color:#818cf8; font-weight:800;">PHASE {i:02d}</small><br>
                    {step}
                </div>
                """, unsafe_allow_html=True)
        
        # Download Section
        st.markdown("---")
        dl1, dl2 = st.columns(2)
        with dl1:
            csv_data = pd.DataFrame(st.session_state['active_steps'], columns=["Workflow Step"]).to_csv(index=False).encode('utf-8')
            st.download_button("📂 Download CSV", data=csv_data, file_name="architecture.csv", use_container_width=True)
        with dl2:
            pdf_bytes = create_pdf(st.session_state['active_steps'], st.session_state['active_industry'])
            st.download_button("📄 Download PDF Report", data=pdf_bytes, file_name="report.pdf", use_container_width=True)
    else:
        # Placeholder for empty state
        st.markdown("""
        <div style="height: 600px; display: flex; flex-direction: column; align-items: center; justify-content: center; border: 2px dashed rgba(99, 102, 241, 0.2); border-radius: 30px; background: rgba(15, 23, 42, 0.2);">
            <h3 style="color: #64748b;">Awaiting Input</h3>
            <p style="color: #475569;">Configure parameters on the left to generate architecture.</p>
        </div>
        """, unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="text-align: center; margin-top: 80px; padding: 40px; border-top: 1px solid rgba(255,255,255,0.05);">
    <p style="color: #64748b;">Architect AI Engine v2.5 | Developed by Ganesh Basani</p>
</div>
""", unsafe_allow_html=True)
