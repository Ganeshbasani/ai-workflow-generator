
import streamlit as st
import pandas as pd
from workflow import generate_workflow, extract_text, create_pdf

st.set_page_config(page_title="Workflow AI", layout="wide")

# Custom CSS for Animations and Modern UI
st.markdown("""
<style>
    @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    .step-card {
        animation: fadeIn 0.5s ease forwards;
        background: #1e293b;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 5px solid #6366f1;
    }
    .footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #0f172a;
        color: white;
        text-align: center;
        padding: 10px;
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ AI Workflow Architect")

# Sidebar for Uploads
with st.sidebar:
    st.header("📁 Input Source")
    uploaded_file = st.file_uploader("Upload PDF or TXT", type=["pdf", "txt"])
    user_text = st.text_area("Or type manually", placeholder="Enter process description...")

# Main Logic
input_data = ""
if uploaded_file:
    input_data = extract_text(uploaded_file)
    st.success("File uploaded successfully!")
elif user_text:
    input_data = user_text

if st.button("Generate Workflow"):
    if input_data:
        steps = generate_workflow(input_data)
        st.session_state['steps'] = steps
    else:
        st.warning("Please provide some input first.")

# Display & Export
if 'steps' in st.session_state:
    steps = st.session_state['steps']
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Generated Process")
        for i, s in enumerate(steps):
            st.markdown(f'<div class="step-card"><b>Step {i+1}:</b> {s}</div>', unsafe_allow_html=True)

    with col2:
        st.subheader("📥 Export")
        # CSV Export
        df = pd.DataFrame(steps, columns=["Workflow Steps"])
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", data=csv, file_name="workflow.csv", mime="text/csv")
        
        # PDF Export
        pdf_data = create_pdf(steps)
        st.download_button("Download PDF", data=pdf_data, file_name="workflow.pdf", mime="application/pdf")

# Footer
st.markdown(f"""
<div class="footer">
    Developed by <b>Ganesh Basani</b> | AI Workflow Automation Project | 2024
</div>
""", unsafe_allow_html=True)
