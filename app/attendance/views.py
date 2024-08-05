from flask import session,render_template, redirect, request, url_for, flash,jsonify
from flask_login import login_user,logout_user,login_required
from . import attendance_manage
import time
from flask_login import current_user,login_user
from ..decorators import permission_required
from ..models import Permission,ClassInfo,ClassStudent,Attendance,Teacher,Student,TeachingRelationship
from .forms import attendanceForm
from .. import db
import time
from flask_paginate import Pagination, get_page_parameter
from pyecharts import options as opts
from pyecharts.charts import Bar,Line,WordCloud
import datetime


@attendance_manage.route("/",methods=["GET","POST"])
@login_required
def index():
    if current_user.role.role=="student":
        return redirect(url_for("attendance_manage.filing"))
    if current_user.role.has_permission(Permission.create_class):
        q = request.args.get('q')
        if q:
            search = True
        page = request.args.get(get_page_parameter(), type=int, default=1)
        start = (page-1)*10
        end =page*10
        #找出当前用户担任班主任的所有班级的所有学生的考勤
        teacher_id=Teacher.query.filter(Teacher.id==current_user.id).first().id
        attend=Attendance.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(TeachingRelationship.teacher_id==current_user.id,TeachingRelationship.subject=="班主任")
        if request.method =="POST":
            type_=request.form["type_"]
            if type_!="全部":
                attend=attend.filter(Attendance.leave_type==type_)
        #筛选出今天请假的记录,现在时间在请假开始时间和结束时间之间的记录
        leaves = attend.filter(Attendance.status==1).filter( Attendance.start_time <= time.strftime("%Y-%m-%d %H:%M:%S",time.localtime())).filter(Attendance.end_time >= time.strftime("%Y-%m-%d %H:%M:%S",time.localtime())).all()
        count=Student.query.join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(TeachingRelationship.teacher_id==current_user.id,TeachingRelationship.subject=="班主任").filter(ClassInfo.id==ClassStudent.class_id).distinct().count()
        pagination=Pagination(page=1,total=attend.count(),per_page=10,error_out=True)
        #近七天每天的请假人数
        seven={}
        now=time.time()
        for i in range(6,-1,-1):
            date=time.strftime("%Y-%m-%d",time.localtime(now-86400*i))
            seven[date]=attend.filter(Attendance.start_time <= time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(now-86400*i))).filter(Attendance.end_time >= time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(now-86400*i))).distinct().count()
        #使用pecharts绘制柱形图,宽高自适应
        bar = Line(init_opts=opts.InitOpts(width="100%", height="100%"))
        bar.add_xaxis(list(seven.keys()))
        bar.add_yaxis("请假人数",list(seven.values()))
        #x轴标签倾斜45度
        bar.set_series_opts(label_opts=opts.LabelOpts(rotate=45))
        #x轴倒序
        bar.set_global_opts(xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-45)))
        #bar.set_global_opts(title_opts=opts.TitleOpts(title="近七天请假人数"))
        #渲染图表，返回给前端显示
        bar = bar.render_embed()
        #找出请假次数前十的学生
        count10 = attend.filter(Attendance.status == 1).group_by(Attendance.student_id).order_by(Attendance.student_id).limit(10).all()
        stu10 = {}
        for i in count10:
            for i in count10:
                if i.student.attendances is not None:
                    stu10[i.student.realname] = len(i.student.attendances)
                else:
                    stu10[i.student.realname] = 0 
        #渲染前十名请假人数
        bar10 = Bar(init_opts=opts.InitOpts(width="100%", height="100%"))
        bar10.add_xaxis(list(stu10.keys()))
        bar10.add_yaxis("请假次数",list(stu10.values()))
        bar10.set_global_opts(xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-45)))
        bar10 = bar10.render_embed()
        #找出请假最多的前十个理由
        reason10=attend.filter(Attendance.status==1).group_by(Attendance.reason).order_by(Attendance.reason).limit(10).all()
        reason=[]
        for i in reason10:
            reason.append((i.reason,attend.filter(Attendance.reason==i.reason).distinct().count()))
        #创建请假理由词云图
        wordcloud = WordCloud(init_opts=opts.InitOpts(width="100%", height="100%"))
        wordcloud.add("", reason)
        #wordcloud.set_global_opts(title_opts=opts.TitleOpts(title="请假理由"))
        #设置图例
        wordcloud.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
        wordcloud = wordcloud.render_embed()
    return render_template("Attendance/index.html",attend=attend[start:end],wordcloud=wordcloud,bar10=bar10,bar=bar,pagination=pagination,leave=leaves,count=count)

