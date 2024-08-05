from flask import render_template, redirect, request, url_for, flash,session,jsonify
from . import auth
from flask_login import login_user,logout_user,login_required
from ..models import User,Role,subject,Teacher,Permission,School
from .forms import userlogin
from .. import db
import time
from flask_login import current_user
from ..decorators import permission_required
from .faceRecognizer import faceRecognize
import  cv2
import numpy as np
import os
import base64
import re
import io
from PIL import Image


@auth.route("/", methods=["POST", "GET"])
def login():    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        remember_me = request.form.get("remember_me")
        if remember_me:
            remember_me = True
        u = User.query.filter_by(username=username).first()
        if u is None or not u.verify_password(password):
            flash("用户名或密码错误")
        else:
            login_user(u, remember=remember_me)
            next = request.args.get('next')
            if not next or not next.startswith("/"):
                next = url_for('main.index')
            u.login_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            db.session.commit()
            return redirect(next)

    return render_template("auth/login.html")

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("你已成功退出系统")
    return(redirect(url_for('auth.login')))

@auth.route("/reset/", methods=["POST", "GET"])
@login_required
def reset():    
    if request.method=="POST":
        id=request.form.get("id")        
        if current_user.id == int(id) or current_user.role.role=="admin":
            u=User.query.filter(User.id==id).first()
            u.password="z123456"
            db.session.flush()
            db.session.commit()
            return("密码修改成功,默认密码z1234567")
        else:
            return("你没有权限")
    else:
        current_user.password="z1234567"
        db.session.flush()
        db.session.commit()
        return("密码修改成功,默认密码z1234567")

@auth.route("/ad")
def ad():
    admin=User(username="admin",role_id=3,password="123")
    print(admin)
    db.session.add(admin)
    db.session.commit()
    return("初始化")

@auth.route("/register", methods=["POST", "GET"])
def reg():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        school = request.form.get("school")
        sub=request.form.get("subject")
        phone_number = request.form.get("phone_number") 
             
        u=User.query.filter_by(username=username).first()
        sch=School.query.filter(School.school_name==school).first()
        if  not sch:
            sch=School(school_name=school)
            db.session.add(sch)
            db.session.commit()
        school_id=sch.id 
        if u :
            flash("用户名已已被注册，请重新输入或联系管理员")        
        else:
            u=Teacher()
            u.username=username
            u.password=password
            u.school_id=school_id
            u.realname=username
            u.phone_number=phone_number
            u.role_id=Role.query.filter(Role.role=="teacher").first().id   
            u.discriminator="teacher"   
            u.subject=sub
            db.session.add(u)
            db.session.commit()
            return(redirect(url_for('auth.login')))
    return(render_template("auth/reg.html",subject=subject))

@auth.route("/personal_details")
def personal_details():
    return(render_template('auth/personal_details.html'))

@auth.route("/face_login",methods=["POST","GET"])
def face_login():
    face=request.form.get("image")
    img = re.sub('^data:image/.+;base64,', '', face)
    img=base64.b64decode(img)
    # base64解码后的图片数据转换为cv2图像
    img = Image.open(io.BytesIO(img))
    img_np = np.array(img)
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    result=faceRecognize.recognize(img_bgr)    
    if result is not None:
        u=User.query.filter_by(username=result).first()
        if u:            
            login_user(u)
            return("success")
    return("未匹配到用户")

@auth.route("/get_face",methods=["POST","GET"]) #人脸采集模块
@login_required
def get_face():
    if request.method=="POST":
        image=request.json["image"]
        img = re.sub('^data:image/.+;base64,', '', image)
        img=base64.b64decode(img)
        # base64解码后的图片数据转换为cv2图像
        img = Image.open(io.BytesIO(img))
        img_np = np.array(img)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        face=faceRecognize.app.get(img_bgr)
        if len(face)==0:
            return jsonify("0","未检测到人脸")
        else:
            #框出人脸转换为base64发送给前端
            face=face[0].bbox
            face=adjust_face_to_square(face)
            img=img_bgr[int(face[1]):int(face[3]),int(face[0]):int(face[2])]           
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            temp=io.BytesIO()
            img.save(temp,format="png")
            img=base64.b64encode(temp.getvalue())
            img=img.decode()
            return jsonify( "1","检测到人脸",img)
        
    return(render_template("auth/camera.html"))
def adjust_face_to_square(face):#将人脸调整为正方形
    # Calculate the width and height of the bounding box
    width = face[2] - face[0]
    height = face[3] - face[1]
    # Determine the maximum dimension (either width or height)
    max_dim = max(width, height)
    # Calculate the center coordinates of the bounding box
    center_x = (face[2] + face[0]) // 2
    center_y = (face[3] + face[1]) // 2
    # Extend the bounding box by half of the maximum dimension to create a square region
    square_size = max_dim // 2
    square_left = center_x - square_size
    square_top = center_y - square_size
    square_right = center_x + square_size
    square_bottom = center_y + square_size
    square_top = int(square_top)
    square_bottom = int(square_bottom)
    square_left = int(square_left)
    square_right = int(square_right)
    # Crop the face image using the square region coordinates
    cropped_face = [square_left, square_top, square_right, square_bottom]

    return cropped_face

def add_padding(base64_string): #base64解码后的图片数据转换为cv2图像
    missing_padding = len(base64_string) % 4
    if missing_padding:
        base64_string += '=' * (4 - missing_padding)
    return base64_string
@auth.route("/save_face",methods=["POST"]) #保存人脸
@login_required
def save_face(): #保存人脸，返回success，学生用户根据用户名存储，非学生用户根据id查找到相应用户的realname
    if request.method=="POST":
        image=request.json["image"]
        tag=request.json["tag"]
        id=request.json["id"]
        img = re.sub('^data:image/.+;base64,', '', image)
        img=add_padding(img)
        img=base64.b64decode(img)
        # base64解码后的图片数据转换为cv2图像
        img = Image.open(io.BytesIO(img))
        img_np = np.array(img)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        u=User.query.filter(User.id==id).first()
        name=u.username
        path=os.path.join("static","faces",name+".jpg")
        cv2.imwrite(os.path.join(os.getcwd(),"app",path),img_bgr)
        u.avatar=path
        db.session.commit()
        return jsonify('success')

@auth.route("/join_school",methods=["POST","GET"]) #加入学校
@login_required
def join_school():
    pass
    return(render_template("auth/join_school.html"))