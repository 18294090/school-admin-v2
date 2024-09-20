from datetime import datetime
import json
from flask_login import UserMixin, AnonymousUserMixin
from sqlalchemy import ForeignKey, func, CheckConstraint, case, Index
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, relationship
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from . import login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role = db.Column(db.String(16), unique=True, nullable=False)
    permissions = db.Column(db.Integer, default=0)

    def add_permission(self, perm):
        if not self.has_permission(perm):
            self.permissions += perm

    def remove_permission(self, perm):
        if self.has_permission(perm):
            self.permissions -= perm

    def reset_permission(self):
        self.permissions = 0

    def has_permission(self, perm):
        return self.permissions & perm == perm

class Permission:
    submit_job = 1
    publish_job = 2
    attendance_management = 4
    create_class = 8
    create_grade = 16
    create_school = 32
    job_grade = 64
    student_management = 128
    class_management = 256
    grade_management = 512
    admin = 1024

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    realname = db.Column(db.String(64), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role_id = db.Column(db.Integer, ForeignKey("roles.id"), nullable=False)
    role = db.relationship("Role", backref=backref("users", lazy="dynamic"))
    phone_number = db.Column(db.String(15))
    id_number = db.Column(db.String(20), unique=True)
    gender = db.Column(db.String(1))
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.Integer)
    avatar = db.Column(db.String(128), nullable=True)
    discriminator = db.Column(db.String(50))

    __mapper_args__ = {
        'polymorphic_identity': 'user',
        'polymorphic_on': discriminator
    }

    @property
    def password(self):
        raise AttributeError('密码字段不可读')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def can(self, perm):
        return self.role is not None and self.role.has_permission(perm)

    def is_administrator(self):
        return self.can(Permission.admin)

class AnonymousUser(AnonymousUserMixin):
    def can(self, permission):
        return False

    def is_administrator(self):
        return False

login_manager.anonymous_user = AnonymousUser

class School(db.Model):
    __tablename__ = "schools"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    school_name = db.Column(db.String(64), unique=True, nullable=False)
    school_master = db.Column(db.Integer, ForeignKey("users.id"))
    grades = db.relationship('GradeInfo', backref='school', lazy='dynamic')

class GradeInfo(db.Model):
    __tablename__ = "grades"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    grade_name = db.Column(db.String(64), unique=True, nullable=False)
    grade_master = db.Column(db.Integer, ForeignKey("users.id"))
    school_id = db.Column(db.Integer, ForeignKey("schools.id"))
    teachers = db.relationship('Teacher', backref='grade', lazy='dynamic', foreign_keys='Teacher.grade_id')
    classes = db.relationship('ClassInfo', backref='grade', lazy='dynamic')
    academic_year = db.Column(db.Integer)
    __table_args__ = (
        CheckConstraint('academic_year >= 1900 AND academic_year <= 2100', name='check_year'), 
    )

class ClassInfo(db.Model):
    __tablename__ = "classes"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    class_name = db.Column(db.String(64), nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey("grades.id"))
    attribute = db.Column(db.String(64))
    teachers = db.relationship('Teacher', secondary='teaching_relationships', back_populates='classes_taught')
    students = db.relationship('ClassStudent', back_populates='class_info', cascade='all, delete-orphan')
    teaching_relationships = db.relationship('TeachingRelationship', back_populates='class_info', cascade='all, delete-orphan')
    job_classes = db.relationship('JobClass', back_populates='classes')

class Teacher(User):
    __tablename__ = "teachers"
    id = db.Column(db.Integer, ForeignKey('users.id'), primary_key=True)
    school_id = db.Column(db.Integer, ForeignKey("schools.id"))
    school = db.relationship('School', backref='teachers')
    grade_id = db.Column(db.Integer, ForeignKey("grades.id"))
    subject = db.Column(db.String(32), nullable=False)
    classes_taught = db.relationship('ClassInfo', secondary='teaching_relationships', back_populates='teachers')
    taught_classes = db.relationship('TeachingRelationship', back_populates='teacher', foreign_keys='TeachingRelationship.teacher_id')
    __mapper_args__ = {
        'polymorphic_identity': 'teacher',
    }

