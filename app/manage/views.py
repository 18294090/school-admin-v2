from .import manage
from .. import db
from flask_paginate import Pagination, get_page_parameter
from flask import render_template, redirect, flash, url_for, request,send_from_directory,jsonify
from ..models import Role,GradeInfo,Student,Message, MessageType,ClassInfo,ClassStudent,Teacher, Attendance,TeachingRelationship,Representative, User,subject,Permission,grades,School,JobStudent,Job,JobClass
from .forms import students_add, teacher_add, teacher_add_all,photo_add
from .. import db
from ..decorators import permission_required
import pandas as pd
from flask_login import current_user,login_required
from sqlalchemy import func,or_
import os
import datetime
from ..auth.faceRecognizer import faceRecognize
from io import BytesIO
import qrcode
import base64

@manage.route("/create_class", methods=["POST", "GET"])
@login_required
@permission_required(Permission.publish_job)
def create_class():
    if request.method == "POST":
        class_type = request.form.get("class_type")
        grade = request.form.get("grade")
        file = request.files.get("file")
        if file is None:
            flash("未选择电子表格文件", "error")
            return redirect(url_for("manage.classes"))
        try:
            file_content = BytesIO(file.read())
        except Exception as e:
            flash(f"读取电子表格文件异常 {e}", "error")
            return redirect(url_for("manage.classes"))
        class_name = request.form.get("classname")
        if class_type == "专业班":
            sub = current_user.subject
            class_name = f"{grade}{sub}{class_name}班"
        else:            
            class_name = f"{grade}{class_name}班"
        school_id = current_user.school_id
        g=GradeInfo.query.filter(GradeInfo.grade_name==grade,GradeInfo.school_id==school_id).first()
        if g is None:
            g=GradeInfo(grade_name=grade,school_id=school_id)
            db.session.add(g)
            db.session.commit()
        sub = "班主任"
        if school_id is None:
            class_ = ClassInfo.query.join(TeachingRelationship).filter(TeachingRelationship.teacher_id == current_user.id, ClassInfo.class_name == class_name).first()
        else:
            class_ = ClassInfo.query.join(GradeInfo, GradeInfo.id == ClassInfo.grade_id).join(School, School.id == GradeInfo.school_id).filter(School.id == current_user.school_id, ClassInfo.class_name == class_name).first()
        if class_ is None:
            class_ = ClassInfo(class_name=class_name, attribute=class_type, grade_id=g.id)
            db.session.add(class_)
            db.session.commit()
        else:
            flash("班级已存在", "error")
            return redirect(url_for("manage.classes"))        
        add, total = import_student(file_content, class_.id)
        teaching_relationships = TeachingRelationship.query.filter(TeachingRelationship.teacher_id == current_user.id, TeachingRelationship.class_id == class_.id, TeachingRelationship.subject =="班主任").first()
        teaching_relationships1= TeachingRelationship.query.filter(TeachingRelationship.teacher_id == current_user.id, TeachingRelationship.class_id == class_.id, TeachingRelationship.subject ==current_user.subject).first()
        if teaching_relationships is None:
            teaching_relationships = TeachingRelationship(teacher_id=current_user.id, class_id=class_.id, subject=sub)
            db.session.add(teaching_relationships)
        if teaching_relationships1 is None:
            teaching_relationships1 = TeachingRelationship(teacher_id=current_user.id, class_id=class_.id, subject=current_user.subject)
            db.session.add(teaching_relationships1)
        db.session.commit()
        flash(f"新添加学生{add}人，共{total}人加入当前班级", "success")
        return redirect(url_for("manage.classes"))
    return render_template("manage/create_class.html", grades=grades, subjects=subject)

@manage.route("/import_students", methods=["POST", "GET"])
@login_required
@permission_required(Permission.publish_job)
def import_student_page():
    if request.method == "POST":
        try:
            file = request.files.get("file")
            class_id = request.form.get("class_id")

            if file is None:
                flash("未选择电子表格文件", "error")
                return jsonify({"error": "未选择电子表格文件"}), 400
            add, total = import_student(file, class_id)
            flash(f"新添加学生{add}人，共{total}人加入当前班级", "success")
            return jsonify({"add": add, "total": total})
        except Exception as e:
            flash(f"导入学生过程中发生异常 {e}", "error")
            return jsonify({"error": f"导入学生过程中发生异常 {e}"}), 500
    return jsonify({"error": "无效请求"}), 400

