"""视图文件，对请求进行处理，返回视图文件（网页模板）"""
 # -*-coding:utf-8-*-
import os
from flask.helpers import url_for
from sqlalchemy.sql.elements import Null
from .import main
from flask import render_template, redirect, flash, send_from_directory, request
from ..models import Permission,User,School,ClassInfo,Job,JobClass,JobStudent,ClassStudent,TeachingRelationship,Attendance,Student
from .forms import school_settings
from .. import db
from flask_login import current_user,login_user,login_required
from ..decorators import permission_required
import datetime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from flask_paginate import Pagination, get_page_parameter
#导入json
import json

@main.route("/index", methods=["POST", "GET"])
def index():    
    if current_user.role.role=='student':
        return redirect(f"/student/{current_user.id}")
    #筛选出任教班级数量，班级不重复
    classes_num= ClassInfo.query.join(TeachingRelationship).filter(TeachingRelationship.teacher_id==current_user.id).distinct().count()
    jobs_num=Job.query.filter(Job.publisher==current_user.id).count()
    end_time = datetime.datetime.now().date()
    start_time = end_time - datetime.timedelta(days=7)
    #求作业的平均分
    avg_score = get_teacher_subject_avg_score(current_user.id, current_user.subject)
    if avg_score is None:
        avg_score = 0
    complte_rate=get_overall_completion_rate(current_user.id, current_user.subject)
    leave_num=Attendance.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(TeachingRelationship.teacher_id==current_user.id,Attendance.end_time>=datetime.date.today(),Attendance.start_time<=datetime.date.today()).filter(Attendance.status==1).count()   
    #筛选出我所任教的班级JobClass的avarage字段，最低的十个数据
    jobs=JobClass.query.join(ClassInfo).join(TeachingRelationship).join(Job).filter(Job.id==JobClass.job_id,TeachingRelationship.teacher_id==current_user.id,TeachingRelationship.subject==current_user.subject,Job.subject==current_user.subject,JobClass.average!=0).order_by(JobClass.average/Job.total1*100).limit(10).all()    
    return(render_template("index.html",classes_num=classes_num,jobs_num=jobs_num,start_time=start_time,end_time=end_time,rank_rate=avg_score*100,finish_rate=complte_rate,leave_num=leave_num,jobs=jobs))
