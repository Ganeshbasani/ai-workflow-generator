def generate_workflow(text):
    if not text or text.strip() == "":
        return ["Please enter a workflow description"]

    steps = []
    sentences = text.replace("\n", ".").split(".")
    step_no = 1

    for sentence in sentences:
        s = sentence.lower().strip()
        if not s:
            continue

        # ---------- EDUCATION DOMAIN ----------
        if any(word in s for word in ["student", "admission", "course", "exam", "result"]):
            if "admission" in s or "apply" in s:
                steps.append(f"Step {step_no}: Process student admission")
                step_no += 1
            elif "course" in s or "enroll" in s:
                steps.append(f"Step {step_no}: Enroll student into course")
                step_no += 1
            elif "exam" in s:
                steps.append(f"Step {step_no}: Schedule examination")
                step_no += 1
            elif "result" in s or "grade" in s:
                steps.append(f"Step {step_no}: Publish academic results")
                step_no += 1
            continue

        # ---------- IT DOMAIN ----------
        if any(word in s for word in ["login", "register", "deploy", "server", "bug", "api"]):
            if "register" in s or "signup" in s:
                steps.append(f"Step {step_no}: Register new user")
                step_no += 1
            elif "login" in s:
                steps.append(f"Step {step_no}: Authenticate user login")
                step_no += 1
            elif "deploy" in s:
                steps.append(f"Step {step_no}: Deploy application")
                step_no += 1
            elif "bug" in s or "error" in s:
                steps.append(f"Step {step_no}: Identify and fix software issue")
                step_no += 1
            continue

        # ---------- BUSINESS DOMAIN ----------
        if any(word in s for word in ["customer", "order", "payment", "invoice", "billing", "report"]):
            if "order" in s or "purchase" in s:
                steps.append(f"Step {step_no}: Process customer order")
                step_no += 1
            elif "payment" in s or "transaction" in s:
                steps.append(f"Step {step_no}: Process payment")
                step_no += 1
            elif "invoice" in s or "billing" in s:
                steps.append(f"Step {step_no}: Generate invoice")
                step_no += 1
            elif "report" in s:
                steps.append(f"Step {step_no}: Generate business report")
                step_no += 1
            continue

        # ---------- COMMON ACTIONS ----------
        if "email" in s or "notify" in s:
            steps.append(f"Step {step_no}: Send notification")
            step_no += 1
        elif "save" in s or "store" in s:
            steps.append(f"Step {step_no}: Save data to database")
            step_no += 1

    if not steps:
        return ["No workflow steps detected"]

    return steps
