import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
from pypdf import PdfReader
# Ensure you have your generate_workflow function in workflow.py
from workflow import generate_workflow 

# --- HELPER FUNCTIONS ---
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

def generate_mermaid_code(steps):
    """Converts a list of steps into Mermaid.js flowchart syntax."""
    mermaid_code = "graph TD\n"
    for i in range(len(steps)):
        clean_step = steps[i].replace('"', "'") # Escape quotes
        node_id = f"step{i}"
        mermaid_code += f'    {node_id}["{i+1}. {clean_step}"]\n'
        if i > 0:
            mermaid_code += f"    step{i-1} --> step{i}\n"
    return mermaid_code

# --- UI CONFIG ---
st.set_page_config(page_title="AI Workflow Workspace", layout="wide")

# Custom CSS for the "Sticky" look
st.markdown("""
<style>
    .stApp { background-color: #020617; color: #e5e7eb; }
    .step-box {
        background: #111827;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border-left: 5px solid #6366f1;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if 'generated_steps' not in st.session_state:
    st.session_state['generated_steps'] = []

# --- SIDEBAR: INPUT & REFINER ---
with st.sidebar:
    st.title("🛠️ Workflow Studio")
    
    # Template Gallery
    template = st.selectbox("Quick Start Templates", ["Custom", "E-commerce Refund", "User Onboarding", "Software Bug Fix"])
    if template != "Custom":
        templates = {
            "E-commerce Refund": "Customer requests refund. Support reviews. Return label sent. Item received. Refund processed.",
            "User Onboarding": "User signs up. Email verification. Profile setup. Welcome tour. First action taken.",
            "Software Bug Fix": "Bug reported. Dev reproduces bug. Fix implemented. QA testing. Deployment."
        }
        st.info(f"Template loaded: {template}")
        user_input_val = templates[template]
    else:
        user_input_val = ""

    uploaded_file = st.file_uploader("Upload Process Doc", type=["pdf", "txt"])
    user_input = st.text_area("Describe your process", value=user_input_val, height=150)
    
    if st.button("⚡ Generate / Reset", use_container_width=True):
        final_input = ""
        if uploaded_file:
            final_input = extract_text_from_pdf(uploaded_file) if uploaded_file.type == "application/pdf" else str(uploaded_file.read(), "utf-8")
        else:
            final_input = user_input
            
        if final_input:
            st.session_state['generated_steps'] = generate_workflow(final_input)
        else:
            st.error("Please provide input.")

    st.divider()
    st.subheader("🪄 Magic Refiner")
    if st.button("Simplify Workflow"):
        # Placeholder for AI logic: st.session_state['generated_steps'] = simplify_logic(...)
        st.toast("Refining logic...")
    if st.button("Identify Bottlenecks"):
        st.toast("Analyzing flow...")

# --- MAIN INTERACTIVE WORKSPACE ---
col_list, col_viz = st.columns([1, 1])

with col_list:
    st.subheader("📝 Interactive Steps")
    if st.session_state['generated_steps']:
        updated_steps = []
        for i, step in enumerate(st.session_state['generated_steps']):
            # Each step becomes an editable text input
            col_text, col_del = st.columns([0.85, 0.15])
            with col_text:
                new_step = st.text_input(f"Step {i+1}", step, key=f"step_edit_{i}", label_visibility="collapsed")
                updated_steps.append(new_step)
            with col_del:
                if st.button("🗑️", key=f"del_{i}"):
                    st.session_state['generated_steps'].pop(i)
                    st.rerun()
        
        st.session_state['generated_steps'] = updated_steps
        
        if st.button("➕ Add Step"):
            st.session_state['generated_steps'].append("New step...")
            st.rerun()
    else:
        st.info("Your generated steps will appear here. Start by typing in the sidebar.")

with col_viz:
    tab1, tab2, tab3 = st.tabs(["📊 Visual Flow", "📂 Export Suite", "🛠️ Metadata"])
    
    with tab1:
        if st.session_state['generated_steps']:
            mermaid_code = generate_mermaid_code(st.session_state['generated_steps'])
            st.markdown(f"```mermaid\n{mermaid_code}\n```")
        else:
            st.write("No workflow to visualize yet.")

    with tab2:
        st.subheader("Download Formats")
        if st.session_state['generated_steps']:
            steps = st.session_state['generated_steps']
            
            # PDF
            st.download_button("📄 Download PDF", data=create_pdf_bytes(steps), file_name="workflow.pdf")
            
            # Markdown
            md_text = "\n".join([f"### {i+1}. {s}" for i, s in enumerate(steps)])
            st.download_button("📝 Download Markdown", data=md_text, file_name="workflow.md")
            
            # JSON
            json_data = json.dumps({"workflow": steps}, indent=4)
            st.download_button("💻 Download JSON", data=json_data, file_name="workflow.json")

    with tab3:
        st.write("**Swimlane Analysis (AI Preview)**")
        st.caption("AI-identified actors for this process:")
        st.code("Primary Actor: Customer\nSystem Actor: Automation Engine")

# --- FOOTER ---
st.markdown(f"""
<div style="text-align: center; margin-top: 50px; color: #6b7280; font-size: 12px;">
    Built by: Ganesh Basani | AI Workflow Workspace © 2025
</div>
""", unsafe_allow_html=True)