@attendance_manage.route("/filing", methods=["POST", "GET"])
@login_required
def filing():
    if current_user.role.role!="student":
        return redirect(url_for("Attendance.index"))    
    id=current_user.id
    if request.method == "POST":        
        reason = request.form.get("reason")
        type_=request.form.get("type_")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        if reason=="其他":
            reason = request.form.get("other")
        now=datetime.datetime.now()
        att=Attendance.query.filter(Attendance.student_id==id,Attendance.start_time<=now,Attendance.end_time>=now,Attendance.leave_type==type_).first()
        if att is not None:
            flash("您已经提交过请假申请", "error")
            return redirect(url_for("attendance.filing"))
        att=Attendance(student_id=id,reason=reason,start_time=start_time,end_time=end_time,status=0,leave_type=type_)
        db.session.add(att)
        db.session.commit()
        return redirect(url_for("attendance.filing"))
    else:               
        att=Attendance.query.filter_by(student_id=id).all()
        
        cla=ClassInfo.query.join(ClassStudent).filter(ClassStudent.student_id==current_user.id).filter(ClassInfo.attribute=="行政班").first()
        if cla is None:
            flash("请联系老师加入班级", "error")
            return("404.html", 404)
        records = Attendance.query.filter_by(student_id=id).all()        
    return render_template("Attendance/filing.html",name=current_user.realname,className=cla.class_name,att=att,form=attendanceForm(),records=records)

@attendance_manage.route("/audit", methods=["POST", "GET"])
@login_required
@permission_required(Permission.attendance_management)
def audit():
    status = request.form.get("status")
    id = request.form.get("id")
    att = Attendance.query.filter_by(id=id).first()
    if status == "0":
        db.session.delete(att)
    elif status == "1":
        att.status = 1
    elif status == "2":
        att.status = 2
    db.session.commit()
    return "success"

@attendance_manage.route("/personal_attendance/", methods=["POST", "GET"])
@login_required
def personal_attendance():
    user_id=request.args.get("user_id")
    days=request.args.get("days")
    end=datetime.datetime.now()
    start=end-datetime.timedelta(days=int(days))
    attendance=Attendance.query.filter_by(student_id=user_id).filter(Attendance.end_time>start)
    dict={}
    access=attendance.filter(Attendance.status==1)
    refuse=attendance.filter(Attendance.status==2)
    dict["已同意"]=[access.filter(Attendance.leave_type=="离校").count(),access.filter(Attendance.leave_type=="跑操请假").count(),access.filter(Attendance.leave_type=="体育课请假").count()]
    dict["未通过"]=[refuse.filter(Attendance.leave_type=="离校").count(),refuse.filter(Attendance.leave_type=="跑操请假").count(),refuse.filter(Attendance.leave_type=="体育课请假").count()]
    #用pyechats绘制堆叠柱形图，x轴为全部，离校，跑操请假，体育课请假，y轴为人数
    bar = Bar(init_opts=opts.InitOpts(width="100%", height="100%"))
    bar.add_xaxis(["离校","跑操请假","体育课请假"])
    bar.add_yaxis("已同意", dict["已同意"],stack="stack1")
    bar.add_yaxis("被拒绝", dict["未通过"],stack="stack1")
    bar.set_global_opts(title_opts=opts.TitleOpts(title="个人请假统计"))
    bar.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
    bar = bar.render_embed()
    return bar

@attendance_manage.route("/personal_attendance_wordcloud/", methods=["POST", "GET"])
@login_required
def personal_attendance_wordcloud():
    user_id=request.args.get("user_id")
    days=request.args.get("days")
    end=datetime.datetime.now()
    start=end-datetime.timedelta(days=int(days))
    attendance=Attendance.query.filter_by(student_id=user_id).filter(Attendance.end_time>=start).group_by(Attendance.reason).order_by(Attendance.reason).limit(10).all()
    reason=[]
    for i in attendance:
        reason.append([i.reason,Attendance.query.filter_by(student_id=user_id).filter(Attendance.end_time>=start).filter(Attendance.reason==i.reason).distinct().count()])
    wordcloud = WordCloud(init_opts=opts.InitOpts(width="100%", height="100%"))
    wordcloud.add("高频请假理由", reason)
    #wordcloud.set_global_opts(title_opts=opts.TitleOpts(title="请假理由"))
    #设置图例
    wordcloud.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
    wordcloud = wordcloud.render_embed()
    return wordcloud