class TeachingRelationship(db.Model):
    __tablename__ = "teaching_relationships"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    subject = db.Column(db.String(64))
    teacher_id = db.Column(db.Integer, ForeignKey("teachers.id", ondelete='CASCADE'))
    teacher = db.relationship('Teacher', back_populates="taught_classes", foreign_keys=[teacher_id])
    class_id = db.Column(db.Integer, ForeignKey("classes.id", ondelete='CASCADE'))
    class_info = db.relationship('ClassInfo', back_populates='teaching_relationships', foreign_keys=[class_id])

class Student(User):
    __tablename__ = "students"
    id = db.Column(db.Integer, ForeignKey('users.id'), primary_key=True)
    number= db.Column(db.String(64), unique=True, nullable=False)
    parent_contact = db.Column(db.String(64))
    jobs= db.relationship('JobStudent', back_populates='student')
    attending_classes = db.relationship('ClassStudent', back_populates='student')
    __mapper_args__ = {
        'polymorphic_identity': 'student',
    }

class ClassStudent(db.Model):
    __tablename__ = "class_student"
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id", ondelete='CASCADE'), primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete='CASCADE'), primary_key=True)
    student = db.relationship('Student', back_populates='attending_classes')
    class_info = db.relationship('ClassInfo', back_populates='students')

class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    job_name = db.Column(db.String(64))
    publish_time = db.Column(db.DateTime, default=datetime.utcnow)
    publisher = db.Column(db.Integer, ForeignKey("teachers.id"))
    publisher_name=db.relationship('Teacher', backref='jobs')
    question_paper = db.Column(db.String(64))
    subject = db.Column(db.String(64))
    context = db.Column(db.Text)
    select_answer = db.Column(db.String(256))
    complete = db.Column(db.String(64))
    paper_url = db.Column(db.String(64))
    answerCardStructure = db.Column(db.Text)
    multiple_choice_info = db.Column(db.Text)
    no_multiple_choice_info = db.Column(db.Text)
    total1 = db.Column(db.Integer)    
    job_classes = db.relationship("JobClass", back_populates="job", cascade="all, delete")
    job_details = db.relationship("JobDetail", back_populates="job", cascade="all, delete")
    job_students = db.relationship("JobStudent", back_populates="job", cascade="all, delete")

class AbnormalJob(db.Model):
    __tablename__ = "abnormal_jobs"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    job_id = db.Column(db.Integer, ForeignKey("jobs.id", ondelete='CASCADE'))
    job = db.relationship("Job", backref=db.backref("abnormal_jobs", lazy="dynamic"))
    reason = db.Column(db.String(64))
    paper = db.Column(db.String(64))
    position = db.Column(db.String(64))
    teacher_id = db.Column(db.Integer, ForeignKey("teachers.id"))
    teacher = db.relationship("Teacher", backref=db.backref("abnormal_jobs", lazy="dynamic"))
    process = db.Column(db.String(64))
    time=db.Column(db.DateTime, default=datetime.utcnow())
    number=db.Column(db.String(32))

class JobClass(db.Model):
    __tablename__ = "job_classes"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    job_id = db.Column(db.Integer, ForeignKey("jobs.id", ondelete='CASCADE'), nullable=False)
    class_id = db.Column(db.Integer, ForeignKey("classes.id", ondelete='CASCADE'), nullable=False)
    classes= db.relationship("ClassInfo", back_populates="job_classes")
    job = db.relationship("Job", order_by="Job.publish_time.desc()", back_populates="job_classes")
    average = db.Column(db.Float(precision=2), default=0)
    max = db.Column(db.Float(precision=2), default=0)
    min = db.Column(db.Float(precision=2), default=0)
    submit_number = db.Column(db.Integer, default=0)
    std = db.Column(db.Float(precision=2), default=0)
    date = db.Column(db.DateTime, default=datetime.utcnow())

class JobDetail(db.Model):
    __tablename__ = "job_details"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    job_id = db.Column(db.Integer, ForeignKey("jobs.id", ondelete='CASCADE'), nullable=False)
    job = db.relationship("Job", back_populates="job_details")
    student_id = db.Column(db.Integer, ForeignKey("students.id", ondelete='CASCADE'), nullable=False)
    student = db.relationship("Student", backref=db.backref("job_details", lazy="dynamic", cascade="all, delete"))
    serial_no = db.Column(db.Integer)
    answer = db.Column(db.String(64))
    tag = db.Column(db.String(64))
    mark = db.Column(db.Float(precision=2))

