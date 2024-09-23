from flask_paginate import Pagination, get_page_parameter
import pandas as pd
from .import job_manage
from flask import render_template, redirect, flash, request,jsonify,make_response,send_from_directory,abort,send_file,url_for
from ..models import Job, JobDetail,JobStudent,Student,JobClass,Difficult, ClassInfo,ClassStudent, TeachingRelationship,User,Permission,GradeInfo,AbnormalJob,Teacher
from .. import db
from .forms import publish
from flask_login import current_user,login_required
from sqlalchemy import func ,or_,cast,null,case
from sqlalchemy.sql import distinct, literal
import datetime
import os
from .paper import creat_paper,judge
from ..decorators import permission_required
import json
from werkzeug.utils import secure_filename
import shutil
from pyecharts.charts import Bar,Pie,HeatMap,Line,Radar,Scatter3D,Bar3D
from pyecharts import options as opts
from collections import defaultdict
from pyecharts.globals import SymbolType
from pyecharts.commons.utils import JsCode
import cv2
import base64
import mammoth
import itertools
import time
import numpy as np
from PIL import Image
import io
import re


@job_manage.route("/",methods=["POST","GET"]) # 作业管理主页教师页面为作业情况，学生页面为学生个人信息
@login_required 
def job_mg():
    if current_user.role.role=="student": # type: ignore
        return (redirect("/manage/student/%s" %current_user.student.id)) # type: ignore
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    p = publish()
    search = False  # 分页切片，flask_paginate模块实现
    q = request.args.get('q')
    if q:
        search = True
    page = request.args.get(get_page_parameter(), type=int, default=1)
    start = (page-1)*10
    end =page*10
    count={}
    count1={}
    g=[]
    if  current_user.role.has_permission(255):             
        jobs=Job.query.order_by(Job.publish_time.desc())              
    elif current_user.role.has_permission(Permission.create_grade):
        jobs = Job.query.filter(Job.subject==current_user.subject).order_by(Job.publish_time.desc())
        g=GradeInfo.query.filter( GradeInfo.academic_year>=datetime.datetime.now().year).order_by(GradeInfo.academic_year.desc()).all()      
    elif  current_user.role.has_permission(Permission.publish_job):
        try:        
            # 查询用户所发布的作业
            published_jobs = db.session.query(
                Job.id.label('job_id'),
                Job.publish_time.label('sort_date'),
                null().label('job_class_date')
            ).filter(
                Job.subject == current_user.subject,
                Job.publisher == current_user.id
            )

            # 查询用户所任教班级的相关作业
            teaching_jobs = db.session.query(
                Job.id.label('job_id'),
                Job.publish_time.label('sort_date'),
                JobClass.date.label('job_class_date')
            ).join(JobClass)\
                .join(ClassInfo)\
                .join(TeachingRelationship)\
                .filter(Job.subject == current_user.subject)\
                .filter(TeachingRelationship.teacher_id == current_user.id)
            # 合并查询结果
            combined_jobs = published_jobs.union_all(teaching_jobs).subquery()
            # 使用窗口函数去重并排序
            ranked_jobs = db.session.query(
                combined_jobs.c.job_id,
                combined_jobs.c.sort_date,
                combined_jobs.c.job_class_date,
                func.row_number().over(
                    partition_by=combined_jobs.c.job_id,
                    order_by=case(
                        (combined_jobs.c.job_class_date != None, combined_jobs.c.job_class_date),
                        else_=combined_jobs.c.sort_date
                    ).desc()
                ).label('rank')
            ).subquery()

            # 选择排名为1的作业（去重后的作业）
            distinct_jobs = db.session.query(ranked_jobs).filter(ranked_jobs.c.rank == 1).subquery()

            # 获取最终的作业记录，并按指定的字段排序
            jobs = db.session.query(Job).join(distinct_jobs, Job.id == distinct_jobs.c.job_id).order_by(
                case(
                    (distinct_jobs.c.job_class_date != None, distinct_jobs.c.job_class_date),
                    else_=distinct_jobs.c.sort_date
                ).desc()
            ).all()
        except Exception as e:
            print(e)
            return(render_template("404.html",errors="没有任教班级"))   
    #class__=current_user.teacher.TeachingRelationship.order_by(TeachingRelationship.class_id.asc())    
    pagination = Pagination(page=page, total=len(jobs), bs_version=4, search=search, record_name='Job')
    for i in jobs:  
                 
        a=os.path.join(os.getcwd(),"app","static","job","answer",str(i.id))
        b=os.path.join(os.getcwd(),"app","static","job","job_readed",str(i.id))
        count[i.id]=len(os.listdir(a))
        count1[i.id]=len(os.listdir(b))    
    return(render_template("job/mainpage.html", p=p,jobs=jobs[start:end] ,count=count,count1=count1,Permission=Permission,subjects=["语文","数学","外语","政治","历史","地理","物理","化学","生物","通用技术","信息技术"],pagination=pagination))

@job_manage.route("/search_job/<name>",methods=["POST","GET"]) # 作业管理主页教师页面为作业情况，学生页面为学生个人信息
@login_required 
def search_job(name):
    search = False  # 分页切片，flask_paginate模块实现
    q = request.args.get('q')
    if q:
        search = True
    page = request.args.get(get_page_parameter(), type=int, default=1)
    start = (page-1)*10
    end =page*10
    if name!="all":
        if current_user.role.has_permission(Permission.job_grade):
            jobs=Job.query.filter(Job.job_name.like("%"+name+"%")).filter(Job.subject==current_user.subject).order_by(Job.publish_time.desc())
        elif current_user.role.has_permission(Permission.publish_job):
            jobs=Job.query.join(JobClass)\
                    .join(ClassInfo).join(TeachingRelationship)\
                    .filter(Job.subject==current_user.subject)\
                    .filter(or_(Job.publisher==current_user.id,TeachingRelationship.teacher_id==current_user.id))\
                        .order_by(Job.publish_time.desc()).filter(Job.job_name.like("%"+name+"%"))   
    else:
        if current_user.role.has_permission(Permission.job_grade):
            jobs=Job.query.filter(Job.subject==current_user.subject).order_by(Job.publish_time.desc())
        elif current_user.role.has_permission(Permission.publish_job):
            jobs=Job.query.join(JobClass)\
                    .join(ClassInfo).join(TeachingRelationship)\
                    .filter(Job.subject==current_user.subject)\
                    .filter(or_(Job.publisher==current_user.id,TeachingRelationship.teacher_id==current_user.id))\
                        .order_by(Job.publish_time.desc())
    count={}
    count1={}
    p = publish()
    pagination = Pagination(page=page, total=len(jobs.all()), bs_version=4, search=search, record_name='Job')
    for i in jobs:            
        a=os.path.join(os.getcwd(),"app","static","job","answer",str(i.id))
        b=os.path.join(os.getcwd(),"app","static","job","job_readed",str(i.id))
        count[i.id]=len(os.listdir(a))
        count1[i.id]=len(os.listdir(b))    
    return(render_template("job/mainpage.html", p=p,pagination =pagination,jobs=jobs.all()[start:end],count=count,count1=count1,Permission=Permission,subjects=["语文","数学","外语","政治","历史","地理","物理","化学","生物","通用技术","信息技术"]))

@job_manage.route("/stu/<id>",methods=["POST","GET"]) # 学生个人作业情况
def stu_job(id):
    jobs=JobDetail.query.filter(JobDetail.student_number==id).all()
    return(render_template("job/stu_job.html",jobs=jobs))

@job_manage.route("/assign_job/<id>",methods=["POST","GET"])
@login_required 
@permission_required(Permission.publish_job)
def assign_job(id):
    if request.method=="GET":
        classes = db.session.query(ClassInfo).join(TeachingRelationship).filter(
                    TeachingRelationship.teacher_id == current_user.id
                ).order_by(ClassInfo.class_name.asc()).all()
        class_={}
        g1={}
        for i in classes:
            if JobClass.query.filter(JobClass.class_id==i.id).filter(JobClass.job_id==id).first():
                class_["%s-%s"%(i.id,i.class_name)]=True
            else:
                class_["%s-%s"%(i.id,i.class_name)]=False
        if current_user.role.role=="HeadSubject":
            g =GradeInfo.query.filter(GradeInfo.academic_year>datetime.datetime.now().year)
            for i in g:
                g1[i.id]=i.grade_name       
        return jsonify(class_,g1)
    if request.method=="POST":
        data=json.loads(request.form.get("list"))
        n=0
        for i in data:            
            j_c=JobClass.query.filter(JobClass.class_id==i[0]).filter(JobClass.job_id==int(id)).first()
            if i[1]==True:                
                if not j_c:
                    n+=1
                    j_c=JobClass(class_id=int(i[0]),job_id=int(id))
                    db.session.add(j_c)                    
                    students=ClassInfo.query.filter(ClassInfo.id==int(i[0])).first().students
                    for j in students:
                        if not JobStudent.query.filter(JobStudent.job_id==int(id),JobStudent.student_id==j.student.id).first():
                            j_stu=JobStudent(job_id=int(id),student_id=j.student.id)
                            db.session.add(j_stu)
            else:
                if j_c:
                    db.session.delete(j_c)                    
        db.session.flush()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return(jsonify("添加失败"))
        return(jsonify("添加了%s个班级的作业" %n))
@job_manage.route("/resetJob/",methods=["POST","GET"])  # 重置作业
@login_required
@permission_required(Permission.publish_job)
def resetJob():
    if request.method=="POST":
        job_id=request.form.get("id")
        job_=Job.query.filter(Job.id==job_id).first()
        if not job_:
            return(jsonify("作业不存在"))
        jt=JobStudent.query.filter(JobStudent.job_id==job_id).all()
        j_c=JobClass.query.filter(JobClass.job_id==job_id).all()
        for i in j_c:
            i.max=None
            i.min=None
            i.average=None
            i.submit_number=None
            i.std=None
        for i in jt:
            j_d=JobDetail.query.filter(JobDetail.job_id==job_id,JobDetail.student_id==i.student_id).all()
            for k in j_d:
                db.session.delete(k)
            i.submit_time=None
            i.select_mark=None
            i.complete_mark=None
        ab=AbnormalJob.query.filter(AbnormalJob.job_id==job_id).all()
        for i in ab:
            db.session.delete(i)        
        db.session.commit()
        #删除相应作业文件夹，abnormal_paper文件夹下所有相关文件
        path=os.path.join(os.getcwd(),"app","static","job","job_readed",str(job_id))
        if os.path.exists(path):
            #删除文件夹下的所有文件
            for i in os.listdir(path):
                os.remove(os.path.join(path,i))
        path=os.path.join(os.getcwd(),"app","static","job","abnormal_paper",str(job_id))
        if os.path.exists(path):
             for i in os.listdir(path):
                os.remove(os.path.join(path,i))
        return("重置成功")
    
@job_manage.route("/exportData/",methods=["POST","GET"]) # 导出作业情况
@login_required 
@permission_required(Permission.publish_job)
def exportData():
    if request.method=="POST":
        job_id=request.get_json()["id"]               
        job_=Job.query.filter(Job.id==job_id).first()
        if not job_:
            #返回错误
            return("该作业不存在")
        data=[]
        if current_user.role.has_permission(Permission.job_grade):            
            job_stus=JobStudent.query.filter(JobStudent.job_id==job_id).all()
        else:
            job_stus = JobStudent.query.join(Student)\
            .join(ClassStudent)\
            .join(ClassInfo)\
            .join(TeachingRelationship)\
            .filter(JobStudent.job_id == job_id, TeachingRelationship.teacher_id == current_user.id).all()
        for i in job_stus:
            data.append({"班级":i.stu_.classes[0].class_name,"学号":i.student.number,"姓名":i.stu_.name,"提交时间":i.submit_time,"选择题得分":i.select_mark,"完整题得分":i.complete_mark,"总分":i.mark})          
        #将数据转换为dataframe，格式为班级列，学号列，姓名列，选择题得分，主观题得分和总分
        df=pd.DataFrame.from_records(data)
        excel_stream = io.BytesIO()
        df.to_excel(excel_stream, engine='openpyxl', index=False)
        excel_stream.seek(0)
        return send_file(excel_stream, as_attachment=True, attachment_filename="data.xlsx")

