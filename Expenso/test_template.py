# test_template.py
from flask import Flask, render_template

app = Flask(__name__, template_folder="templates")

@app.route("/")
def home():
    return render_template("register.html")

if __name__ == "__main__":
    app.run(debug=True)
