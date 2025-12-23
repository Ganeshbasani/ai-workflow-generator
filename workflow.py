def generate_workflow(text):
    if not text or text.strip() == "":
        return ["Please enter a workflow description"]

    steps = []
    step_no = 1

    # Split into sentences
    sentences = text.replace("\n", ".").split(".")

    for sentence in sentences:
        s = sentence.lower().strip()
        if not s:
            continue

        # ---------- DOMAIN IDENTIFICATION ----------
        domain = None

        if any(word in s for word in ["student", "admission", "course", "exam", "result"]):
            domain = "education"
        elif any(word in s for word in ["login", "register", "deploy", "server", "bug", "api"]):
            domain = "it"
        elif any(word in s for word in ["customer", "order", "payment", "invoice", "billing", "report"]):
            domain = "business"

        # ---------- DOMAIN-SPECIFIC STEPS ----------
        if domain == "education":
            if "admission" in s or "apply" in s:
                steps.append(f"Step {step_no}: Process student admission")
                step_no += 1
            if "course" in s or "enroll" in s:
                steps.append(f"Step {step_no}: Enroll student into course")
                step_no += 1
            if "exam" in s:
                steps.append(f"Step {step_no}: Schedule examination")
                step_no += 1
            if "result" in s or "grade" in s:
                steps.append(f"Step {step_no}: Publish academic results")
                step_no += 1

        elif domain == "it":
            if "register" in s or "signup" in s:
                steps.append(f"Step {step_no}: Register new user")
                step_no += 1
            if "login" in s:
                steps.append(f"Step {step_no}: Authenticate user login")
                step_no += 1
            if "deploy" in s:
                steps.append(f"Step {step_no}: Deploy application")
                step_no += 1
            if "bug" in s or "error" in s:
                steps.append(f"Step {step_no}: Identify and fix software issue")
                step_no += 1

        elif domain == "business":
            if "order" in s or "purchase" in s:
                steps.append(f"Step {step_no}: Process customer order")
                step_no += 1
            if "payment" in s or "transaction" in s:
                steps.append(f"Step {step_no}: Process payment")
                step_no += 1
            if "invoice" in s or "billing" in s:
                steps.append(f"Step {step_no}: Generate invoice")
                step_no += 1
            if "report" in s:
                steps.append(f"Step {step_no}: Generate business report")
                step_no += 1

        # ---------- COMMON ACTIONS (ALWAYS CHECKED) ----------
        if "save" in s or "store" in s:
            steps.append(f"Step {step_no}: Save data to database")
            step_no += 1

        if "email" in s:
            steps.append(f"Step {step_no}: Send email notification")
            step_no += 1

        if "notify" in s:
            steps.append(f"Step {step_no}: Send system notification")
            step_no += 1

        if "approve" in s:
            steps.append(f"Step {step_no}: Approve request")
            step_no += 1

        if "reject" in s:
            steps.append(f"Step {step_no}: Reject request")
            step_no += 1

    if not steps:
        return ["No workflow steps detected"]

    return steps
