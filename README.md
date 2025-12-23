
--> AI-DRIVEN DYNAMIC WORKFLOW GENERATOR  <--

A modern application that converts **natural language descriptions** into **structured, step-by-step workflows**.
Built using **Python and Streamlit**, with a **custom HTML/CSS embedded UI** for a clean, professional experience.

---

1. OVERVIEW

This project allows users to describe a process in plain English (business, IT, or education workflows), and automatically generates a structured workflow.

The project demonstrates:

* Rule-based workflow generation
* Sentence parsing and keyword detection
* Clean UI design using HTML & CSS
* Scalable handling of large workflow inputs

---

2. FEATURES

* Converts natural language into workflow steps
* Supports Business, IT, and Education domains
* Handles small to large workflow descriptions
* Deduplication of repeated steps
* Basic conditional handling (example: failed payment)
* Modern dark-themed UI inspired by SaaS dashboards
* Runs and deploys on Streamlit Cloud

---

3. TECH STACK

Frontend (UI):

* HTML & CSS (embedded inside Streamlit)

Application:

* Python

Framework:

* Streamlit

Logic:

* Rule-based workflow engine

Deployment:

* Streamlit Cloud

Version Control:

* Git & GitHub

---

4. PROJECT STRUCTURE

ai-workflow-generator/
│
├── app.py            → Streamlit app with embedded HTML & CSS
├── workflow.py       → Workflow generation logic
├── requirements.txt  → Python dependencies
└── README.txt

---

5. HOW THE SYSTEM WORKS

1. User enters a process description in natural language
2. Input text is split into sentences
3. Each sentence is analyzed using keyword-based rules
4. Relevant workflow steps are generated
5. Duplicate steps are removed
6. Final workflow steps are displayed as cards in the UI

This simulates **AI-style reasoning using rule-based logic**.

---

 EXAMPLE INPUT

Customer registers.
Places order.
Makes payment.
Generate invoice.

---

 EXPECTED OUTPUT

Step 1: Register customer
Step 2: Save data to database
Step 3: Process customer order
Step 4: Process payment
Step 5: Generate invoice

---

6. TEST DATASETS

The project has been tested using:

* Small workflows (3–5 steps)
* Medium workflows (10–15 steps)
* Large enterprise workflows (20+ steps)
* Single-domain and multi-domain inputs

This ensures correctness and scalability.

---

7. UI DESIGN

* Dark gradient background
* Card-based workflow steps
* Clear visual hierarchy
* HTML & CSS embedded inside Streamlit
* No external HTML or CSS files

---

8. HOW TO RUN LOCALLY

1. Clone the repository:
   git clone : https://ai-workflow-generator-cysztisfr9rbs8ro7fcuuw.streamlit.app/

2. Navigate to the folder:
   cd ai-workflow-generator

3. Install dependencies:
   pip install -r requirements.txt

4. Run the app:
   streamlit run app.py

---

9. DEPLOYMENT

The application is deployed using **Streamlit Cloud**.
No additional server configuration is required.

---


10. FUTURE ENHANCEMENTS

* Flowchart visualization of workflows
* Export workflow as PDF or text
* Domain-based color tagging
* Advanced NLP support
* Workflow history storage

---

11. AUTHOR

  Ganesh Basani 

---


12.  LICENSE

This project is open-source and intended for educational and learning purposes.

