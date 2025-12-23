def generate_workflow(text):
    steps = []

    if not text or text.strip() == "":
        return ["Please enter a workflow description"]

    sentences = text.replace("\n", ".").split(".")
    step_count = 1

    for sentence in sentences:
        s = sentence.lower().strip()
        if not s:
            continue

        # -------- BUSINESS DOMAIN --------
        if "customer" in s or "user" in s:
            steps.append(f"Step {step_count}: Capture customer/user details")
            step_count += 1

        if "order" in s or "purchase" in s:
            steps.append(f"Step {step_count}: Process customer order")
            step_count += 1

        if "payment" in s or "transaction" in s:
            steps.append(f"Step {step_count}: Validate and process payment")
            step_count += 1

        if "invoice" in s or "billing" in s:
            steps.append(f"Step {step_count}: Generate invoice")
            step_count += 1

        if "report" in s:
            steps.append(f"Step {step_count}: Generate business report")
            step_count += 1

        # -------- IT / SOFTWARE DOMAIN --------
        if "login" in s or "authenticate" in s:
            steps.append(f"Step {step_count}: Authenticate user login")
            step_count += 1

        if "register" in s or "signup" in s:
            steps.append(f"Step {step_count}: Register new user")
            step_count += 1

        if "deploy" in s:
            steps.append(f"Step {step_count}: Deploy application")
            step_count += 1

        if "server" in s or "api" in s:
            steps.append(f"Step {step_count}: Handle server/API request")
            step_count += 1

        if "bug" in s or "error" in s:
            steps.append(f"Step {step_count}: Log and fix software issue")
            step_count += 1

        # -------- EDUCATION DOMAIN --------
        if "student" in s:
            steps.append(f"Step {step_count}: Capture student information")
            step_count += 1

        if "admission" in s or "enroll" in s:
            steps.append(f"Step {step_count}: Process student admission")
            step_count += 1

        if "course" in s or "subject" in s:
            steps.append(f"Step {step_count}: Assign course to student")
            step_count += 1

        if "exam" in s or "test" in s:
            steps.append(f"Step {step_count}: Schedule examination")
            step_count += 1

        if "result" in s or "grade" in s:
            steps.append(f"Step {step_count}: Publish academic results")
            step_count += 1

        # -------- COMMON ACTIONS --------
        if "save" in s or "store" in s:
            steps.append(f"Step {step_count}: Save data to database")
            step_count += 1

        if "email" in s:
            steps.append(f"Step {step_count}: Send email notification")
            step_count += 1

        if "notify" in s:
            steps.append(f"Step {step_count}: Send system notification")
            step_count += 1

        if "approve" in s:
            steps.append(f"Step {step_count}: Approve request")
            step_count += 1

        if "reject" in s:
            steps.append(f"Step {step_count}: Reject request")
            step_count += 1

    if not steps:
        return ["No workflow steps detected"]

    return steps
