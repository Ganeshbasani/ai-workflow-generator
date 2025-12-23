@app.route("/", methods=["GET", "POST"])
def index():
    steps = []

    if request.method == "POST":
        user_input = request.form["process"]
        steps = generate_workflow(user_input)

    return render_template("index.html", steps=steps)
