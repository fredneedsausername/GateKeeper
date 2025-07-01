from ..server import app
from flask import render_template
from shared import auth_required
base_url = "/"

@app.route(base_url + "")
def index():
    return render_template("index.html")

# @auth_required