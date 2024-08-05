from functools import wraps
from flask import abort, jsonify
from flask_login import current_user
from .models import Permission

def permission_required(permisson):
    def decorate(f):
        @wraps(f)
        def decorated_fuction(*args, **kwargs):
            if not current_user.can(permisson):
                abort(403)
            return f(*args, **kwargs)
        return(decorated_fuction)
    return decorate

def admin_required(f):
    return permission_required(Permission.admin)(f)

def handle_database_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # 处理数据库错误的逻辑
            return jsonify({"error": str(e)}), 500
    return wrapper