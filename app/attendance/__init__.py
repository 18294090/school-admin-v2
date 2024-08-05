from flask import Blueprint
attendance_manage = Blueprint("attendance", __name__)
from . import views