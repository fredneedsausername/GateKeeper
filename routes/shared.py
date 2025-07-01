from flask import session, redirect
from functools import wraps
from page_routes import base_url as pages_base_url

def auth_required(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not session['user']:
            return redirect(pages_base_url + "login")
        return fn(*args, **kwargs)
    return decorated