def import_student(file, class_id):
    add = 0
    total = 0
    try:
        df = pd.read_excel(file)
    except Exception as e:
        flash(f"读取电子表格文件异常 {e}", "error")
        return add, total
    for i in range(len(df)):
        #以字符串方式读取学号位数为十位如果不足十位，前面补0，超出十位取后十位
        number = str(df.at[i, "学号"]).zfill(10)
        number = number[:10]
        name = df.at[i, "姓名"]
        sex = None
        if df.at[i, "性别"] in ["男","女"]:
            sex = df.at[i, "性别"]
        total += 1
        username=str(current_user.id)+number
        student_ = User.query.filter(User.username == username).first()        
        if student_ is None:
            role = Role.query.filter(Role.role == "student").first()       
            student_ = Student(username=username, password=number, role=role, realname=name, gender=sex,discriminator="student",number=number)
            student_.number=number
            db.session.add(student_)
            db.session.commit()
            add += 1
        class_student = ClassStudent.query.filter(ClassStudent.student_id == student_.id, ClassStudent.class_id == class_id).first()
        if class_student is None:
            class_student = ClassStudent(student_id=student_.id, class_id=class_id)
            db.session.add(class_student)            
    db.session.commit()
    return add, total

@manage.route("/classes")
@login_required
@permission_required(Permission.publish_job)
def classes():
    all_grades=GradeInfo.query.join(School).filter(School.id==current_user.school_id).all()
    classes = ClassInfo.query.join(TeachingRelationship).filter(TeachingRelationship.teacher_id == current_user.id).all()
    cla=[]
    for i in classes:
        master=db.session.query(TeachingRelationship).filter(TeachingRelationship.class_id==i.id,TeachingRelationship.subject=="班主任").first()
        if master is None:
            name=None
            id=None
        else:
            name=master.teacher.realname
            id=master.teacher.id
        cla.append([i.class_name,name,len(i.students),i.attribute,id,i.id])
    return render_template("manage/classes.html" , classes=cla,subjects=subject,all_grades=all_grades)

#删除班级
@manage.route("/delete_class/<id>")
@login_required
@permission_required(Permission.publish_job)
def delete_class(id):
    class_=ClassInfo.query.filter(ClassInfo.id==int(id)).first()
    TeachingRelationship.query.filter(TeachingRelationship.class_id==class_.id).delete()
    ClassStudent.query.filter(ClassStudent.class_id==class_.id).delete()
    JobClass.query.filter(JobClass.class_id==class_.id).delete()
    db.session.delete(class_)
    db.session.commit()
    return redirect(url_for("manage.classes"))

@manage.route("/invite_teacher/",methods=["GET", "POST"])
@login_required
@permission_required(Permission.publish_job)
def edit_class():
    if request.method=="POST":
        teacher=request.json.get("teacher")
        class_id=request.json.get("class_id")
        message_type=db.session.query(MessageType).filter(MessageType.message_type=="任课邀请").first().id
        class_=ClassInfo.query.filter(ClassInfo.id==class_id).first()
        
        message=Message(title="任课邀请",content=f"{current_user.realname}老师邀请您加入:{class_.class_name}",sender=current_user.id,receiver=teacher,message_type=message_type,status=0)
        db.session.add(message)
        db.session.commit()
        flash("邀请已发送，请等待相关老师确认")
        return ("邀请已发送，请等待相关老师确认")

@manage.route("/class/<id>",methods=["POST","GET"]) #班级信息
@login_required
@permission_required(Permission.publish_job)
def student_info(id):
    #end为当前日期的后一天
    end=datetime.datetime.now()
    start=end-datetime.timedelta(days=7)
    job_name=""
    if TeachingRelationship.query.filter(TeachingRelationship.class_id==id,TeachingRelationship.teacher_id==current_user.id,TeachingRelationship.subject=='班主任').first() is not None:
        subject_="全部"
    else:
        subject_=current_user.subject
    if request.method=="POST":
        start=request.form.get("start")
        end=request.form.get("end")
        job_name=request.form.get("job_name")
        subject_=request.form.get("subject")
        if not job_name:
            job_name=""
        id=request.form.get("class_id")  
    t_info=TeachingRelationship.query.filter(TeachingRelationship.class_id==id,TeachingRelationship.teacher_id==current_user.id).first()
    if not t_info:
        flash("您没有权限查看该班级的学生信息")
        return("您没有权限查看该班级的学生信息")
    class_=db.session.query(ClassInfo).filter(ClassInfo.id==id).first()
    sub=[]
    t=TeachingRelationship.query.filter(TeachingRelationship.class_id==id,TeachingRelationship.teacher_id==current_user.id,TeachingRelationship.subject=='班主任').first()
    if t is not None:
        sub.append("全部")
        tl=TeachingRelationship.query.filter(TeachingRelationship.class_id==id)
        for i in tl:
            if i.subject not in sub and i.subject!='班主任':
                sub.append(i.subject)
    else:
        sub.append(current_user.subject)
    stu=Student.query.join(ClassStudent,Student.id==ClassStudent.student_id).filter(ClassStudent.class_id==id).all()
    #查找时间段内,所任教学科布置给该班级的学生的作业
    job_=Job.query.join(JobClass).filter(Job.job_name.like("%"+str(job_name)+"%"),JobClass.class_id == id,JobClass.date.between(start,end))
    if subject_!="全部":
        job_=job_.filter(Job.subject==subject_)
    job_=job_.all()
    table=[]
    for s in stu:
        dict={}
        dict["name"]=s.realname
        dict["number"]=s.number
        dict["username"]=s.username
        dict["id"]  = s.id
        dict["leave"]=Attendance.query.filter(Attendance.student_id==s.id,or_(Attendance.start_time>=start,Attendance.end_time<=end)).count()
        jobs_ids = [i.id for i in job_]
        if jobs_ids:
            unsubmitted_jobs = JobStudent.query.filter(JobStudent.job_id.in_(jobs_ids),
                                                      JobStudent.student_id==s.id,
                                                      JobStudent.submit_time==None).count()
            dict["未交作业"] = unsubmitted_jobs
        else:
            dict["未交作业"] = 0
        #平均得分率为每个作业的得分，除以该作业的总分，再求平均值，每个作业的总分在job表中的total字段
        scores = []
        for j in job_:
            job_student_ = JobStudent.query.filter(JobStudent.job_id==j.id, JobStudent.student_id==s.id).first()
            
            if job_student_ is not None  and job_student_.mark is not None and j.total1:
                scores.append(job_student_.mark / j.total1)
        dict["平均得分率"] = round(sum(scores) / len(scores)*100,2) if scores else 0
        table.append(dict)
    df=pd.DataFrame(table)
    #如果df不为空，根据平均得分率降序排序
    if not df.empty:
        df=df.sort_values(by="平均得分率",ascending=False)
    unique_classes = {}
    unique_classes[int(id)] = class_.class_name
    for taught_class in current_user.taught_classes:
        if taught_class.class_id not in unique_classes:
            unique_classes[taught_class.class_id] = taught_class.class_info.class_name

    return(render_template("/manage/class.html",unique_classes=unique_classes,sub=sub,class_=class_,df=df,jobs=len(job_)))