@main.route("/student/<id>/", methods=["POST", "GET"])
@login_required
def student(id):
    #只有任教老师和学生自己可以访问
    if current_user.id==int(id) or db.session.query(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(TeachingRelationship.teacher_id==current_user.id,ClassStudent.student_id==id).first():
        realname=db.session.query(Student.realname).filter(Student.id==id).first()[0]
        #在job_student中找出所有的学科，以及每个学科有几个Job_student记录
        subjects_info=db.session.query(Job.subject,func.count(JobStudent.id)).join(JobStudent).filter(JobStudent.student_id==id).group_by(Job.subject).all()
        num=JobStudent.query.filter(JobStudent.student_id==id).count()
        return render_template("student.html",user_id=id,subjects_info=subjects_info,num=num,realname=realname)
    else:
        flash("您没有权限访问该页面")
        if current_user.role.has_permission(Permission.publish_job):
            return  redirect(url_for("main.index"))
        else:
            return render_template("404.html","身份验证错误，请联系管理员")
@main.route("/star/<period>/", methods=["POST", "GET"])
@login_required
@permission_required(Permission.publish_job)
def get_star(period):  # 获取学生作业得分率
    end_time=datetime.datetime.now()    
    start_time=end_time-datetime.timedelta(days=int(period))    
    subject_=current_user.subject
    try:
        top_students = (
            db.session.query(
                Student.realname,
                Student.number,
                func.avg(JobStudent.mark / Job.total1*100).label('average_score_rate'),
                Student.id
            )
            .join(ClassStudent, Student.id == ClassStudent.student_id)
            .join(ClassInfo, ClassStudent.class_id == ClassInfo.id)
            .join(TeachingRelationship, ClassInfo.id == TeachingRelationship.class_id)
            .join(JobStudent, JobStudent.student_id == Student.id)
            .join(Job, JobStudent.job_id == Job.id)            
            .filter(TeachingRelationship.teacher_id == current_user.id)
            .filter(Job.subject == subject_)  # 使用当前用户的任教学科
            .filter(JobStudent.submit_time >= start_time, JobStudent.submit_time <= end_time)
            .group_by(Student.id)
            .order_by(func.avg(JobStudent.mark / Job.total1*100 ).desc())
            .limit(10)
            .all()
        )
        top_students_dict_list = []
        for student_row in top_students:
            student_dict = {
                'realname': student_row[0],
                'number': student_row[1],
                'average_score_rate': student_row[2],
                'id': student_row[3]
            }
            top_students_dict_list.append(student_dict)
        # 将字典列表序列化为JSON
        top_students= json.dumps(top_students_dict_list, ensure_ascii=False)
        return top_students
    except SQLAlchemyError as e:
        print(f"Error occurred while querying average score: {e}")
        flash("获取数据失败，请检查数据库连接", "danger")
        return None 
    
def get_overall_completion_rate(user_id, subject):
    try:
        # 获取当前用户任教班级的信息
        classes =ClassInfo.query.join(TeachingRelationship).filter(
            TeachingRelationship.teacher_id == user_id
        ).all()
        total_submissions = 0
        total_students = 0
        for class_info in classes:
            class_id = class_info.id
            student_count = len(class_info.students)
            # 查询该班级的所有作业提交人数
            query=db.session.query(func.sum(JobClass.submit_number)).join(Job).filter(
                Job.subject == subject,
                JobClass.class_id == class_id,
                JobClass.submit_number != None,
                JobClass.submit_number != 0

            )
            total_submissions += query.scalar() or 0
            n=JobClass.query.join(Job).filter(JobClass.class_id==class_id,Job.subject==subject).count()
            total_students += student_count*n        
        if total_students > 0:
            overall_completion_rate = (total_submissions / total_students) * 100
        else:
            overall_completion_rate = 0
        return overall_completion_rate
    except SQLAlchemyError as e:
        print(f"Error occurred while querying completion rates: {e}")
        return 0

def get_teacher_subject_avg_score(user_id, subject):
    try:
        # 获取当前用户任教班级的作业
        class_ids = db.session.query(ClassInfo.id).join(TeachingRelationship).filter(
            TeachingRelationship.teacher_id == user_id
        ).subquery()

        # 查询这些班级的作业，并计算平均分
        avg_score = db.session.query(func.avg(JobClass.average/Job.total1)).join(Job).filter(
            Job.subject == subject,
            JobClass.class_id.in_(class_ids),
            
            JobClass.average != 0
        ).scalar()

        return avg_score

    except SQLAlchemyError as e:
        print(f"Error occurred while querying average score: {e}")
        return None


@main.route("/teaching", methods=["POST", "GET"])
def teaching():
    return(render_template("index.html"))


@main.route("/download/<path:filename>",methods=["POST","GET"]) #下载文件
def download(filename):
    dir = os.getcwd()
    dir =os.path.join(dir,"app/static/file/") 
      
    return send_from_directory(dir,filename, as_attachment=True)


@main.route("/search/<ob>", methods=["POST", "GET"])
def search(ob):
    return(str(ob))


@main.route("/test", methods=["POST", "GET"])
def test():
    
    return(render_template("test.html"))


@main.route("/")
def root():
    return(redirect("/auth/"))

@main.route('/answer/<path:path>')
def browse_static(path):
    id=path
    
    # get the absolute path of the static folder
    static_folder = os.path.join(os.getcwd(),'app','static')
    # get the absolute path of the requested file or folder
    abs_path = os.path.join(static_folder,'answer', path)
    
    path="answer/"+path
    # check if the path exists and it is a file
    if os.path.exists(abs_path) and os.path.isfile(abs_path):
        # send the file as a response
        
        
        return send_from_directory(static_folder, path)
    # check if the path exists and it is a folder
    elif os.path.exists(abs_path) and os.path.isdir(abs_path):
        # get the list of files and folders in the path
        files = os.listdir(abs_path)
        
        # render a template with the files and folders
        return render_template('folder.html', files=files, path=path,name=Job.query.filter(Job.id==id).first().job_name)
    else:
        # return 404 if the path does not exist or is not valid
        return "Not found", 404

from flask import Flask, request, jsonify

app = Flask(__name__)

@main.route('/autocomplete', methods=['GET']) #输入框输入数据时自动补全
def autocomplete():
    query = request.args.get('q')
    param_type = request.args.get('type')

    if not query or not param_type:
        return jsonify([])
    # 根据传递的参数进行相应的处理，这里用示例数据代替
    if param_type == 'school':
        data = db.session.query(School).filter(School.school_name.like(f'%{query}%')).all()
    suggestions = [d.school_name for d in data]
    return jsonify(suggestions)


    



            