class JobStudent(db.Model):
    __tablename__ = "job_students"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    job_id = db.Column(db.Integer, ForeignKey("jobs.id", ondelete='CASCADE'), nullable=False)
    job = db.relationship("Job", order_by="Job.publish_time.desc()", back_populates="job_students")
    student_id = db.Column(db.Integer, ForeignKey("students.id", ondelete='CASCADE'), nullable=False)
    student = db.relationship("Student", backref="job_students")
    submit_time = db.Column(db.DateTime)
    select_mark = db.Column(db.Float(precision=2))
    complete_mark = db.Column(db.Float(precision=2))

    @hybrid_property
    def mark(self):
        if self.select_mark is None:
            return self.complete_mark
        elif self.complete_mark is None:
            return self.select_mark
        else:
            return self.select_mark + self.complete_mark

    @mark.expression
    def mark(cls):
        return case(
            (cls.select_mark == None, cls.complete_mark),
            (cls.complete_mark == None, cls.select_mark),
            else_=(cls.select_mark + cls.complete_mark)
        ).label("mark")
class Difficult(db.Model):
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    difficult = db.Column(db.String(32))
    context = db.Column(db.String(128))

class Representative(db.Model):
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    student_id = db.Column(db.Integer, ForeignKey("students.id"))
    teacher_id = db.Column(db.Integer, ForeignKey("teachers.id"))  # Corrected foreign key
    subject = db.Column(db.String(64))
    student = db.relationship("Student", backref=db.backref("representatives", lazy="dynamic"))

class Attendance(db.Model):  # 出勤
    __tablename__ = "attendances"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, ForeignKey("students.id"), nullable=False)  # 确保外键非空
    student = db.relationship("Student", backref="attendances")
    reason = db.Column(db.String(64), comment="请假理由")  # 添加注释提高代码可读性
    start_time = db.Column(db.DateTime, nullable=False, comment="请假开始时间")  # 确保开始时间非空
    end_time = db.Column(db.DateTime, nullable=False, comment="请假结束时间")  # 确保结束时间非空
    approver_id = db.Column(db.Integer, ForeignKey("teachers.id"),comment="审批人ID")
    approver = db.relationship("Teacher", backref="approved_attendances")
    status = db.Column(db.Integer, comment="请假状态: 0-待审核, 1-通过, 2-拒绝", default=0)
    leave_type = db.Column(db.String(64), comment="请假类型")
class Message(db.Model):
    __tablename__ = "messages" 
    id=db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(64))
    content = db.Column(db.String(128))
    sender = db.Column(db.INTEGER, ForeignKey("users.id"))
    sender_info = db.relationship("User", backref=db.backref("send_messages", lazy="dynamic"),foreign_keys=[sender])
    receiver = db.Column(db.INTEGER, ForeignKey("users.id"))
    receiver_info = db.relationship("User", backref=db.backref("receive_messages", lazy="dynamic"),foreign_keys=[receiver])
    time = db.Column(db.DateTime, default=datetime.utcnow)
    message_type = db.Column(db.Integer, ForeignKey("message_types.id"))
    msg_type=db.relationship("MessageType", backref=db.backref("messages", lazy="dynamic"))
    status = db.Column(db.Integer, default=0)#0为未读，1为已读，2为同意，3为拒绝

class MessageType(db.Model):
    __tablename__ = "message_types"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message_type = db.Column(db.String(64))


subject = {
    "语文": "chinese",
    "数学": "math",
    "外语": "foreign_language",
    "政治": "politics",
    "历史": "history",
    "地理": "geography",
    "物理": "physics",
    "化学": "chemistry",
    "生物": "biology",
    "科学": "science",
    "社会": "society",
    "信息技术": "it",
    "通用技术": "ut",    
}

grades = {
    "一年级": "1",
    "二年级": "2",
    "三年级": "3",
    "四年级": "4",
    "五年级": "5",
    "六年级": "6",
    "初一": "7",
    "初二": "8",
    "初三": "9",
    "高一": "10",
    "高二": "11",
    "高三": "12",
}