@manage.route("/get_qrcode/",methods=["GET", "POST"])
@login_required
@permission_required(Permission.publish_job)
def genarate_qrcode():
    if request.method=="POST":
        msg=request.json.get("msg")
        class_id,subject_=msg.split("|")
        #获取当前服务器地址
        url=request.host_url
        url=url+"join_class/"+class_id+"/"+subject_+"/f"
        print (url)

        qr=qrcode.make(url)
        #将二维码以base64编码返回给前端显示
        buffered = BytesIO()
        qr.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return jsonify(img_str)

@manage.route("/get_teachers/",methods=["GET", "POST"])
@login_required
@permission_required(Permission.publish_job)
def get_teacher():
    if request.method=="POST":
        subject=request.json.get("subject")
        teachers=Teacher.query.filter(Teacher.subject==subject,Teacher.school_id==current_user.school_id,Teacher.school_id!=None).all()
        teacher=[]
        for i in teachers:
            teacher.append([i.realname,i.id])       
        return(jsonify(teacher))
    

@manage.route("/get_classes/",methods=["GET", "POST"])
@login_required
@permission_required(Permission.publish_job)
def get_class():
    if request.method=="POST":
        gd=request.json.get("grade")
        classes=ClassInfo.query.join(GradeInfo).filter(GradeInfo.id==gd).all()
        class_=[]
        for i in classes:
            class_.append([i.class_name,i.id])       
        return(jsonify(class_))

@manage.route('/join_class/<class_id>/<subject_>/<user_id>/', methods=['GET', 'POST'])
@login_required
@permission_required(Permission.publish_job)
def join_class(class_id,subject_,user_id):
    #如果用户未登录，跳转到登录页面
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if user_id =="f":
        user_id=current_user.id
    class_=ClassInfo.query.filter(ClassInfo.id==class_id).first()
    if class_ is None:
        msg="班级不存在,请联系班主任"
        
    else:
        us=User.query.filter(User.id==user_id).first()
        if us is None:
            msg="用户不存在,请登录或联系班主任"
        else:
            if  subject_!=us.subject:
               msg="学科检测不正确，请联系班主任"
        
            else:
                tl=TeachingRelationship.query.filter(TeachingRelationship.class_id==class_id,TeachingRelationship.teacher_id==user_id,TeachingRelationship.subject==subject_).first()
                if tl is None:
                    tl=TeachingRelationship(class_id=class_id,teacher_id=user_id,subject=subject_)
                    db.session.add(tl)
                    db.session.commit()
                    msg="加入班级成功"
                else:
                    msg=f"{us.realname}已加入{class_.class_name}，无需重复操作"
    
    return(msg)

@manage.route("/delete_student/",methods=["GET", "POST"])
@login_required
@permission_required(Permission.create_class)
def delete_student():
    if request.method=="POST":
        id=request.form.get("id")
        student=ClassStudent.query.filter(ClassStudent.student_id==id).first()
        db.session.delete(student)
        db.session.commit()
        return("删除成功")