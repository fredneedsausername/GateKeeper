from flask import Flask
import os
from waitress import serve
from functools import wraps
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from functools import wraps

app = Flask(__name__)

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

if __name__ == "__main__":
    
    flask_env = get_env("FLASK_ENV")
    flask_port = get_env("FLASK_PORT")

    match flask_env:
        case "development":
            app.run(debug=True, port=flask_port, host="127.0.0.1")
        case "production":
            serve(app, port=flask_port, host="0.0.0.0")
        case _:
            raise Exception(f"{flask_env} must be either \"development\" or \"production\"")