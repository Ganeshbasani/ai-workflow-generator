def generate_workflow(text):
    steps = []
    text = text.lower()

    if "register" in text:
        steps.append("Capture user details")

    if "save" in text or "store" in text:
        steps.append("Save data to database")

    if "email" in text:
        steps.append("Send confirmation email")

    if not steps:
        steps.append("No workflow detected")

    return steps
