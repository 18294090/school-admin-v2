"""登录页面视图上窗体的定义"""
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import PasswordField, SubmitField, SelectField, StringField, IntegerField, DateTimeField
from flask_wtf import FlaskForm
from flask_wtf.file import DataRequired


from wtforms.validators import InputRequired, EqualTo

class attendanceForm(FlaskForm):
   
    reason = StringField("请假原因", validators=[InputRequired()])
    startTime = DateTimeField("开始时间", validators=[InputRequired()])
    endTime = DateTimeField("结束时间", validators=[InputRequired()])
    submit = SubmitField("提交")