@job_manage.route("/question_statistics/", methods=["POST", "GET"])
@login_required 
@permission_required(Permission.publish_job)
def question_statistics():
    if request.method == 'POST':
        class_id = request.form.get("class_id")
        job_id = request.form.get("job_id")        
        if class_id == '0' and current_user.role.has_permission(Permission.job_grade):
            job_details = JobDetail.query.filter(JobDetail.job_id == job_id).all()
        elif class_id == "0":
            job_details = JobDetail.query.join(Student) \
                .join(ClassStudent) \
                .join(ClassInfo) \
                .join(TeachingRelationship) \
                .filter(JobDetail.job_id == job_id, TeachingRelationship.teacher_id == current_user.id).all()
        else:
            job_details = JobDetail.query.join(Student) \
                .join(ClassStudent) \
                .join(ClassInfo) \
                .filter(JobDetail.job_id == job_id, ClassInfo.id == class_id).all()
        job_ = Job.query.filter(Job.id == job_id).first()
        tags = json.loads(job_.context)
        answers = json.loads(job_.select_answer)        
        groups = defaultdict(list)
        for detail in job_details:
            groups[detail.serial_no].append(detail)
        
        groups = dict(sorted(groups.items()))
        bar_charts = []

        for serial_no, details in groups.items():
            if str(serial_no) in answers.keys():
                choices = {'A': 0, 'B': 0, 'C': 0, 'D': 0,
                           'AB': 0, 'AC': 0, 'AD': 0, 'BC': 0, 'BD': 0, 'CD': 0,
                           'ABC': 0, 'ABD': 0, 'ACD': 0, 'BCD': 0, 'ABCD': 0}
                choices_ = {'A': "", 'B': "", 'C': "", 'D': ""}
                total_num = 0

                for detail in details:
                    if detail.answer:
                        detail.answer = "".join(sorted(detail.answer))
                        total_num += 1
                        if detail.answer in choices:
                            choices[detail.answer] += 1
                        if len(detail.answer) > 1:
                            for answer in detail.answer:
                                choices[answer] += 1
                                choices_[answer] += " " + detail.student.realname
                                if len(choices_[answer].split()) % 2 == 0:
                                    choices_[answer] += "<br>"
                        else:
                            choices_[detail.answer] += " " + detail.student.realname
                            if len(choices_[detail.answer].split()) % 2 == 0:
                                choices_[detail.answer] += "<br>"

                x_data = ['A', 'B', 'C', 'D']
                correct_item = answers[str(serial_no)]
                b_num = choices[correct_item]
                b_percent = round((b_num / total_num) * 100, 1)

                if len(correct_item) == 1:
                    markpoint_opts = opts.MarkPointOpts(data=[
                        opts.MarkPointItem(value=f'{b_percent}', coord=[correct_item, choices[correct_item]], 
                                           name="正确率",
                                           itemstyle_opts=opts.ItemStyleOpts(color="#55ff37" if b_percent > 70 else 
                                                                             "#dbff5e" if b_percent > 60 else 
                                                                             "#feaf2c" if b_percent > 50 else "red"))
                    ])
                else:
                    markpoint_opts = opts.MarkPointOpts(data=[
                        opts.MarkPointItem(value=f'{round((choices[item] / total_num) * 100, 1)}', 
                                           coord=[item, choices[item]], 
                                           name="正确率",
                                           itemstyle_opts=opts.ItemStyleOpts(color="#55ff37" if round((choices[item] / total_num) * 100, 1) > 70 else 
                                                                             "#dbff5e" if round((choices[item] / total_num) * 100, 1) > 60 else 
                                                                             "#feaf2c" if round((choices[item] / total_num) * 100, 1) > 50 else "red"))
                        for item in correct_item
                    ])

                title = Difficult.query.filter(Difficult.id == tags[serial_no - 1]).first()
                if title:
                    title = title.difficult
                else:
                    title = ""

                bar_chart = (
                    Bar(init_opts=opts.InitOpts(width='150px', height='300px'))
                    .add_xaxis(x_data)
                    .add_yaxis(f'第 {serial_no}题：', [
                        {'value': choices["A"], 'text': choices_["A"]},
                        {'value': choices["B"], 'text': choices_["B"]},
                        {'value': choices["C"], 'text': choices_["C"]},
                        {'value': choices["D"], 'text': choices_["D"]}
                    ], color='#004080', markpoint_opts=markpoint_opts)
                    .set_global_opts(
                        title_opts=opts.TitleOpts(subtitle=title),
                        tooltip_opts=opts.TooltipOpts(trigger="axis", formatter=JsCode("function (params) { return params[0].data.text; }"))
                    )
                )
            else:
                mark = int(json.loads(job_.no_multiple_choice_info)[str(serial_no)]["分值"])
                bins = [x for x in range(0, mark + 1, 2)]
                if bins[-1] < mark:
                    bins.append(mark)
                label = []
                for i in range(1, len(bins)):
                    if i == 1:
                        label.append(f"<={bins[i]}")
                    else:
                        if bins[i - 1] + 1 == bins[i]:
                            label.append(str(bins[i]))
                        else:
                            label.append(f"{bins[i - 1] + 1}-{bins[i]}")

                score_range = pd.cut([job.mark for job in details if job.mark is not None], bins=bins, labels=label)
                score_counts = pd.Series(pd.Categorical(score_range, categories=label)).value_counts()
                score_percentages = [(count / len(details)) * 100 for count in score_counts]

                bar_chart = (
                    Pie(init_opts=opts.InitOpts(width='150px', height='300px'))
                    .add('', list(zip(score_counts.index.tolist(), score_percentages)))
                    .set_global_opts(
                        title_opts=opts.TitleOpts(title=f'第 {serial_no}题：', subtitle=f'{Difficult.query.filter(Difficult.id == tags[serial_no - 1]).first().difficult}'),
                        legend_opts=opts.LegendOpts(pos_right='right')
                    )
                    .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {d}%"))
                )

            bar_charts.append(bar_chart)

        bar_html_list = [chart.render_embed() for chart in bar_charts]
        return json.dumps(bar_html_list)


def job_sub(submist_list):
    pass

@job_manage.route("/job_info/<job_id>", methods=["POST", "GET"])
@login_required 
@permission_required(Permission.publish_job)
def job_info(job_id):
    update_ClassInfo(job_id)
    mode = 0
    job_ = Job.query.filter(Job.id == job_id).first()
    if not job_ or job_.subject != current_user.subject:
        return "该作业不存在或你没有查看该作业的权限"

    select_answer = json.loads(job_.select_answer)
    no_select_infor = json.loads(job_.no_multiple_choice_info)

    if current_user.role.has_permission(Permission.job_grade):
        classes_ = JobClass.query.filter(JobClass.job_id == job_id).order_by(JobClass.class_id.asc()).all()
    else:
        classes_ = db.session.query(JobClass) \
            .join(TeachingRelationship, TeachingRelationship.class_id == JobClass.class_id) \
            .join(Teacher, Teacher.id == TeachingRelationship.teacher_id) \
            .filter(Teacher.id == current_user.id, JobClass.job_id == job_id) \
            .order_by(cast(JobClass.class_id, db.Integer).asc()) \
            .all()

    if not classes_:
        flash("作业%s没有布置给你的任教班级" % job_.job_name)
        return redirect(url_for("job.job_mg"))

    if request.method == "POST":
        class_id = request.form.get("class_id")
        mode = request.form.get("mod")
        class_ = ClassInfo.query.filter(ClassInfo.id == class_id).first()
        j_c = JobClass.query.filter(JobClass.job_id == job_id, JobClass.class_id == class_id).first()
    else:
        class_ = ClassInfo.query.filter(ClassInfo.id == classes_[0].class_id).first()
        j_c = JobClass.query.filter(JobClass.job_id == job_id, JobClass.class_id == classes_[0].class_id).first()

    if class_:
        jobs = db.session.query(JobStudent).join(Student).join(ClassStudent).filter(
            ClassStudent.class_id == class_.id,
            JobStudent.job_id == job_id
        ).order_by(
            cast(JobStudent.mark, db.Float).desc()
        ).all()
    else:
        jobs = []
    
    sum_ = job_.total1
    f = len([j.mark for j in jobs if j.select_mark is None])    
    class_names = [data.classes.class_name for data in classes_ if data]
    max_scores = [data.max for data in classes_ if data.max is not None]
    min_scores = [data.min for data in classes_ if data.min is not None]
    avg_scores = [data.average for data in classes_ if data.average is not None]
    
    bar = (
        Bar(init_opts=opts.InitOpts(width="100%", height="100%"))
        .add_xaxis(class_names)
        .add_yaxis("最高分", max_scores)
        .add_yaxis("最低分", min_scores)
        .add_yaxis("平均分", avg_scores)
        .set_series_opts(
            label_opts=opts.LabelOpts(is_show=False),
            markline_opts=opts.MarkLineOpts(data=[opts.MarkLineItem(type_="average")]),
        )
        .set_global_opts(
           
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-15)),
            yaxis_opts=opts.AxisOpts(min_=0, max_=sum_),
        )
    )
    
    js = {}
    answers_dict = {}
    dict_ = {"A": 0, "B": 1, "C": 2, "D": 3,"AB":4,"AC":5,"AD":6,"BC":7,"BD":8,"CD":9,"ABC":10,"ABD":11,"ACD":12,"BCD":13,"ABCD":14}
    for i in jobs:
        jt = JobDetail.query.filter(JobDetail.job_id == i.job_id, JobDetail.student_id == i.student_id)
        data = {
            "number": str(i.student.number),
            "name": i.student.realname,
            "id": i.student.id
        }
        data1 = []
        for j in select_answer.keys():
            jt_ = jt.filter(JobDetail.serial_no == j).first()
            if jt_:
                #对jt_.anser进行排序
                t = "".join(sorted(jt_.answer))

                data[j] = t
                if jt_.mark is not None and jt_.mark >0:
                    data1.append(15)
                    continue  # 正确答案，跳过相似度计算
                else:
                    data1.append(dict_[t])  # 错误答案，保留用于相似度计算
            else:
                continue  # 没有回答，跳过相似度计算

        for j in no_select_infor.keys():
            jt_ = jt.filter(JobDetail.serial_no == j).first()
            
            if jt_:
                data[j] = jt_.mark
            else:
                data[j] = None

        data["select_mark"] = i.select_mark
        data["complete_mark"] = i.complete_mark
        data["mark"] = i.mark
        js[i.id] = data
        answers_dict[i.id] = data1

    df = pd.DataFrame.from_dict(answers_dict, orient='index')
    heat = ""
    if mode == "1" and not df.empty:
        df2 = df.T
        similarity = df2.corr(method='pearson')
        similar_pairs = []
        x = []
        y = []
        for i in range(len(similarity)):
            for j in range(i + 1, len(similarity)):
                if similarity.iloc[i, j] >= 0.59:
                    
                    if js[similarity.index[i]]["name"] not in x:
                        x.append(js[similarity.index[i]]["name"])
                    if js[similarity.columns[j]]["name"] not in y:
                        y.append(js[similarity.columns[j]]["name"])
                    similar_pairs.append([js[similarity.index[i]]["name"], js[similarity.columns[j]]["name"], similarity.iloc[i, j]])
        c = (
            HeatMap(init_opts=opts.InitOpts(width="100%", height="600px"))
            .add_xaxis(x)
            .add_yaxis("相似度", y, similar_pairs)
            .set_global_opts(
                #title_opts=opts.TitleOpts(title="《{}》学生答案相似度".format(job_.job_name)),
                visualmap_opts=opts.VisualMapOpts(max_=1, min_=0.9),
                xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-15)),
            )
            .set_series_opts(label_opts=opts.LabelOpts(is_show=False))
        )
        heat = c.render_embed()
    bar.width = "100%"
    charts = bar.render_embed()
    
    dict_ = {
        'id': job_id,
        "name": job_.job_name,
        "select": select_answer,
        "publish_time": job_.publish_time,
        "sum": sum_,
        "n_sub": f,
        'no_select': no_select_infor
    }
    
    return render_template("job/job_info.html", dict=dict_, classes_=classes_, class_=class_, js=js, df=df, j_c=j_c, charts=charts, heat=heat)


