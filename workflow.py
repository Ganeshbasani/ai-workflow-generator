import re

def generate_workflow(text):
    # -------- BASIC VALIDATION --------
    if not isinstance(text, str) or text.strip() == "":
        return ["Please enter a valid workflow description"]

    text = text.lower().strip()

    # -------- REGEX-BASED SENTENCE PARSING --------
    sentences = re.split(r"[.!?\n]+", text)

    raw_steps = []
    seen = set()
    step_no = 1

    for sentence in sentences:
        s = sentence.strip()
        if s == "":
            continue

        # ================= EDUCATION DOMAIN =================
        if any(w in s for w in ["student", "admission", "course", "exam", "teacher", "school"]):
            if "apply" in s or "admission" in s: raw_steps.append("Process student admission")
            if "verify" in s: raw_steps.append("Verify student documents")
            if "enroll" in s or "course" in s: raw_steps.append("Enroll student into course")
            if "assign" in s: raw_steps.append("Assign subjects or classes")
            if "exam" in s or "test" in s: raw_steps.append("Schedule examination")
            if "result" in s or "grade" in s: raw_steps.append("Publish academic results")

        # ================= BUSINESS / ORGANIZATIONS =================
        if any(w in s for w in ["customer", "order", "payment", "invoice", "client", "employee"]):
            if "register" in s or "onboard" in s: raw_steps.append("Register new client/customer")
            if "order" in s or "purchase" in s: raw_steps.append("Process order request")
            if "payment" in s:
                if "fail" in s: raw_steps.append("Handle failed payment")
                else: raw_steps.append("Process payment transaction")
            if "invoice" in s: raw_steps.append("Generate tax invoice")
            if "ship" in s or "delivery" in s: raw_steps.append("Arrange logistics and delivery")

        # ================= REAL ESTATE DOMAIN =================
        if any(w in s for w in ["property", "house", "tenant", "buyer", "rent", "listing"]):
            if "list" in s or "add" in s: raw_steps.append("Create property listing")
            if "visit" in s or "view" in s: raw_steps.append("Schedule property viewing")
            if "agreement" in s or "contract" in s: raw_steps.append("Draft lease/sale agreement")
            if "rent" in s or "pay" in s: raw_steps.append("Collect rental payment")
            if "maintenance" in s: raw_steps.append("Log maintenance request")
            if "sell" in s or "buy" in s: raw_steps.append("Execute property transfer")

        # ================= HOSPITAL / HEALTHCARE =================
        if any(w in s for w in ["patient", "doctor", "appointment", "medical", "health", "ward"]):
            if "book" in s or "appointment" in s: raw_steps.append("Schedule doctor appointment")
            if "check" in s or "admit" in s: raw_steps.append("Patient check-in and vitals recording")
            if "diagnose" in s or "test" in s: raw_steps.append("Perform medical diagnosis")
            if "prescribe" in s or "medicine" in s: raw_steps.append("Issue medical prescription")
            if "bill" in s or "discharge" in s: raw_steps.append("Process discharge and final billing")

        # ================= SOFTWARE INDUSTRY / PROJECTS =================
        if any(w in s for w in ["software", "code", "sprint", "feature", "bug", "developer", "git"]):
            if "requirement" in s or "plan" in s: raw_steps.append("Analyze project requirements")
            if "design" in s: raw_steps.append("Create system architecture design")
            if "develop" in s or "code" in s: raw_steps.append("Commence feature development")
            if "test" in s or "qa" in s: raw_steps.append("Perform Quality Assurance (QA) testing")
            if "deploy" in s or "release" in s: raw_steps.append("Deploy to production environment")
            if "review" in s: raw_steps.append("Conduct code review")

        # ================= IT / INFRASTRUCTURE =================
        if any(w in s for w in ["user", "login", "server", "database", "cloud"]):
            if "login" in s or "auth" in s: raw_steps.append("Authenticate user")
            if "server" in s: raw_steps.append("Monitor server health")
            if "backup" in s: raw_steps.append("Perform automated data backup")

        # ================= GENERIC CATCH-ALL (Prevents empty results) =================
        if "start" in s or "begin" in s: raw_steps.append("Initiate workflow process")
        if "update" in s: raw_steps.append("Update system records")
        if "save" in s or "store" in s: raw_steps.append("Save data to database")
        if "email" in s or "send" in s: raw_steps.append("Send communication/notification")
        if "end" in s or "finish" in s: raw_steps.append("Complete workflow process")

    # -------- DEDUPLICATION + NUMBERING --------
    final_steps = []
    for step in raw_steps:
        if step not in seen:
            seen.add(step)
            final_steps.append(f"Step {step_no}: {step}")
            step_no += 1

    if not final_steps:
        # Instead of failing, try to turn their sentence into a generic step
        if len(sentences) > 0 and len(sentences[0]) > 2:
             return [f"Step 1: {sentences[0].capitalize()}"]
        return ["No specific workflow steps detected. Please describe the process more clearly."]

    return final_steps
