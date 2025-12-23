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
        if "student" in s or "admission" in s or "course" in s or "exam" in s:
            if "apply" in s or "admission" in s:
                raw_steps.append("Process student admission")
            if "verify" in s:
                raw_steps.append("Verify student documents")
            if "enroll" in s or "course" in s:
                raw_steps.append("Enroll student into course")
            if "assign" in s:
                raw_steps.append("Assign subjects to student")
            if "exam" in s:
                raw_steps.append("Schedule examination")
            if "result" in s or "grade" in s:
                raw_steps.append("Publish academic results")
            if "attendance" in s:
                raw_steps.append("Record student attendance")

        # ================= BUSINESS DOMAIN =================
        if "customer" in s or "order" in s or "payment" in s or "invoice" in s:
            if "register" in s:
                raw_steps.append("Register customer")
            if "order" in s or "purchase" in s:
                raw_steps.append("Process customer order")
            if "payment" in s:
                if "fail" in s or "failed" in s:
                    raw_steps.append("Handle failed payment")
                else:
                    raw_steps.append("Process payment")
            if "refund" in s:
                raw_steps.append("Process refund request")
            if "invoice" in s or "billing" in s:
                raw_steps.append("Generate invoice")
            if "shipment" in s or "delivery" in s:
                raw_steps.append("Arrange product delivery")
            if "report" in s:
                raw_steps.append("Generate business report")
            if "revenue" in s:
                raw_steps.append("Calculate revenue")

        # ================= IT / SOFTWARE DOMAIN =================
        if "user" in s or "login" in s or "deploy" in s or "server" in s:
            if "register" in s or "signup" in s:
                raw_steps.append("Register new user")
            if "login" in s or "authenticate" in s:
                raw_steps.append("Authenticate user login")
            if "permission" in s or "role" in s:
                raw_steps.append("Assign user role and permissions")
            if "deploy" in s:
                raw_steps.append("Deploy application")
            if "server" in s:
                raw_steps.append("Monitor server performance")
            if "backup" in s:
                raw_steps.append("Take system backup")
            if "bug" in s or "error" in s:
                raw_steps.append("Identify and fix software issue")
            if "log" in s:
                raw_steps.append("Log system activity")

        # ================= COMMON ACTIONS =================
        if "save" in s or "store" in s:
            raw_steps.append("Save data to database")
        if "update" in s:
            raw_steps.append("Update existing records")
        if "delete" in s:
            raw_steps.append("Delete record")
        if "email" in s:
            raw_steps.append("Send email notification")
        if "notify" in s or "alert" in s:
            raw_steps.append("Send notification")
        if "approve" in s:
            raw_steps.append("Approve request")
        if "reject" in s:
            raw_steps.append("Reject request")
        if "generate" in s:
            raw_steps.append("Generate system output")

    # -------- DEDUPLICATION + NUMBERING --------
    final_steps = []
    for step in raw_steps:
        if step not in seen:
            seen.add(step)
            final_steps.append(f"Step {step_no}: {step}")
            step_no += 1

    if not final_steps:
        return ["No workflow steps detected"]

    return final_steps