#显示学生答题卡，用于核对系统扫描阅卷结果
@job_manage.route("/show_student_card/<id_number>",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)
def show_student_card(id_number):
    job_id=id_number.split("_")[0]
    stu_id=id_number.split("_")[1]
    number=Student.query.filter(Student.id==stu_id).first().number
    job_=Job.query.filter(Job.id==job_id).first()
    if not job_:
        return(render_template("404.html",errors="该作业不存在"))
    path=os.path.join(os.getcwd(),"app","static","job","job_readed","%s" %job_id,"%s.png" %number)
    answers={}
    if os.path.exists(path):
        try:
            #打开作业标准答题卡
            original= judge.open_answer_card(os.path.join(os.getcwd(),"app","static","job","answerCard",job_.paper_url))
            #打开学生答题卡
            img= judge.open_student_card(path)
            n=judge.n
            #调整图片
            img=judge.paper_ajust(original,img)
            if img is None:

               return(render_template("404.html", errors="找不到答题卡，请联系管理员"))
            num=judge.number_pos(img)
            pict=judge.pict(img)
            #识别学号
            num_img=pict[16*n:36*n,27*n:67*n]
            #找出学号轮廓
            cnts,h=cv2.findContours(num_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            #调整cnts位置，匹配原图img
            cnts=[cnt+np.array([27*n,16*n]) for cnt in cnts]

            #将学号框出来并写出学号
            cv2.drawContours(img,cnts,-1,(0,0,255),2)
            cv2.putText(img,num,(int(27*n),int(13*n)),cv2.FONT_HERSHEY_COMPLEX,1,(0,0,255),2)
            #识别选择题
            multi=job_.multiple_choice_info
            multi=json.loads(multi)
            msg,answers=multiple_choice_judge(img,job_id)
            select_answer=json.loads(job_.select_answer)
            if msg!="success":
                return(render_template("404.html",errors="阅卷错误，请联系管理员"))
            for i in multi:
                posi=i["位置"]
                #根据位置信息，找出选择题的轮廓
                t=pict[posi['start']*n:posi['end']*n,6*n:77*n]
                cnts,h=cv2.findContours(t, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                #调整cnts位置，匹配原图img
                cnts=[cnt+np.array([6*n,posi['start']*n]) for cnt in cnts]
                #将选择题框出来
                cv2.drawContours(img,cnts,-1,(0,0,255),2)            
                #将答案写到试卷上
                for j in range(i["初始题号"],i["初始题号"]+i["题目数量"]):
                    if j in answers.keys():
                        if answers[j][0]==select_answer[str(j)]:
                            cv2.putText(img,answers[j][0],((j-i["初始题号"])%4*15*n+6*n,(posi['start']+(j-i["初始题号"])//4*2)*n+n),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
                        else:
                            cv2.putText(img,answers[j][0],((j-i["初始题号"])%4*15*n+6*n,(posi['start']+(j-i["初始题号"])//4*2)*n+n),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
                        
            #将图片转换为base64编码
            img=cv2.imencode('.png',img)[1]
            base64_str = base64.b64encode(img)
            return (render_template("job/show_student_card.html",student_card=base64_str.decode(),answers=answers,number=num,job_id=job_id))
        except Exception as e:
            return(render_template("404.html",errors= "打开试卷错误，请检查"))
    else:
        return(render_template("404.html",errors="找不到答题卡，请联系管理员"))
#更新阅卷信息
@job_manage.route("/update/",methods=["POST","GET"]) #更新学生阅卷信息
@login_required
@permission_required(Permission.publish_job)
def update():
    if request.method=="POST":
        data=request.get_json()
        job_id=data["job_id"]
        job_=Job.query.filter(Job.id==job_id).first()
        number=data["student_id"]
        msg=check_student_number(number,job_.id)
        print(msg)
        if msg[0]!="success" and "重复阅卷" not in msg[0]:
            return(msg)
        student_id=int(msg[1])
        #job_student_=JobStudent.query.filter(JobStudent.job_id==job_id,JobStudent.student_id==student_id).first()
        answers=data["answers"]
        update_select_info(student_id,job_id,answers)
        update_ClassInfo(job_id)
        return("success")
    else:
        return("没有提交数据")
        
@job_manage.route("/show_paper/<url>",methods=["POST","GET"]) #显示问卷
@login_required 
@permission_required(Permission.publish_job)
def show_paper(url):
    filename=os.path.join(os.getcwd(),'app',"static","job","paper",'question_paper',current_user.subject,url)
    #将filename转换为html
    with open(filename, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file)
        html = result.value
    return(render_template("job/show_paper.html",html=html,url=url))

@job_manage.route('/show_file/<path:filename>')
@login_required 
@permission_required(Permission.publish_job)
def show_file(filename):
    path=os.path.join(os.getcwd(),'app',"static","paper",'question_paper',current_user.subject)
    return send_from_directory(path,filename)

@job_manage.route("/create_paper",methods=["POST","GET"])  #
@login_required 
@permission_required(Permission.publish_job)
def create_paper():
    data={}
    data["status"]=0
    if request.method == "POST":        
        title=request.form.get("title") 
        if Job.query.filter(Job.job_name==title).first():
            data["status"]+=1
            data["%s" %data["status"]]="已存在该作业"
            return(data)
        number = request.form.get("number")        
        select = request.form.get("select")
        subtopic =request.form.get("subtopic")
        subtopic=json.loads(subtopic)
        c_mark=json.loads(request.form.get("c_mark"))            
        teacher = current_user.realname
        publish_time=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime())
        publisher=current_user.id            
        file=request.files.get("file")            
        #deadline =datetime.datetime.strptime(deadline,"/%Y/%m/%d")             
        g=request.form.get("grade") 
        g=json.loads(g)
        if current_user.role.has_permission(Permission.publish_job): 
            teacher = current_user.id
            subject=current_user.subject
        s_answer=request.form.get("answers")
        tags=request.form.get("tags")
        tags=json.loads(tags)
        r=creat_paper.paper(subject,current_user.realname,2000,title,int(select),subtopic)
        url =str(teacher)+"-"+str(time.time())+".png"
        path=os.path.join(os.getcwd(),"app","static","job","paper","excercise",url)
        if not r[-1]:
            data["status"]=1                
            data["1"]="生成答题卡失败，题目过多，超出卷面"
            return(data)                  
        r[1].save(path) 
        path=os.path.join(os.getcwd(),"app","static","job","paper","question_paper",subject) 
        if not os.path.exists(path): 
            os.makedirs(path)            
        file_ext = file.filename.rsplit('.', 1)[1] # 获取文件扩展名
        filename = title +"."+ file_ext
        path=os.path.join(path,filename)
        file.save(path)
        submit_job = Job(job_name=title,publish_time=publish_time,publisher=publisher,question_paper=filename,subject=subject,select_answer=s_answer,context=json.dumps(tags),paper_url=url,s_m=int(number),complete=json.dumps(c_mark),line=json.dumps(r[0]),select=int(select))
        db.session.add(submit_job)
        db.session.flush()
        path=os.path.join(os.getcwd(),"app","static","job","answer",str(submit_job.id))
        path1=os.path.join(os.getcwd(),"app","static","job","job_readed",str(submit_job.id))
        if not os.path.exists(path):
            os.makedirs(path)
        if not os.path.exists(path1):
            os.makedirs(path1)
        if g:
            class_list=db.session.query(ClassInfo).join(GradeInfo).filter(GradeInfo.id.in_(g)).filter(ClassInfo.attribute=="行政班").all()    
        else:          
            class_list=db.session.query(ClassInfo).filter(ClassInfo.id.in_(json.loads(request.form.get("classlist")))).all()
        #print(json.loads(request.form.get("classlist")))
        if class_list:  # 作业布置 
            for i in class_list:                    
                check_job=JobClass.query.join(Job,JobClass.job).filter(Job.job_name==title,JobClass.class_id==i.id,Job.subject==current_user.subject).first()  #避免重复布置相同作业
                if check_job:
                    data["status"]+=1
                    data["%s" %data["status"]]="%s班已经有名为《%s》的作业！" %(check_job.ClassInfo.class_name,title)
                else:
                    publish_job = JobClass(class_id=i.id,job_id=submit_job.id)
                    db.session.add(publish_job)

                    for j in i.students:
                        j_stu=JobStudent(job_id=submit_job.id,student_id=j.id)
                        db.session.add(j_stu)
        else:            
            data["status"]+=1
            data["%s" %data["status"]]="没有设置班级"
        data["url"]="/static/paper/excercise/"+url
        db.session.flush()
        db.session.commit()        
    else:
        data["status"]+=1
        data["%s" %data["status"]]="没有提交作业数据"
    return(data)

"""@job_manage.route("/genarate_paper",methods=["POST","GET"])  #
@login_required 
@permission_required(Permission.publish_job)
def genarate_paper():
    diff=difficult.query.all()
    if current_user.role.has_permission(Permission.publish_job):
        class__=current_user.teacher.TeachingRelationship.order_by(TeachingRelationship.class_id.asc())
        class_=[]
        for i in class__:
            if i.ClassInfo not in class_:
                class_.append(i.ClassInfo)
    elif current_user.role.role=="representative":
        class_.append(current_user.student.ClassInfo)
    if current_user.role.has_permission(Permission.job_grade):
        pass
    g=GradeInfo.query.all()
    return(render_template("job/genarate_paper.html",g=g,difficult=diff,class_=class_,Permission=Permission))"""

@job_manage.route("/del/",methods=["POST"])
@login_required 
@permission_required(Permission.publish_job)
def del_job():
    url=request.form.get("url")
    try:
        job_=Job.query.filter(Job.id==url.split(".")[0]).first()
        path=os.path.join(os.getcwd(),"app","static","job","paper","excercise",job_.paper_url)
        if os.path.exists(path):
            os.remove(path)
        abnormal=AbnormalJob.query.filter(AbnormalJob.job_id==job_.id).all()
        for i in abnormal:
            db.session.delete(i)
             
        db.session.delete(job_)
        db.session.flush()
        db.session.commit()
        return("已删除该作业")
    except Exception as e:
        #显示错误信息
        print(e)
        db.session.rollback()
        return("删除作业失败")

@job_manage.route("/upload/<id>",methods=["POST","GET"])  #
@login_required 
@permission_required(Permission.submit_job)
def upload_paper(id):
    if request.method == 'POST':
        if id=="all":
            url=os.path.join(os.getcwd(),"app","static","job","answer","all",str(current_user.id))
        else:       
            url=os.path.join(os.getcwd(),"app","static","job","answer",str(id))
        if not os.path.exists(url):
            os.makedirs(url)
        files = request.files.getlist("files")
        n=0
        erro_paper=[]
        for file in files:            
            filename=secure_filename(file.filename)            
            img= Image.open(file.stream)
            # 将 PIL 图像转换为 numpy 数组
            img_np = np.array(img)
            # 将 RGB 图像转换为 BGR 图像
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            img=cv2.cvtColor(img_bgr,cv2.COLOR_BGR2GRAY)
            #保存img
            save_path=os.path.join(os.getcwd(),url, filename)
            standard=judge.open_answer_card(os.path.join(os.getcwd(),"app","static","job","answerCard","%s.png" %id))
            img=judge.open_student_card(img)
            img=judge.paper_ajust(standard,img)
            if img is None:
                flash(filename+":试卷定位失败")
                erro_paper.append([filename,"试卷不能正常定位"])
                continue
            messeage=judge.qr_recognize(img,(judge.n*15,judge.n*36,judge.n*65,judge.n*82))
            if not messeage:
                #旋转180度
                img=cv2.rotate(img,cv2.ROTATE_180)
                messeage=judge.qr_recognize(img,(judge.n*15,judge.n*36,judge.n*65,judge.n*82))
                
            if messeage:
                if messeage[0].split("_")[0]!=str(id):
                    #异常卷移至abnormal_paper文件夹中
                    flash(filename+":二维码信息不匹配")
                    erro_paper.append([filename,"二维码信息不匹配"])
                    continue
            else:
                img=cv2.rotate(img,cv2.ROTATE_180)
                flash(filename+":二维码识别失败") 
                erro_paper.append([filename,"二维码识别失败"])
                
                continue
            cv2.imwrite(save_path,img)
            n+=1                            
            
        count=len(os.listdir(url))

        return(jsonify([n,count,erro_paper]))

@job_manage.route("/GetCardFromCamera/<id>",methods=["POST","GET"])  #
@login_required
@permission_required(Permission.submit_job)
def GetCardFromCamera(id):
    job_=Job.query.filter(Job.id==id).first()
    if request.method=="POST":
        url=os.path.join(os.getcwd(),"app","static","job","job_readed",str(id))
        if not os.path.exists(url):
            os.makedirs(url)       
        img=request.get_json()["image"]        
        img = re.sub('^data:image/.+;base64,', '', img)
        img=base64.b64decode(img)
        # base64解码后的图片数据转换为cv2图像
        img = Image.open(io.BytesIO(img))
        img_np = np.array(img)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        tag,img=judge.find_paper(img_bgr)
        msg=""
        if tag!=2:
            standard=judge.open_answer_card(os.path.join(os.getcwd(),"app","static", "job","answerCard",str(id)+".png"))
            img=img[judge.n*1:-judge.n*1,judge.n*1:-judge.n*1]
            img=judge.paper_ajust(standard,img)
            chWidth=judge.n
            qr=judge.qr_recognize(img,(chWidth*13,chWidth*39,chWidth*64,chWidth*82))
            if not qr:
                #旋转180度
                img=cv2.rotate(img, cv2.ROTATE_180)
                qr=judge.qr_recognize(img,(chWidth*13,chWidth*39,chWidth*64,chWidth*82))
            if not qr:                
                msg=time.strftime("%H:%M:%S") +"没有识别出二维码"
                tag=3
            else:
                if qr[0]!=id:
                    msg=time.strftime("%H:%M:%S")+"二维码不匹配，请检查答题卡是否正确："
                    tag=3
                else:
                    number=judge.number_pos(img)
                    check=check_student_number(number,id)                    
                    if check[0]=="success":   
                        stu_id=int(check[1] )  
                                       
                        choiceInfo,mark=multiple_choice_judge(img,id)
                        if choiceInfo=="success":
                            se=update_select_info(stu_id,id,mark)
                            
                            
                            j_stu = JobStudent.query.filter(
                                        JobStudent.job_id == int(id),
                                        JobStudent.student_id ==stu_id
                                    ).first()                            
                            j_stu.select_mark=se
                            j_stu.submit_time=datetime.datetime.now()
                            
                            filename=str(stu_id)+".png"
                            save_path=os.path.join(url, filename)
                            cv2.imwrite(save_path,img)
                            db.session.commit()
                        else:
                            genarate_exception_info(id,choiceInfo,save_path,number)

                        msg=time.strftime("%H:%M:%S")+"识别成功"+number+"选择题阅卷:"+choiceInfo
                        non_multiple_choice_to_read(stu_id,id) #生成非选择题阅卷信息
                    else:
                        msg=time.strftime("%H:%M:%S")+number+check                    
            #将img转换为base64编码
            img=cv2.imencode('.png',img)[1]
            img = base64.b64encode(img)
            img=img.decode()
        else:
            msg=time.strftime("%Y-%m-%d %H:%M:%S") +"没有找到试卷，请重试"
            img=""
        return(jsonify(tag,img,msg))
    return(render_template("job/camera.html",id=id,name=job_.job_name))
@job_manage.route("/detect_paper/",methods=["POST","GET"]) 
def detect_paper():
    if request.method=="POST":
        #获取前端传来的图片
        img=request.get_json()["image"]
        id=request.get_json()["id"]
        job_=Job.query.filter(Job.id==id).first()
        standard = judge.open_answer_card(os.path.join(os.getcwd(),"app","static","job","answerCard",str(id)+".png")) 
        img = re.sub('^data:image/.+;base64,', '', img)
        img=base64.b64decode(img)
        # base64解码后的图片数据转换为cv2图像
        img = Image.open(io.BytesIO(img))
        img_np = np.array(img)
        img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        img=judge.paper_ajust(standard,img)
        number=judge.number_pos(img)        
        if number=="0":
            return(jsonify(0,"没有找到学号"))
        url=os.path.join(os.getcwd(),"app","static","job","answer",id)
        if not os.path.exists(url):
            os.makedirs(url)
        filename=str(number)+".png"
        #保存图片,文件名为时间戳
        url=os.path.join(url, filename)
        if  not os.path.exists(url):            
            cv2.imwrite(url, img)
            return(jsonify(job_.job_name ,number))
        else:
            return(jsonify(0,"重复上传"))
    return(render_template("job/detect_paper.html"))
@job_manage.route("/judge/<id>",methods=["POST","GET"]) #阅卷主程序
@login_required 
@permission_required(Permission.submit_job)
def job_judge(id):
    path=os.path.join(os.getcwd(),"app","static","job","answer",str(id))
    #遍历path文件夹下的所有文件
    files=os.listdir(path)
    n=0
    print(path)
    #如果path文件夹下没有文件，则返回
    if not files:
        print("没有找到该试卷的答题卡")
        return
    for i in files:
        #获取文件的绝对路径
        file=os.path.join(path,i)
        #判断是否是文件夹
        path1=os.path.join(os.getcwd(),"app","static","job","abnormal_paper",str(id))
        if not os.path.exists(path1):
            os.makedirs(path1)
        if not os.path.isdir(file):
            standard=judge.open_answer_card(os.path.join(os.getcwd(),"app","static","job","answerCard","%s.png" %id))
            img=judge.open_student_card(file)
            if img is None:
                print("没有找到该试卷的答题卡")
                continue
            img=judge.paper_ajust(standard,img)
            if img is None:
                print("答题卡与试卷不匹配")
                continue
            
            number=judge.number_pos(img)  
            print(number)          
            msg=check_student_number(number,id)          
            if msg[0]!="success":
                print(msg)
                #将异常卷的信息存入abnormal_job表中
                try:
                    #如果msg是元组
                    if isinstance(msg,tuple):
                       
                        msg=msg[0]
                    #将异常卷的信息存入abnormal_job表中
                    ab=AbnormalJob(job_id=int(id),paper=i,number=number,reason=msg,teacher_id=current_user.id)
                    db.session.add(ab)               
                    #将异常卷移至abnormal_paper文件夹中
                    os.rename(file,os.path.join(path1,i))
                    db.session.commit()
                except Exception as e:
                    print(e)
                    db.session.rollback()

                    continue
            else:
                stu_id=int(msg[1])
                msg1,mark=multiple_choice_judge(img,id)
                if msg1!="success":
                    ab=AbnormalJob(job_id=id,paper=i,number=number,reason=msg1,teacher_id=current_user.id)
                    db.session.add(ab)                    
                    #将异常卷移至abnormal_paper文件夹中
                    os.rename(file,os.path.join(path1,i))
                    db.session.commit()
                    if msg1=="作业不存在":
                        print("作业不存在")
                        continue                
                se=update_select_info(stu_id,id,mark)
                j_stu = JobStudent.query.filter(
                        JobStudent.job_id == int(id),
                        JobStudent.student_id == stu_id
                    ).first() 
                j_stu.select_mark=se
                j_stu.submit_time=datetime.datetime.now()
                n+=1
            #将已经阅卷的卷子移至job_readed文件夹中,并修改文件名            
            if msg[0]=="success" and msg1=="success":
                path1=os.path.join(os.getcwd(),"app","static","job","job_readed",str(id))
                if not os.path.exists(path1):
                    os.makedirs(path1)
                path2=os.path.join(path1,str(number)+".png")                  
                os.rename(file,path2)
            #生成非选择题阅卷信息
            non_multiple_choice_to_read(number,id)
    update_ClassInfo(id)
    db.session.commit()
    return(jsonify("成功阅卷%s份" %n))

@job_manage.route("/show_answer/<id>",methods=["POST","GET"]) #
@login_required 
@permission_required(Permission.publish_job)
def show_answer(id):
    #获取前端以get方式传来的json数据
    data=request.get_json()
    #获取密码
    password=data["password"]
    #验证密码是否正确
    if current_user.verify_password(password):       
        job_=Job.query.filter(Job.id==id).first().select_answer
        return jsonify(job_)
    else:
        return(jsonify("erro"))

@job_manage.route("/get_cpl_title_number/",methods=["POST","GET"]) #
@login_required 
@permission_required(Permission.publish_job)
def get_title_number():
    if request.method=="POST":
        id=request.form.get("id")
        j=Job.query.filter(Job.id==id).first()
        if not j:
            return("没有该作业")
        cpl=json.loads(j.no_multiple_choice_info)
        title_number=[]
        for k in cpl.keys():
            title_number.append(k)        
        return(jsonify(title_number))


@job_manage.route("/cpl_judge/",methods=["POST","GET"]) #填空题阅卷
@login_required 
@permission_required(Permission.publish_job)
def cpl_judge():
    if request.method=="POST":
        id=request.form.get("id")
        title_number=request.form.get("title_number")
        stu=request.form.get("stu")
        j=Job.query.filter(Job.id==id).first()    
        if not j:
            return("没有该作业")        
        if not stu:
            j_detail=JobDetail.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship)\
                .filter(JobDetail.job_id==id)\
                .filter(JobDetail.student_id==Student.id)\
                .filter(Student.id==ClassStudent.student_id)\
                .filter(ClassStudent.class_id==ClassInfo.id)\
                .filter(ClassInfo.id==TeachingRelationship.class_id)\
                .filter(TeachingRelationship.teacher_id==current_user.id)\
                .filter(JobDetail.serial_no==title_number,JobDetail.mark==None)\
                .order_by(JobDetail.serial_no).first()
        else:
            #如果stu是汉字
            if re.match(r"[\u4e00-\u9fa5]+",stu):
                stu=Student.query.filter(Student.realname==stu).first()
            else:
                stu=Student.query.filter(Student.number==stu).first()
            if stu:
            #找出job_detail的 job_id==id,serial_no==title_number的记录中，student like stu或者 stu.realname like stu的记录
                j_detail=JobDetail.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship)\
                    .filter(JobDetail.job_id==id)\
                    .filter(JobDetail.student_id==Student.id)\
                    .filter(Student.id==ClassStudent.student_id)\
                    .filter(ClassStudent.class_id==ClassInfo.id)\
                    .filter(ClassInfo.id==TeachingRelationship.class_id)\
                    .filter(TeachingRelationship.teacher_id==current_user.id)\
                    .filter(JobDetail.serial_no==title_number)\
                    .filter(Student.id==stu.id)\
                    .first()        
        if j_detail:            
            paper =os.path.join(os.getcwd(),"app","static","job","job_readed",str(id),str(j_detail.student_id)+".png")            
            if os.path.exists(paper):
                answer_card=os.path.join(os.getcwd(),"app","static","job","answerCard",j.paper_url)                
                img=judge.open_answer_card(answer_card)
                ep =judge.open_student_card(paper)
                ep=judge.paper_ajust(img,ep)
                #if judge.qr(img)==judge.qr(ep):
                infor=json.loads(j.no_multiple_choice_info)
                n=judge.n                
                img=ep[infor[title_number]["位置"]["start"]*n:infor[title_number]["位置"]["end"]*n,7*n:75*n]               
                retval, buffer = cv2.imencode('.png', img)
                # 创建响应对象
                img_b64 = base64.b64encode(buffer).decode('utf-8')
                stu=Student.query.filter(Student.id==j_detail.student_id).first().realname
                response = {'image': img_b64,'No':j_detail.serial_no,'mark':infor[title_number]["分值"],'id':j_detail.id,'name':stu}
                response['Content-Type'] = 'image/png'
                return jsonify(response)
            else:
                paper1=os.path.join(os.getcwd(),"app","static","job","abnormal_paper",str(id),j_detail.student_id+".png")
                if os.path.exists(paper1):
                    img=judge.open(os.path.join(os.getcwd(),"app","static","job","paper","excercise",j.paper_url))
                    ep =judge.open2(paper1)
                    ep=judge.paper_ajust(img,ep)
                    #if judge.qr(img)==judge.qr(ep):
                    infor=json.loads(j.no_multiple_choice_info)
                    n=judge.n                
                    img=ep[infor[title_number]["位置"]["start"]*n:infor[title_number]["位置"]["end"]*n,7*n:75*n]               
                    retval, buffer = cv2.imencode('.png', img)
                    # 创建响应对象
                    img_b64 = base64.b64encode(buffer).decode('utf-8')
                    stu=Student.query.filter(Student.id==j_detail.student_id).first().name
                    response = {'image': img_b64,'No':j_detail.serial_no,'mark':infor[title_number]["分值"],'id':j_detail.id,'name':stu}
                    response['Content-Type'] = 'image/png'
                    return jsonify(response)
                else:
                    img=None
                    response= make_response("试卷不存在")
                    response.headers['Content-Type'] = 'text/plain' 
            #计算图片的非白色像素点的个数
            if img:
                count = cv2.countNonZero(img)
                #计算图片的像素点总个数
                size = img.size                             
        else:
            response= make_response("无待阅卷")
            response.headers['Content-Type'] = 'text/plain'
        return(response)

@job_manage.route("/set_cpl_mark/",methods=["POST"]) #
@login_required 
@permission_required(Permission.publish_job)
def set_cpl_mark():
    if request.method=="POST":
        id=request.json["id"]
        mark=request.json["mark"]
        #serial_no=request.json["title_number"]       
        j_t=JobDetail.query.filter(JobDetail.id==id).first()        
        if j_t:
            job_stu=JobStudent.query.filter(JobStudent.job_id==j_t.job_id,JobStudent.student_id==j_t.student_id).first()
            if job_stu:
                if job_stu.complete_mark:
                    job_stu.complete_mark=job_stu.complete_mark-j_t.mark+mark
                else:
                    job_stu.complete_mark=mark
            else:
                jot_stu=JobStudent(job_id=j_t.job_id,student_id=j_t.student_id,select_mark=mark)
                db.session.add(jot_stu)
            j_t.mark=mark
            
            db.session.flush()
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                return(Exception)
            return(jsonify(j_t.job_id))
        else:
            return("找不到该作业")
        
@job_manage.route("/judge_report/<id>",methods=["POST","GET"]) #阅卷报告
@login_required
@permission_required(Permission.publish_job)
def judge_report(id):
    if id == "this":
        #筛选出当前教师所任教班级的所有异常作业
        d_judge=AbnormalJob.query.filter(AbnormalJob.job_id==id).all()
        #筛选出当前教师所任教班级的所有作业
        this=JobStudent.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(ClassInfo.id==TeachingRelationship.class_id).filter(TeachingRelationship.teacher_id==current_user.id).filter(JobStudent.submit_time>datetime.datetime.now()-datetime.timedelta(minutes=5)).filter(JobStudent.mark!=None).count()
        all=JobStudent.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(ClassInfo.id==TeachingRelationship.class_id).filter(TeachingRelationship.teacher_id==current_user.id).filter(JobStudent.mark!=None).count()
        t=JobStudent.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(ClassInfo.id==TeachingRelationship.class_id).filter(TeachingRelationship.teacher_id==current_user.id).filter(JobStudent.submit_time!=None).order_by(JobStudent.submit_time.desc()).first()
    elif id=="all":
        d_judge=AbnormalJob.query.filter(AbnormalJob.job_id==id).all()
        this=JobStudent.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(ClassInfo.id==TeachingRelationship.class_id).filter(TeachingRelationship.teacher_id==current_user.id).filter(JobStudent.submit_time>datetime.datetime.now()-datetime.timedelta(minutes=5)).filter(JobStudent.mark!=None).count()
        all=JobStudent.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(ClassInfo.id==TeachingRelationship.class_id).filter(TeachingRelationship.teacher_id==current_user.id).filter(JobStudent.mark!=None).count()
        #筛选出最近提交的记录
        t=JobStudent.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(ClassInfo.id==TeachingRelationship.class_id).filter(TeachingRelationship.teacher_id==current_user.id).filter(JobStudent.submit_time!=None).order_by(JobStudent.submit_time.desc()).first()
    #判断id是否为数字，如果是数字，则为作业id，否则为all或者this
    elif id.isdigit():
        d_judge=AbnormalJob.query.filter(AbnormalJob.job_id==id).all()
        job_=Job.query.filter(Job.id==id).first()
        #n为提交时间为一个小时之内的job_student记录数
        try:
            this_query = JobStudent.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(ClassInfo.id == TeachingRelationship.class_id).filter(TeachingRelationship.teacher_id == current_user.id).filter(JobStudent.submit_time > datetime.datetime.now() - datetime.timedelta(minutes=5)).filter(JobStudent.mark != None).filter(JobStudent.job_id == int(id))
            all_query = JobStudent.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(ClassInfo.id == TeachingRelationship.class_id).filter(TeachingRelationship.teacher_id == current_user.id).filter(JobStudent.mark != None).filter(JobStudent.job_id == int(id))
            t_query = JobStudent.query.join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(ClassInfo.id == TeachingRelationship.class_id).filter(TeachingRelationship.teacher_id == current_user.id).filter(JobStudent.submit_time != None).filter(JobStudent.job_id == int(id)).order_by(JobStudent.submit_time.desc())
            this = this_query.count()
            all = all_query.count()
            t = t_query.first()
        except Exception as e:
            return "Error occurred while querying database: {}".format(str(e)), 500
    else:
        return("没有相关作业")
    data=[[d.id,d.reason,d.paper,d.number,d.time] for d in d_judge]
    if t:
        time=t.submit_time
        name=t.student.realname
    else:
        time=name=None
    data={"s_num":this,"d_num":len(data),"name":job_.job_name,"total":all,"d_list":data,"time":time,"stu":name}
    return render_template("job/judge_report.html",data=data,id=id)

@job_manage.route("/clear_abnormal/<id>",methods=["POST","GET"]) #阅卷报告
@login_required
@permission_required(Permission.publish_job)
def clear_abnormal(id):
    if request.method=="POST":
        #data为后台传来的json数据，是一个列表,存储了要删除的异常记录的paper字段的值
        data=request.json
        n=0
        for d in data:
            AbnormalJob.query.filter(AbnormalJob.paper==d).delete()
            #删除异常异常卷图片
            path=os.path.join(os.getcwd(),"app","static","job","abnormal_paper",str(id),d)
            if os.path.exists(path):
                os.remove(path)
            n+=1
        db.session.flush()
        db.session.commit()
        d_judge=AbnormalJob.query.filter(or_(AbnormalJob.student_id==None,AbnormalJob.student_id.in_(db.session.query(ClassStudent.student_id).filter(ClassStudent.class_id.in_(db.session.query(TeachingRelationship.class_id).filter(TeachingRelationship.teacher_id==current_user.id)))))).filter(AbnormalJob.job_id==id).all()
    data=[[d.id,d.reason,d.paper,d.student_id] for d in d_judge]
    total=JobStudent.query.filter(JobStudent.job_id==int(id)).filter(JobStudent.mark!=None).count()
    name=Job.query.filter(Job.id==id).first().job_name
    return(jsonify({"s_num":n,"d_num":len(data),"name":name,"total":total,"d_list":data}))

@job_manage.route("/abnormal/<args>",methods=["POST","GET"]) #显示异常阅卷
@login_required
@permission_required(Permission.publish_job)
def abnormal(args):
    job_id,ab_id=args.split(":")
    job_=Job.query.filter(Job.id==job_id).first()
    abn=AbnormalJob.query.filter(AbnormalJob.id==ab_id).first()
    path1=os.path.join(os.getcwd(),"app","static","job","answerCard",job_.paper_url)
    path2=os.path.join(os.getcwd(),"app","static","job","abnormal_paper",str(job_id),abn.paper)
    if not os.path.exists(path1):
        return("作业不存在") 
    if not os.path.exists(path2):
        return("学生答题卡不存在,请返回")
    img=judge.open_answer_card (path1)
    pict=judge.open_student_card(path2)
    pict=judge.paper_ajust(img,pict)
    n=judge.n
    if pict is None:
        pass
    elif abn.reason=="二维码识别失败":
        retval, buffer = cv2.imencode('.png', pict)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
    elif "学号" in abn.reason:        
        pict=pict[4*n:36*n,6*n:68*n]        
    elif "选择题" in abn.reason:        
        pict=pict[4*n:36*n,7*n:68*n]
    #使用cv2识别出pict中的黑色方快，并将其描边为红色
    if '选择题' in abn.reason or '学号' in abn.reason:
        cnts=judge.pict(pict)        
        cnt,h=cv2.findContours(cnts,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        number=judge.number_pos(pict[15*n:36*n,27*n:67*n]) 
        pict=cv2.drawContours(pict,cnt,-1,(0,0,255),2)
    if pict is None :
        img_b64=None
    else:
        retval, buffer = cv2.imencode('.png', pict)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
    return render_template("job/abnormal.html",img=img_b64,job=job_,abnormal=abn)
   
@job_manage.route("/JudgeErroHanding/modifyNumber/",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)
def modifyNumber():
    if request.method=="POST":
        id=request.form.get("id")
        paper=request.form.get("paper")
        number=request.form.get("number")
        ab=AbnormalJob.query.filter(AbnormalJob.id==id).first()
        paper=os.path.join(os.getcwd(),'app','static','job',paper)         
        msg=judgeWithNumber(number,paper,ab.job_id)
        if msg!="success":
            if ab.paper==paper.split("/")[-1]:
                ab.reason=msg
            else:
                ab1=AbnormalJob(job_id=ab.job_id,reason=msg,paper=paper.split("/")[-1],teacher_id=current_user.id,time=datetime.datetime.now())
                db.session.add(ab1)
        else:
            #删除abs
            if ab.paper==paper.split("/")[-1]:
                db.session.delete(ab)
            else:
                paper=os.path.join(os.getcwd(),'app','static','job','abnormal_paper',str(ab.job_id),ab.paper)
                msg=judgeWithNumber(ab.student_id,paper,ab.job_id)
                if msg!="success":
                    ab.reason=msg
                else:
                    db.session.delete(ab)
        db.session.flush()
        db.session.commit()
        return(msg)

@job_manage.route("/JudgeErroHanding/Assignjob/",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)
def Assignjob():
    if request.method=="POST":
        id=request.form.get("id")
        job_id=request.form.get("job_id")
        student_id=request.form.get("student_id")
        ab=AbnormalJob.query.filter(AbnormalJob.id==id).first()
        j_s=JobStudent.query.filter(JobStudent.job_id==job_id,JobStudent.student_number==student_id).first()
        if j_s:
            msg="该学生已经有名为《%s》的作业任务" %Job.query.filter(Job.id==job_id).first().job_name
        else:
            j_s=JobStudent(job_id=job_id,student_number=student_id)
            db.session.add(j_s)
            db.session.flush()
            msg="已为学号为%s的学生布置名为《%s》的作业任务" %(student_id,Job.query.filter(Job.id==job_id).first().job_name)
        msg1=judgeWithNumber(student_id,os.path.join(os.getcwd(),'app','static','job','abnormal_paper',str(job_id),ab.paper),job_id)
        #如果msg1不为success，则将异常卷的原因改为msg1,否则删除abnormal_job表中的记录
        if msg1!="success":
            ab.reason=msg1
            ab.student_id=student_id
            ab.job_id=job_id
        else:
            db.session.delete(ab)
        db.session.flush()
        db.session.commit()
        return(msg,msg1)

def judgeWithNumber(number,paper,job_id):
    #找出任教学生中，学号为number的学生的id
    stu_id=Student.query.join(ClassStudent,ClassStudent.student_id==Student.id).join(TeachingRelationship,TeachingRelationship.class_id==ClassStudent.class_id).filter(TeachingRelationship.teacher_id==current_user.id).filter(Student.number==number).first().id

    
    j_stu=JobStudent.query.filter(JobStudent.job_id==int(job_id),JobStudent.student_id==stu_id).first()
    if not j_stu:
        return("学号为:%s的学生没有名为《%s》的作业任务" %(number ,Job.query.filter(Job.id==job_id).first().job_name))  
    card=os.path.join(os.getcwd(),'app','static','job','answerCard',Job.query.filter(Job.id==job_id).first().paper_url)
    img=judge.open_student_card(paper)
    img=judge.paper_ajust(judge.open_answer_card(card),img)
    msg1,mark=multiple_choice_judge(img,job_id)
    
    if msg1=="作业不存在":   
        return msg1        
    se=update_select_info(stu_id,job_id,mark)    
    j_stu.select_mark=se
    j_stu.submit_time=datetime.datetime.now()
    if msg1=="success":
#将已经阅卷的卷子移至job_readed文件夹中,并修改文件名    
        path1=os.path.join(os.getcwd(),"app","static","job","job_readed",str(job_id))
        if not os.path.exists(path1):
            os.makedirs(path1)
        path2=os.path.join(path1,str(number)+".png")
        os.rename(paper,path2)
    #生成非选择题阅卷信息
    non_multiple_choice_to_read(number,job_id)
    update_ClassInfo(job_id)
    db.session.commit()
    return(msg1)

@job_manage.route("func1",methods=["POST","GET"])#为所有行政班任教的学生布置作业
def func1():
    #获取当前用户的行政班任教信息
    t_info=TeachingRelationship.query.join(ClassInfo).filter(TeachingRelationship.teacher_id==current_user.id,ClassInfo.attribute=="行政班").all()
    #获取当前用户所在学科的所有作业
    jobs=Job.query.filter(Job.subject==current_user.subject).all()
    #将每一个作业布置给每一个班级
    for j in jobs:
        for t in t_info:
            j_s=JobClass(job_id=j.id,class_id=t.class_id)
            db.session.add(j_s)
    db.session.flush()
    db.session.commit()
    return("ok")

@job_manage.route("/job_analyse",methods=["POST","GET"]) #阅卷报告
@login_required
@permission_required(Permission.publish_job)
def job_analyse():    
    t_info=TeachingRelationship.query.join(ClassInfo).filter(TeachingRelationship.teacher_id==current_user.id,TeachingRelationship.subject==current_user.subject).all()
    classes=[c.class_info for c in t_info]
    end=datetime.date.today()
    #end加一天
    end=end+datetime.timedelta(days=1)
    start=end-datetime.timedelta(days=7)
    id=None
    job_name=""
    if request.method=="POST":
        start=request.form.get("start")
        end= request.form.get("end")
        id = request.form.get("id")
        job_name=request.form.get("job_name")
        end=datetime.datetime.strptime(end,"%Y-%m-%d")
        now=datetime.datetime.now()
        #将字符串end转换为日期对象        
        end= datetime.datetime.combine(end, now.time())
    bar=class_job_comparision(start,end,job_name)    
    #查找出所有在所选时间段内，布置给所任教班级的所任教学科的作业，布置时间数据在JobClass表date字段中，JobClass数据表为作业布置数据表,以布置时间排序
    jobs=Job.query.join(JobClass).filter(JobClass.class_id.in_([c.id for c in classes]),Job.job_name.like("%"+str(job_name)+"%"),Job.subject==current_user.subject,JobClass.date.between(start,end)).order_by(JobClass.date).all()
    #将作业的平均分，完成率，标准差，以pyecharts折线图呈现
    job_names=[j.job_name for j in jobs]
    avg_scores=[]
    completion_rates=[]
    std_devs=[]
    for j in jobs:
        if id:#如果前端传来了班级id，则统计该班级的作业信息，否则，统计所有班级的作业信息
            JobClass_=JobClass.query.filter(JobClass.job_id==j.id,JobClass.class_id==int(id),JobClass.average!=0).first()
            if JobClass_:
                avg_scores.append(round(JobClass_.average/j.total1*100,2))
                completion_rates.append(round(JobClass_.submit_number/len(ClassStudent.query.filter(ClassStudent.class_id==JobClass_.class_id).all())*100,2))
                std_devs.append(round(JobClass_.std,2))
            else:   
                avg_scores.append(0)
                completion_rates.append(0)
                std_devs.append(0)
        else:
            JobClasses=JobClass.query.filter(JobClass.job_id==j.id).all()
            if JobClasses:
                if sum([c.submit_number for c in JobClasses if c.submit_number]):
                    avg_scores.append(round(sum([c.average/j.total1*c.submit_number for c in JobClasses if c.average])/sum([c.submit_number for c in JobClasses])*100,2))               
                    completion_rates.append(round(sum([c.submit_number for c in JobClasses if c.submit_number] )/sum([len(ClassStudent.query.filter(ClassStudent.class_id==c.class_id).all()) for c in JobClasses])*100,2))
                    std_devs.append(round(sum([c.std for c in JobClasses if c.std])/len(JobClasses),2))
                else:
                    completion_rates.append(0)
                    avg_scores.append(0)
                    std_devs.append(0)
            else:
                avg_scores.append(0)
                completion_rates.append(0)
                std_devs.append(0)    
    line = (
        Line(init_opts=opts.InitOpts(width="100%", height="100%"))
        .add_xaxis(job_names)
        .add_yaxis("得分率", avg_scores)
        .add_yaxis("完成率", completion_rates)
        .add_yaxis("标准差", std_devs)
        .set_global_opts(title_opts=opts.TitleOpts(title="所选时段内作业情况变化趋势图"),xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-15)))   
    )
    return render_template("job/job_analyse.html", classes=classes, chart=bar,chart2=line.render_embed())

#班级作业情况对比图
@job_manage.route("/class_job_comparision/",methods=["POST","GET"])
@login_required
def class_job_comparision_():
    job_name=""
    if request.method=="POST":
        n=request.form.get("days")        
        name=request.form.get("job_name")
        if name:
            job_name=name
        end=datetime.datetime.now()
        start=end-datetime.timedelta(days=int(n))
    bar=class_job_comparision(start,end,job_name)
    return bar
def class_job_comparision(start,end,job_name):    
    t_info=TeachingRelationship.query.join(ClassInfo).filter(TeachingRelationship.teacher_id==current_user.id,TeachingRelationship.subject==current_user.subject).all()
    classes=[c.class_info for c in t_info]
    #JobClass表中，存储了某班级，某作业的情况，包括作业的平均分，标准差，完成率，找出时间段内，所任教班级的任教学科作业的平均分，完成率，标准差，以pyecharts柱形图呈现
    class_names = [c.class_name for c in classes]
    avg_scores=[]
    completion_rates=[]
    std_devs=[]
    for i in classes:
        #筛选所有JobClass表中，class_id==i.id的记录，作业名称包含job_name的，布置时间在start和end之间，学科为当前用户任教学科的作业记录
        JobClasses = JobClass.query.join(Job).filter(JobClass.class_id==i.id,Job.job_name.like("%"+str(job_name)+"%"),JobClass.date.between(start,end),Job.subject==current_user.subject,JobClass.average!=0,JobClass.average!=None).all() 
        if JobClasses:            
            avg_scores.append(round(sum([c.average/Job.query.filter(Job.id==c.job_id).first().total1 for c in JobClasses if c.average])/len(JobClasses)*100,2))
            completion_rates.append(round(sum([c.submit_number/len(ClassStudent.query.filter(ClassStudent.class_id==c.class_id).all()) for c in JobClasses if c.submit_number])/len(JobClasses)*100,2))
            std_devs.append(round(sum([c.std for c in JobClasses if c.std])/len(JobClasses),2))
        else:
            avg_scores.append(0)
            completion_rates.append(0)
            std_devs.append(0)
    bar = (
        Bar(init_opts=opts.InitOpts(width="100%", height="120%"))#宽度跟随父元素
        .add_xaxis(class_names)
        .add_yaxis("得分率", avg_scores)
        .add_yaxis("完成率", completion_rates)
        .add_yaxis("标准差", std_devs)
        .set_global_opts(title_opts=opts.TitleOpts(title="班级作业对比")) 
        #x轴的数据旋转角度
    )
    return bar.render_embed()

#获取作业未完成情况
@job_manage.route("/get_unfinish_job/",methods=["POST","GET"]) 
@login_required
@permission_required(Permission.publish_job)
def get_unfinish_job():    
    days=request.form.get("days")
    end=datetime.date.today()
    end=datetime.datetime.combine(end, datetime.time(23, 59, 59))
    start=end-datetime.timedelta(days=int(days))
    j_s=JobStudent.query.join(Job).join(JobClass).join(Student).join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(TeachingRelationship.teacher_id==current_user.id,JobStudent.submit_time==None,JobClass.date.between(start,end),Job.subject==current_user.subject).all()
    #统计每个人的未完成情况
    result={}    
    for i in j_s:
        if i.student.realname not in result:
            result[i.student.realname]=1
        else:
            result[i.student.realname]+=1
    #找出最大5个
    result=dict(sorted(result.items(),key=lambda x:x[1],reverse=True)[:5])        
    return jsonify(result)

@login_required
@permission_required(Permission.publish_job)
@job_manage.route("/get_pie/",methods=["POST","GET"])  #得分率分布饼图
def get_pie():
    if request.method == "POST":
        start = request.form.get("start")
        end = request.form.get("end")
        job_name = request.form.get("job_name")
        id = request.form.get("id")
        class_id = request.form.get("class_id")
        subject_ = request.form.get("subject")        
        base_query = (
            JobStudent.query
            .join(Job, JobStudent.job_id == Job.id)
            .join(JobClass, JobClass.job_id == JobStudent.job_id)
            .join(ClassInfo, ClassInfo.id == JobClass.class_id)
            .join(ClassStudent, ClassStudent.class_id == ClassInfo.id)
            .join(TeachingRelationship, TeachingRelationship.class_id == ClassInfo.id)
            .join(Student, Student.id == JobStudent.student_id)
            .filter(
                TeachingRelationship.teacher_id == current_user.id, 
                   )
        )
        if subject_ is None:
            subject_ = current_user.subject
        elif subject_ =="全部":
            subject_ = None
        base_query = base_query.filter(Job.subject == subject_)
  
        if job_name:
            Job.job_name.like(f"%{job_name}%")
        if id:
            base_query = base_query.filter(Job.id == id)
        if class_id:
            base_query = base_query.filter(ClassInfo.id == class_id)
        if start and end:
            base_query = base_query.filter(JobClass.date.between(start, end))
        l1 = base_query.filter(JobStudent.mark / Job.total1 >= 0.90).distinct().count()
        l2 = base_query.filter(JobStudent.mark / Job.total1 >= 0.80, JobStudent.mark / Job.total1 < 0.90).distinct().count()
        l3 = base_query.filter(JobStudent.mark / Job.total1 >= 0.70, JobStudent.mark / Job.total1 < 0.80).distinct().count()
        l4 = base_query.filter(JobStudent.mark / Job.total1 >= 0.60, JobStudent.mark / Job.total1 < 0.70).distinct().count()
        l5 = base_query.filter(JobStudent.mark / Job.total1 >= 0.50, JobStudent.mark / Job.total1 < 0.60).distinct().count()
        l6 = base_query.filter(JobStudent.mark / Job.total1 >= 0.40, JobStudent.mark / Job.total1 < 0.50).distinct().count()
        l7 = base_query.filter(JobStudent.mark / Job.total1 < 0.40).distinct().count()
        # 创建玫瑰图
        pie = (
            Pie(init_opts=opts.InitOpts(width="100%", height="100%"))
            .add(
                "",
                [
                    list(z) for z in zip(
                        ["90-100", "80-89", "70-79", "60-69", "50-59", "40-49", "<40"],
                        [l1, l2, l3, l4, l5, l6, l7]
                    )
                ],
                radius=["30%", "70%"],
                rosetype="radius"
            )
            .set_global_opts(title_opts=opts.TitleOpts(title="得分率分布"), legend_opts=opts.LegendOpts(is_show=False))
            .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
        )
        return jsonify(pie.render_embed())        
        
@job_manage.route("/modify_mark/<id>",methods=["POST","GET"]) #修改选择题成绩，当选择题分数设置错误或答案错误，需要整体修改时运行该函数
@login_required
@permission_required(Permission.publish_job)
def modify_mark(id):
    job_=Job.query.filter(Job.id==id).first()    
    answer=json.loads(job_.select_answer)
    multiple_choice_info=json.loads(job_.multiple_choice_info)    
    jt=JobDetail.query.filter(JobDetail.job_id==id).filter(JobDetail.serial_no.in_(answer.keys())).all()

    mark=[]
    for key in multiple_choice_info:
        for j in range(key["初始题号"],key["题目数量"]+key["初始题号"]):
            mark.append(key["分值"])    
    for j in jt:
        if j.answer!=answer[str(j.serial_no)]:
            j.mark=0
        else:
            j.mark=mark[j.serial_no-1]
    js=JobStudent.query.filter(JobStudent.job_id==id).all()
    for j in js:
        #计算每个学生的选择题得分,从job_detail表中，找出job_id==id,student==j.student的记录，将mark字段求和
        j.select_mark=JobDetail.query.filter(JobDetail.job_id==id,JobDetail.student_id==j.student_id).filter(JobDetail.serial_no.in_(answer.keys())).with_entities(func.sum(JobDetail.mark)).first()[0]
    update_ClassInfo(id)
    return (jsonify("更新成功"))

@job_manage.route("/modify/<id>",methods=["POST","GET"]) #将异常卷的文件名以学号命名
@login_required
@permission_required(Permission.publish_job)
def modify(id):
    ab=db.session.query(AbnormalJob).filter(AbnormalJob.job_id==id).all()
    n=0
    for a in ab:
        path=os.path.join(os.getcwd(),"app/static/abnormal_paper",str(id),a.paper)        
        if os.path.exists(path):
            if a.student_id:
                os.rename(path,os.path.join(os.getcwd(),"app/static/abnormal_paper",str(id),a.student_id+".png"))
                a.paper=a.student_id+".png"                
                n+=1
    db.session.flush()
    db.session.commit()
    return(str(n))

@job_manage.route("/personal/<id_class>", methods=["POST", "GET"])
@login_required
@permission_required(Permission.publish_job)
def student_charts(id_class):
    start = datetime.datetime.now() - datetime.timedelta(days=7)
    end = datetime.datetime.now()
    job_name = ""
    id, class_id = id_class.split("_")
    if request.method == "POST":
        start_str = request.form.get("start")
        end_str = request.form.get("end")
        job_name = request.form.get("job_name")
        subject_=request.form.get("subject")
        now = datetime.datetime.now()        
        # 将字符串start和end转换为日期对象
        start = datetime.datetime.strptime(start_str, "%Y-%m-%d") if start_str else start
        end = datetime.datetime.strptime(end_str, "%Y-%m-%d") if end_str else end
        end = datetime.datetime.combine(end, now.time())    
    # 查找学生所处班级    
    class_ = ClassInfo.query.filter_by(id=class_id).first()
    job_ = Job.query.join(JobClass).filter(
        Job.job_name.like(f"%{job_name}%"),
        JobClass.class_id == class_.id,
        JobClass.date.between(start, end)
    )
    if subject_!="全部":
        job_=job_.filter(Job.subject==subject_)
    # 查找时间段内, 所任教学科布置给该班级的学生的作业
    job_=job_.all()
    
    job_names = [j.job_name for j in job_]
    scores = []
    average = []
    student = Student.query.filter_by(id=id).first()
    name = student.realname if student else "Unknown"
    
    for j in job_:
        job_student_ = JobStudent.query.filter_by(job_id=j.id, student_id=id).first()
        if job_student_ and j.total1:
            scores.append(round((job_student_.mark / j.total1) * 100, 2) if job_student_.mark is not None else 0)
        else:
            scores.append(0)

        job_class_ = JobClass.query.filter_by(job_id=j.id, class_id=class_.id).first()
        if job_class_ and j.total1:
            average.append(round((job_class_.average / j.total1) * 100, 2) if job_class_.average else 0)
        else:
            average.append(0)

    line = (
        Line(init_opts=opts.InitOpts(width="100%", height="500px"))
        .add_xaxis(job_names)
        .add_yaxis("得分率", scores)
        .add_yaxis("班级平均得分率", average)
        .set_global_opts(
            title_opts=opts.TitleOpts(title=f"{name}作业得分情况"),
            toolbox_opts=opts.ToolboxOpts(),
            xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-20)),
            yaxis_opts=opts.AxisOpts(min_=0, max_=100)
        )
    )

    # line图表渲染，通过ajax传送给前端
    return line.render_embed()


@job_manage.route("/genarate_paper",methods=["POST","GET"])  #
@login_required 
@permission_required(Permission.publish_job)
def genarate_paper():
    diff=Difficult.query.all()
    if current_user.role.has_permission(Permission.publish_job):
        class__=current_user.classes_taught
        class_=[]
        for i in class__:
            if i not in class_:
                class_.append(i)
    if current_user.role.has_permission(Permission.publish_job):
        pass
    g=GradeInfo.query.all()
    return(render_template("job/paper.html",g=g,difficult=diff,class_=class_,Permission=Permission))


@job_manage.route("/paper/",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)
def initial_paper():               
    paper=creat_paper.genarate_papaer(2000)#paper为pil格式图片
    n=paper.width//82       
    creat_paper.number_area(n,paper,n*27,n*9,10)
    paper=creat_paper.paste_image(paper)
    #将paper保存在static文件夹下的temp文件夹中，文件名为currentuser的id，格式为png
    paper.save(os.path.join(os.getcwd(),"app","static","job","temp",str(current_user.id)+".png"))
    #将pil格式图片转换为opencv格式图片
    paper_cv=np.array(paper)
    paper_cv=cv2.cvtColor(paper_cv,cv2.COLOR_RGB2BGR)
    retval, buffer = cv2.imencode('.png', paper_cv)
    img_b64 = base64.b64encode(buffer).decode('utf-8')
    # 创建响应对象
    response = make_response(img_b64)
    # 设置响应头
    response.headers['Content-Type'] = 'text/plain'
    return(response)

@job_manage.route("/modifyTitle/",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)
def modifyTitle():
    if request.method=="POST":
        title=request.form.get("title")
        img=Image.open(os.path.join(os.getcwd(),"app/static/job/temp",str(current_user.id)+".png"))
        img=creat_paper.add_title(img,title)
        img.save(os.path.join(os.getcwd(),"app/static/job/temp",str(current_user.id)+".png"))
        img_cv=np.array(img)
        img_cv=cv2.cvtColor(img_cv,cv2.COLOR_RGB2BGR)
        retval, buffer = cv2.imencode('.png', img_cv)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        # 创建响应对象
        response = make_response(img_b64)
        # 设置响应头
        response.headers['Content-Type'] = 'text/plain'
        return(response)

@job_manage.route("/paper/select",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)
def drawSelect():
    if request.method=="POST":
        quantity=int(request.form.get("quantity"))
        number1=int(request.form.get("number1"))
        number2=int(request.form.get("number2"))
        score=float(request.form.get("score"))
        position=int(request.form.get("position"))
        checkMultiple=request.form.get('checkMultiple')
        #打开pil图像,图像位置在static文件夹下的temp目录中
        img=Image.open(os.path.join(os.getcwd(),"app/static/job/temp",str(current_user.id)+".png"))
        n=img.width//82
        pos=creat_paper.genarate_select(n,number1,number2,quantity,score,img,n*7,n*position,checkMultiple)
        img.save(os.path.join(os.getcwd(),"app/static/job/temp",str(current_user.id)+".png"))
        #将pil格式图片转换为opencv格式图片
        img_cv=np.array(img)
        img_cv=cv2.cvtColor(img_cv,cv2.COLOR_RGB2BGR)
        retval, buffer = cv2.imencode('.png', img_cv)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        # 创建响应对象，将pos和img_b64传输给前端
        response = make_response(json.dumps({"pos":pos,"img":img_b64}))
        # 设置响应头
        response.headers['Content-Type'] = 'text/plain'
        return(response)

@job_manage.route("/paper/complete/",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)
def drawComplete():
    if request.method=="POST":
        subtopic=request.form.get("subtopic")
        subtopic=json.loads(subtopic)
        number1=int(request.form.get("number1"))
        number2=int(request.form.get("number2"))
        c_marks=request.form.get("c_mark") 
        c_marks=json.loads(c_marks) 
        position=int(request.form.get("position"))
        #打开pil图像,图像位置在static文件夹下的temp目录中
        img=Image.open(os.path.join(os.getcwd(),"app/static/job/temp",str(current_user.id)+".png"))
        n=img.width//82
        pos=creat_paper.generate_completion(n,img,subtopic,c_marks,n*7,n*position,number1,number2)
        img.save(os.path.join(os.getcwd(),"app/static/job/temp",str(current_user.id)+".png"))
        #将pil格式图片转换为opencv格式图片
        img_cv=np.array(img)
        img_cv=cv2.cvtColor(img_cv,cv2.COLOR_RGB2BGR)
        retval, buffer = cv2.imencode('.png', img_cv)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        # 创建响应对象，将pos和img_b64传输给前端,pos是一个列表，每个元素是一个字典，包含了每题的开始位置和结束位置
        response = make_response(json.dumps({"pos":pos[0],"img":img_b64}, default=str))
        response.headers['Content-Type'] = 'text/plain'
        return(response)

@job_manage.route("/paper/shortAnswer/",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)
def drawShortAnswer():
    if request.method=="POST":
        line=request.form.get("line")
        line=json.loads(line)
        score=request.form.get("score")
        score=json.loads(score)
        number1=int(request.form.get("number1"))
        number2=int(request.form.get("number2"))
        position=int(request.form.get("position"))
        #打开pil图像,图像位置在static文件夹下的temp目录中
        img=Image.open(os.path.join(os.getcwd(),"app","static","job","temp",str(current_user.id)+".png"))
        n=img.width//82
        pos=creat_paper.drawShortAnswer(n,img,n*position,line,score,number1,number2)
        img.save(os.path.join(os.getcwd(),"app","static","job","temp",str(current_user.id)+".png"))
        #将pil格式图片转换为opencv格式图片
        img_cv=np.array(img)
        img_cv=cv2.cvtColor(img_cv,cv2.COLOR_RGB2BGR)
        retval, buffer = cv2.imencode('.png', img_cv)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        # 创建响应对象，将pos和img_b64传输给前端,pos是一个列表，每个元素是一个字典，包含了每题的开始位置和结束位置
        response = make_response(json.dumps({"pos":pos,"img":img_b64}, default=str))
        response.headers['Content-Type'] = 'text/plain'
        return(response)

@job_manage.route("/paper/rollBack/",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)
def rollback():
    if request.method=="POST":
        #获取后台传来的structrued数据
        structrued=request.form.get("structrued")
        structrued=json.loads(structrued)
        key=structrued.keys()
        last=structrued[list(key)[-1]]
        if "选" in last["类型"]:
            start=last["位置"]["start"]
            end=last["位置"]["end"]
        else:
            key=last["位置"].keys()
            start=last["位置"][list(key)[0]]["start"]
            end=last["位置"][list(key)[-1]]["end"]+1
        #打开pil图像,图像位置在static文件夹下的temp目录中
        img=Image.open(os.path.join(os.getcwd(),"app/static/job/temp",str(current_user.id)+".png"))
        #将img的start到end的区域填充为白色
        n=img.width//82
        img=creat_paper.fillWhite(img,(start-3)*n,end*n)
        pos=start-3
        img.save(os.path.join(os.getcwd(),"app/static/job/temp",str(current_user.id)+".png"))
        #将pil格式图片转换为opencv格式图片
        img_cv=np.array(img)
        img_cv=cv2.cvtColor(img_cv,cv2.COLOR_RGB2BGR)
        retval, buffer = cv2.imencode('.png', img_cv)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        # 创建响应对象，将pos和img_b64传输给前端,pos是一个列表，每个元素是一个字典，包含了每题的开始位置和结束位置
        response = make_response(json.dumps({'img':img_b64,'pos':pos}, default=str))
        response.headers['Content-Type'] = 'text/plain'
        return(response)

@job_manage.route("/publish_work/",methods=["POST","GET"])
@login_required 
@permission_required(Permission.publish_job)
def publish_work():
    db.session.commit()
    if request.method=="POST":
        title=request.form.get("title")
        if Job.query.filter_by(job_name=title).first():
            return("作业名重复")
        #获取后台传来的structrued数据
        structrued1=request.form.get("structrued")
        structrued=json.loads(structrued1)                
        answer=request.form.get("answers")
        answer=json.loads(answer)
        classlist=request.form.get("classlist")
        classlist=json.loads(classlist)
        g=request.form.get("grade") 
        g=json.loads(g)       
        tags=request.form.get("tags")
        tags=json.loads(tags)
        files=request.files.get("file")
        subject=current_user.subject
        total=0
        select=[]
        no_Select={}
        s_answer={}
        for key in structrued.keys():
            if "选" in structrued[key]["类型"]:
                s={}
                total+=structrued[key]["分值"]*structrued[key]["小题数"]
                s["大题号"]=key
                s["初始题号"]=structrued[key]["初始题号"]
                s["题目数量"]=structrued[key]["小题数"]
                s["分值"]=structrued[key]["分值"]
                s["位置"]=structrued[key]["位置"]
                select.append(s)             
                for k in range(len(answer[key])):
                    s_answer[s["初始题号"]+k]=answer[key][k]
            else:
                total+=sum(structrued[key]["分值"].values())                
                for k in structrued[key]["位置"].keys():
                    NS={}                    
                    NS["位置"]=structrued[key]["位置"][k]
                    NS["分值"]=structrued[key]["分值"][k]
                    no_Select[k]=NS
        if files:
            filename=secure_filename(files.filename)
            filename=title+"."+filename.split(".")[-1]
            url=os.path.join(os.getcwd(),"app/static/job/paper/question_paper",subject)
            if not os.path.exists(url):
                os.makedirs(url)
            url=os.path.join(url,filename)
            files.save(url)
        job1=Job(job_name=title,answerCardStructure=json.dumps(structrued),select_answer=json.dumps(s_answer),context=json.dumps(tags),subject=subject,publisher=current_user.id ,multiple_choice_info=json.dumps(select),no_multiple_choice_info=json.dumps(no_Select),total1=total,question_paper=filename,publish_time=datetime.datetime.now())
        db.session.add(job1)
        db.session.flush()
        job1.paper_url=str(job1.id)+".png"
        db.session.commit()
        path=os.path.join(os.getcwd(),"app","static","job","answer",str(job1.id))  
        path1=os.path.join(os.getcwd(),"app","static","job","job_readed",str(job1.id))      
        if not os.path.exists(path):
            os.makedirs(path)
        if not os.path.exists(path1):
            os.makedirs(path1) 
        if g:
            class_list=db.session.query(ClassInfo).join(GradeInfo).filter(GradeInfo.id.in_(g)).filter(ClassInfo.attribute=="行政班").all()    
        else:          
            class_list=db.session.query(ClassInfo).filter(ClassInfo.id.in_(json.loads(request.form.get("classlist")))).all()
        #将答题卡移至对应的文件夹中
        path=os.path.join(os.getcwd(),"app","static","job","answerCard",subject)
        if not os.path.exists(path):
            os.makedirs(path)
        try:
            path1=os.path.join(os.getcwd(),"app","static","job","temp",str(current_user.id)+".png")
            path2=os.path.join(os.getcwd(),"app","static","job","answerCard",str(job1.id)+".png")
            #给答题卡添加二维码
            img = Image.open(path1)
            n=img.width//82
            messeage=str(job1.id)
            #creat_paper.generate_barcode(str(job1.id),img,(n*68,n*13),n*12)
            creat_paper.qr_paste(messeage,img,(n*68,n*20),n*12) 
            img.save(path2)
            img.save(path1)
        except Exception as e:  
            print(e)          
            db.session.rollback()
        #将作业发布给对应的班级
        if class_list:  # 作业布置 
            for i in class_list:                    
                check_job=JobClass.query.join(Job,JobClass.job).filter(Job.job_name==title,JobClass.class_id==i.id,Job.subject==current_user.subject).first()  #避免重复布置相同作业
                if check_job:
                    messege="%s班已经有名为《%s》的作业！" %(check_job.ClassInfo.class_name,title)
                    return(messege)
                else:
                    publish_job = JobClass(class_id=i.id,job_id=job1.id)
                    db.session.add(publish_job)
                    
                    for j in i.students:
                        j_stu=JobStudent(job_id=job1.id,student_id=j.student.id)
                        db.session.add(j_stu)                        
        else:
            messege="没有设置班级,请在作业主界面选择班级布置作业！"
            return(messege)
        db.session.flush()
        db.session.commit()
        return("success")
 
@job_manage.route("/super_judge/",methods=["POST","GET"]) #识别二维码阅卷
@login_required 
@permission_required(Permission.submit_job)
def super_judge():
    path=os.path.join(os.getcwd(),"app","static","job","answer","all",str(current_user.id))
    #遍历path文件夹下的所有文件
    files=os.listdir(path)
    n=0
    id=[]
    m=0
    #如果path文件夹下没有文件，则返回
    if not files:
        return("没有作业需要阅卷")
    for i in files:
        #获取文件的绝对路径
        file=os.path.join(path,i)
        #判断是否是文件夹
        if not os.path.isdir(file):
            standard=judge.open_answer_card(os.path.join(os.getcwd(),"app","static","job","paper","standard.png"))
            img=judge.open_student_card(file)
            img=judge.paper_ajust(standard,img) 
            qr_img=img[judge.n*20:judge.n*35,judge.n*68:judge.n*80]
            #形态学操作，去除噪点，补上缺点
            qr_img=cv2.morphologyEx(qr_img, cv2.MORPH_OPEN, np.ones((3,3),np.uint8))
            qr_img=cv2.morphologyEx(qr_img, cv2.MORPH_OPEN, np.ones((3,3),np.uint8))
            _, qr_img = cv2.threshold(qr_img, 180, 255, cv2.THRESH_BINARY)            
            messeage=judge.qr_recognize(qr_img,(0,qr_img.shape[0],0,qr_img.shape[1]))
            if messeage:
                print(messeage)
            else:
                m+=1
                print("没有识别到二维码")
            number=judge.number_pos(img)
            if messeage and number:     
                messeage=messeage[0].split("_")                
                job_id=messeage[0]
                if job_id not in id:
                    id.append(job_id)
                msg=check_student_number(number,job_id)
                if msg[0] !="success":
                    #将异常卷的信息存入abnormal_job表中
                    ab=AbnormalJob(job_id=int(job_id),paper=i,student_numer=number,reason=msg,teacher_id=current_user.id)
                    db.session.add(ab)
                   
                    #将异常卷移至abnormal_paper文件夹中
                    path1=os.path.join(os.getcwd(),"app","static","job","abnormal_paper",str(job_id))
                    if not os.path.exists(path1):
                        os.makedirs(path1)
                    os.rename(file,os.path.join(path1,i))
                    continue
                stu_id=int(msg[1])                
                msg1,mark=multiple_choice_judge(img,job_id)
                if msg1!="success":
                    ab=AbnormalJob(job_id=job_id,paper=i,student_number=number,reason=mark,time=datetime.datetime.now(),teacher_id=current_user.id)
                    db.session.add(ab)                    
                    #将异常卷移至abnormal_paper文件夹中
                    path1=os.path.join(os.getcwd(),"app","static","job","abnormal_paper",str(job_id))
                    if not os.path.exists(path1):
                        os.makedirs(path1)
                    os.rename(file,os.path.join(path1,i))
                    db.session.commit()
                    if msg1=="作业不存在": 
                        continue
                se=update_select_info(stu_id,job_id,mark)
                j_stu=JobStudent.query.filter(JobStudent.job_id==int(job_id),JobStudent.student_id==int(stu_id)).first()
                j_stu.select_mark=se
                j_stu.submit_time=datetime.datetime.now()
                n+=1
                #将已经阅卷的卷子移至job_readed文件夹中,并修改文件名
                if  msg1=="success":  
                    path1=os.path.join(os.getcwd(),"app","static","job","job_readed",str(job_id))
                    if not os.path.exists(path1):
                        os.makedirs(path1)
                    path2=os.path.join(path1,str(stu_id)+".png")
                    os.rename(file,path2)
                #生成非选择题阅卷信息
                non_multiple_choice_to_read(stu_id,job_id)
    for i in id:
        update_ClassInfo(i)
    db.session.flush()
    db.session.commit()
    return(jsonify("%s份作业未成功识别二维码，成功阅卷%s份" %(m,n)))

@job_manage.route("/UpdateClassInfo/",methods=["POST","GET"])
@login_required 
@permission_required(Permission.submit_job)
def UpdateClassInfo():
    if request.method=="POST":
        id=request.get_json()["id"]
        update_ClassInfo(id)
        return(jsonify("成功更新成绩信息"))

@job_manage.route("/getCard/",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)#根据前端发来的图片路径，找到相应图片并转换为base64
def getCard():
    if request.method=="POST":
        url=request.form.get("url")
        url=os.path.join(os.getcwd(),"app","static","job",url)
        print(url)
        img_b64=get_img(url)
        response = make_response(img_b64)
        # 设置响应头
        response.headers['Content-Type'] = 'img/png'
        return(response)

@job_manage.route("/modifyAnswer/",methods=["POST","GET"])
@login_required
@permission_required(Permission.publish_job)
def modifyAnswer():
    if request.method=="POST":
        data=request.get_json()        
        id=data["id"]
        answer=data["answer"]
        job_=Job.query.filter(Job.id==id).first()
        answer_=json.loads(job_.select_answer)
        for key in answer.keys():
            answer_[key]=answer[key]
        job_.select_answer=json.dumps(answer_)
        db.session.commit()
        return(jsonify("成功更新答案"))

@job_manage.route("/student_subject_compare/",methods=["POST","GET"])
@login_required
def student_subject_compare():
    student_id = request.args.get("user_id")
    if not student_id:
        return jsonify("error", "学生ID不能为空")
    student_ = Student.query.get(student_id)
    if not student_:
        return jsonify("error", "该学生不存在")
    all_data={}
    sub=[]
    end = datetime.datetime.now()
    for i in [7,14,30,3600]:
        data={}
        start = end - datetime.timedelta(days=i)
    #找出该学生的所有作业，根据学科汇总出各学科平均得分率，平均得分率为JobStudent.mark/Job.total*100
        average_scores = db.session.query(
            Job.subject.label('subject'),
            func.round(func.avg((JobStudent.mark / Job.total1) * 100), 2).label('average_score')
        ).select_from(JobStudent).join(Job, JobStudent.job_id == Job.id).filter(
            JobStudent.student_id == student_id,
            JobStudent.submit_time.between(start, end)
        ).group_by(Job.subject).all()
        #使用pyecharts创建雷达图
        # 转换数据格式
        for subject_, score in average_scores:
            if subject_ not in data.keys():
            
                data[subject_] = score
            if subject_ not in sub:
                sub.append(subject_)
        if i==3600:
            all_data["全部"]=data
        else:
            all_data[f"{i}天"]=data
    # 定义雷达图的属性（每个维度的最大值可以根据实际情况调整）
    max_score = 100
    c_schema = [opts.RadarIndicatorItem(name=subject_, max_=max_score) for subject_ in sub]
    # 创建雷达图
    radar = (
        Radar( opts.InitOpts(width="100%", height="100%"))
        .add_schema(schema=c_schema)
       
        .set_series_opts(label_opts=opts.LabelOpts(is_show=False))
    )
    for k,v in all_data.items():
        # 添加数据
        item=[]
        for subject_ in sub:
            if subject_ in v.keys():
                item.append(v[subject_])
            else:
                item.append(0)
        radar.add(series_name=k, data=[item]) 
    return radar.render_embed()

@job_manage.route("/student_important_job/", methods=["POST", "GET"])
@login_required
def student_important_job():
    student_id = request.args.get("user_id")
    days_str = request.args.get("days")    
    if student_id is None:
        return jsonify({"status": "error", "message": "学生ID不能为空"})    
    student_ = Student.query.get(student_id)
    if student_ is None:
        return jsonify({"status": "error", "message": "该学生不存在"})    
    try:
        days = int(days_str)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid days value"})
    
    # 查询学生的作业信息
    now = datetime.datetime.now()
    start = now - datetime.timedelta(days=days)
    student_jobs = (
        JobStudent.query
        .filter(
            JobStudent.student_id == student_id,
            JobStudent.submit_time.between(start, now)
        )
        .order_by(JobStudent.mark.asc())
        .limit(5)
        .all()
    )
    dicts=[]
    for student_job in student_jobs:
        dict={}
        dict["name"]=student_job.job.job_name
        dict["subject"]=student_job.job.subject
        dict["submit_time"]= student_job.submit_time.strftime("%Y-%m-%d %H:%M:%S"),
        dict["select_mark"]=student_job.select_mark
        dict["complete_mark"]=student_job.complete_mark
        dict["rate"]=round(student_job.mark/student_job.job.total1*100,2)
        dicts.append(dict)
    return jsonify(dicts)

@job_manage.route("/student_jobs_rate/",methods=["GET"])
@login_required
def student_jobs_rate():
    user_id = request.args.get("user_id")
    days=request.args.get("days")
    days=int(days)
    end=datetime.datetime.now()
    end=datetime.datetime.combine(end, datetime.time(23, 59, 59))
    start=end-datetime.timedelta(days=days)
    student_jobs=JobStudent.query.filter(JobStudent.student_id==user_id,JobStudent.submit_time.between(start,end)).all()
    subjects=[]
    job_names=[]
    data=[]
    for student_job in student_jobs:
        if student_job.job.subject not in subjects:
            subjects.append(student_job.job.subject)
        job_names.append(student_job.job.job_name)
        data.append([job_names.index(student_job.job.job_name),subjects.index(student_job.job.subject),student_job.mark/student_job.job.total1*100])

    scatter3d = Scatter3D(init_opts=opts.InitOpts(width="100%", height="100%"))
    scatter3d.add(
        series_name="",
        data=data,
        xaxis3d_opts=opts.Axis3DOpts(type_="category", data=job_names, name='作业名'),
        yaxis3d_opts=opts.Axis3DOpts(type_="category", data=subjects, name='学科'),
        zaxis3d_opts=opts.Axis3DOpts(type_="value", name='得分率'),
    )
    scatter3d.set_global_opts(
        title_opts=opts.TitleOpts(title=""),
        visualmap_opts=opts.VisualMapOpts( ),

        legend_opts=opts.LegendOpts(is_show=False),
        tooltip_opts=opts.TooltipOpts(
        formatter=lambda params: f'X: {job_names[params.data[0]]}<br>Y: {subjects[params.data[1]]}<br>Z: {params.data[2]}')
    )

    return scatter3d.render_embed()
@job_manage.route("/student_jobs/", methods=["POST", "GET"])
@login_required
def student_jobs():
    student_id = request.args.get("user_id")
    if student_id is None:
        return jsonify({"status": "error", "message": "学生ID不能为空"})
    student_ = Student.query.get(student_id)
    if student_ is None:
        return jsonify({"status": "error", "message": "该学生不存在"}
    )
    subject_=request.args.get("subject")
    if subject_ is None:
        return jsonify({"status": "error", "message": "学科不能为空"})
    student_jobs = (
        JobStudent.query
        .filter(
            JobStudent.student_id == student_id,
            JobStudent.submit_time != None
        )
    )
    if subject_ != "全部":
        student_jobs = student_jobs.join(Job).filter(Job.subject == subject_)
    student_jobs = student_jobs.order_by(JobStudent.submit_time.desc()).all()
    dicts=[]
    for student_job in student_jobs:
        dict={}
        dict["id"]=student_job.id
        dict["name"]=student_job.job.job_name
        dict["subject"]=student_job.job.subject
        dict["submit_time"]= student_job.submit_time.strftime("%Y-%m-%d %H:%M:%S"),
        dict["select_mark"]=student_job.select_mark
        dict["complete_mark"]=student_job.complete_mark
        dict["rate"]=round(student_job.mark/student_job.job.total1*100,2)
        dicts.append(dict)
    return jsonify({"status": "success", "data": dicts})
@job_manage.route("/student_unfinished_job/", methods=["POST", "GET"])
@login_required
def student_unfinished_job():
    student_id = request.args.get("user_id")
    if student_id is None:
        return jsonify({"status": "error", "message": "学生ID不能为空"})
    student_ = Student.query.get(student_id)
    if student_ is None:
        return jsonify({"status": "error", "message": "该学生不存在"}
    )
    student_jobs = (
        JobStudent.query
        .filter(
            JobStudent.student_id == student_id,
            JobStudent.submit_time == None
        )
    ).all()   
   
    dicts=[]
    for student_job in student_jobs:
        dict={}
        dict["id"]=student_job.job.id
        dict["name"]=student_job.job.job_name
        dict["subject"]=student_job.job.subject
        dicts.append(dict)
    return jsonify({"status": "success", "data": dicts})

def multiple_choice_judge(answer_card,job_id):#选择题阅卷
    msg=""
    mark={}
    job_=db.session.query(Job).filter(Job.id==job_id).first()
    if job_:       
        structrued=json.loads(job_.answerCardStructure)
        multiple_choice_info=json.loads(job_.multiple_choice_info)
        answer=json.loads(job_.select_answer)
        tag=json.loads(job_.context)
        for q in multiple_choice_info:
            #切出题目区域垂直方向为start到end，水平方向为n*7到n*75
            img=answer_card[q['位置']['start']*judge.n:q['位置']['end']*judge.n,judge.n*7:judge.n*75]
            initial_number=q['初始题号']
            score=q['分值']
            quantity=q['题目数量']
            student_answer=judge.check_select(img,quantity)
            for k in student_answer.keys():
                if str(initial_number+k-1) not in answer.keys():
                    continue
                if student_answer[k]==answer[str(initial_number+k-1)]:
                    mark[initial_number+k-1]=[student_answer[k],score,tag[initial_number+k-2]]                   
                else:
                    mark[initial_number+k-1]=[student_answer[k],0,tag[initial_number+k-2]]    
        msg="success"
    else:
        msg="作业不存在"
    return(msg,mark)
 
def check_student_number(number,id):#检测学号是否正确
    if  len(number)>10:
        return("学号长度不正确")
    job_=Job.query.filter(Job.id==int(id)).first()
    if not job_:
        return("作业不存在") 
    
    stu_id=Student.query.join(ClassStudent).join(ClassInfo).join(TeachingRelationship).filter(Student.number==number,ClassInfo.id==TeachingRelationship.class_id,TeachingRelationship.teacher_id==current_user.id).first()
    if not stu_id:
        return("没有学号为%s的学生" %(number))
    else:
        stu_id=stu_id.id  

    j_stu = JobStudent.query.filter(JobStudent.job_id==job_.id,JobStudent.student_id==stu_id).first()
    if j_stu is None:
        return("学号为%s的学生没有名为%s作业任务" %(number,job_.job_name))
    if not j_stu: #判断该生是否有作业任务，若无，不作阅卷处理
        return("学号为%s的学生没有名为%s作业任务" %(number,job_.job_name))
    else:#判断该生是否已经阅卷，若已阅卷，不作阅卷处理
        if j_stu.submit_time is not None:
            return("%s已阅卷,请检查是否重复阅卷" %number,stu_id)           
            
        else:
            return("success",stu_id)

#更新学生选择题答案信息
def update_select_info(id,job_id,answer):
    se=0     
    for key in answer.keys():
        jt = JobDetail.query.filter(
            JobDetail.student_id==id,
            JobDetail.job_id == job_id,
            JobDetail.serial_no == key
        ).first()
        if jt:    
            jt.answer=answer[key][0]
            jt.mark=answer[key][1]
            jt.tag=answer[key][2]
        else:
            jt=JobDetail(job_id=job_id,student_id=id,serial_no=key,answer=answer[key][0],mark=answer[key][1],tag=answer[key][2])
            db.session.add(jt)        
        se+=answer[key][1]
    job_student_=JobStudent.query.filter(JobStudent.job_id==job_id,JobStudent.student.has(User.id==id)).first()
    if  job_student_:
        job_student_.select_mark=se
    db.session.flush()
    db.session.commit()
    return(se)

#更新班级成绩统计信息
def update_ClassInfo(id):
    j_cla=JobClass.query.filter(JobClass.job_id==int(id)).all()  #阅卷完成后统计作业情况，查询被布置了此作业的所有班级
    for j in j_cla:
        # Query the average score of the students in the class
        try:
            average = db.session.query(func.avg(JobStudent.mark)) \
                       .join(Student, JobStudent.student_id == Student.id) \
                       .join(ClassStudent, Student.id == ClassStudent.student_id) \
                       .filter(ClassStudent.class_id == j.class_id, JobStudent.job_id == int(id)) \
                       .scalar()
        except Exception as e:
            print(f"An error occurred while calculating the average score: {e}")
            average = None
        if average is None:
            average = 0.0  # Set the average to 0 if it is None
        
        # Query the number of students who submitted the job
        submit_number = JobStudent.query.filter(
            JobStudent.job_id == int(id),
            JobStudent.submit_time != None
        ).join(Student, JobStudent.student_id == Student.id).join(
            ClassStudent, Student.id == ClassStudent.student_id
        ).filter(
            ClassStudent.class_id == j.class_id
        ).count()
        
        # Query the maximum score of the students in the class
        max = db.session.query(func.max(JobStudent.mark)).join(
            Student, JobStudent.student_id == Student.id
        ).join(
            ClassStudent, Student.id == ClassStudent.student_id
        ).filter(
            ClassStudent.class_id == j.class_id,
            JobStudent.job_id == int(id)
        ).scalar()
        if max is None:
            max = 0
        
        # Query the minimum score of the students in the class
        min = db.session.query(func.min(JobStudent.mark)).join(
            Student, JobStudent.student_id == Student.id
        ).join(
            ClassStudent, Student.id == ClassStudent.student_id
        ).filter(
            ClassStudent.class_id == j.class_id,
            JobStudent.job_id == int(id)
        ).scalar()
        if min is None:
            min = 0
        
        # Query the standard deviation of the scores of the students in the class
        std = db.session.query(func.stddev(JobStudent.mark)).join(
            Student, JobStudent.student_id == Student.id
        ).join(
            ClassStudent, Student.id == ClassStudent.student_id
        ).filter(
            ClassStudent.class_id == j.class_id,
            JobStudent.job_id == int(id)
        ).scalar()
        if std is None:
            std = 0

        # Update the class information
        j.average = average
        j.submit_number = submit_number
        j.max = max
        j.min = min
        j.std = std
    db.session.flush()
    db.session.commit()
    return("success")

def non_multiple_choice_to_read(stu_id,id):
    job_=Job.query.filter(Job.id==int(id)).first()
    complete=json.loads(job_.no_multiple_choice_info)
    #遍历complete字典生成填空题阅卷信息
    for key in complete.keys():   
        jt=JobDetail.query.filter(JobDetail.student_id==int(stu_id),JobDetail.job_id==int(id),JobDetail.serial_no==key).first()
        if not jt:
            jt=JobDetail(job_id=int(id),student_id=int(stu_id),serial_no=key,answer='F',tag=json.loads(job_.context)[int(key)-1])
            db.session.add(jt)
    db.session.flush()
    db.session.commit()
    return("success")

def get_img(url):#打开图片并转换为base64格式
    img=Image.open(url)
    img_cv=np.array(img)
    img_cv=cv2.cvtColor(img_cv,cv2.COLOR_RGB2BGR)
    retval, buffer = cv2.imencode('.png', img_cv)
    img_b64 = base64.b64encode(buffer).decode('utf-8')
    return(img_b64)

#生成阅卷异常信息
def genarate_exception_info(job_id,msg,pap,number):
    
    path1=os.path.join(os.getcwd(),"app","static","job","abnormal_paper",str(job_id))
    if not os.path.exists(path1):
        os.makedirs(path1)
    #如果pap是文件名，则将其移至abnormal_paper文件夹中，若是cv2格式图片，则直接保存
    if os.path.isfile(pap):
        shutil.copy(pap,os.path.join(path1,pap))
    else:
        cv2.imwrite(os.path.join(path1,pap))
    #保存异常信息
    ab=AbnormalJob(job_id=job_id,paper=pap,student_id=number,reason=msg,time=datetime.datetime.now(),teacher_id=current_user.id)
    db.session.add(ab)    
    #将异常卷移至abnormal_paper文件夹中
    db.session.commit()
    return("success")
    