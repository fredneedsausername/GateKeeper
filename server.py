from flask import Flask, request, session, redirect, render_template, jsonify
from waitress import serve
from psycopg.rows import dict_row
import os
from psycopg_pool import ConnectionPool
from functools import wraps

def auth_required(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            return redirect("/login")
        return fn(*args, **kwargs)
    return decorated

def get_env(env_var: str):
        ret = os.getenv(env_var)
        if not ret:
            raise Exception(f"{env_var} not found")
        return ret

db_url = get_env("DATABASE_URL")
db_pool = ConnectionPool(
    conninfo=db_url,
    min_size=2,
    max_size=20,
    timeout=30.0,
    configure=lambda conn: setattr(conn, 'row_factory', dict_row)
)

def connected_to_database(fn):
    @wraps(fn)
    def wrapped_function(*args, **kwargs):
         with db_pool.connection() as conn:
              with conn.cursor() as curs:
                   ret = fn(curs, *args, **kwargs)
                   conn.commit()
                   return ret
    return wrapped_function

app = Flask(__name__)

@app.context_processor
def inject_global_vars():
    return {
        'username': session.get("user", "Non riconosciuto"),
    }

secret_key = get_env("SECRET_KEY")

app.secret_key = str(secret_key)

@app.route("/")
@auth_required
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    if request.method == "POST":
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        @connected_to_database
        def fetch_username(curs):
            curs.execute("""
            SELECT username
            FROM users
            WHERE password=%s        
            """, (password,))

            return curs.fetchone()

        if fetch_username():
            session["user"] = username
            return jsonify({
                "message": "Login effettuato con successo",
                "redirect": "/"
            }), 200
        else:
            return jsonify({
                "error": "Credenziali incorrette"
            })

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# @app.route("/")

if __name__ == "__main__":
    
    flask_env = get_env("FLASK_ENV")
    flask_port = get_env("FLASK_PORT")

    match flask_env:
        case "development":
            try:
                app.run(debug=True, port=flask_port, host="127.0.0.1")
            except SystemExit:
                db_pool.close(timeout=0)
        case "production":
            serve(app, port=flask_port, host="0.0.0.0")
        case _:
            raise Exception(f"{flask_env} must be either \"development\" or \"production\"")