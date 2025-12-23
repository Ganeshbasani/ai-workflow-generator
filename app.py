import streamlit as st
from workflow import generate_workflow

st.title("AI-Driven Dynamic Workflow Generator")

user_input = st.text_area("Describe your process:")

if st.button("Generate Workflow"):
    workflow = generate_workflow(user_input)

    for i, step in enumerate(workflow, 1):
        st.write(f"{i}. {step}")
