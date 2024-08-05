
"""定义蓝图，作控制器，分发url请求"""

from flask import Blueprint
message = Blueprint("message", __name__)
from . import views



