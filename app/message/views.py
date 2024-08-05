from .import message
from ..models import Message,MessageType,User,ClassInfo,Job,JobClass,JobStudent,ClassStudent,TeachingRelationship,Attendance,Student
from .. import db
from flask import request,jsonify,render_template,redirect,url_for,flash
from flask_login import current_user,login_user,login_required
from ..manage.views import join_class

@message.route('/read/', methods=['GET', 'POST'])
def message_read():
    if request.method == 'POST':
        message_id = request.form.get('id')
        message = Message.query.filter(Message.id == message_id).first()
        if message:
            message.status =1
            db.session.commit()
            return jsonify({"id":message.id,"title":message.title,"content":message.content,"status":message.status,"sender":message.sender_info.realname,"receiver":message.receiver_info.realname,"time":message.time.strftime("%Y-%m-%d %H:%M:%S"),"message_type":message.message_type})       
        return jsonify({'status': 'error'})
    
@message.route('/agree/', methods=['POST'])
def message_agree():
    if request.method == 'POST':
        message_id = request.form.get('id')
        message = Message.query.filter(Message.id == message_id).first()
        if not message:
            return jsonify({'status': 'error', 'message': 'Message not found'})
        
        if message.message_type == 3:   
            try:
                class_name = message.content.split(":")[1]
                class_ = ClassInfo.query.join(TeachingRelationship)\
                    .filter(ClassInfo.class_name == class_name,
                            TeachingRelationship.teacher_id == message.sender,
                            TeachingRelationship.subject == "班主任",
                            TeachingRelationship.class_id == ClassInfo.id).first()
                
                if not class_:
                    flash("班级不存在,请联系邀请发送者")
                    return jsonify({'status': 'error', 'message': 'Class not found'})
                
                class_id = class_.id
                msg = join_class(class_id, current_user.subject, message.receiver)
                
                flash(msg)
                
                db.session.delete(message)
                db.session.commit()
                return jsonify({'status': 'ok'})
            
            except Exception as e:
                db.session.rollback()
                return jsonify({'status': 'error', 'message': str(e)})
        elif message.message_type == 5:
            try:
                user_=User.query.filter(User.id==message.sender).first()
                subject_=user_.subject
                class_name=message.content.split(":")[1]
                class_ = ClassInfo.query.join(TeachingRelationship)\
                    .filter(ClassInfo.class_name == class_name,
                            TeachingRelationship.teacher_id == message.receiver,
                            TeachingRelationship.subject == "班主任",
                            TeachingRelationship.class_id == ClassInfo.id).first()
                if not class_:
                    flash("班级不存在,请联系邀请发送者")
                    return jsonify({'status': 'error', 'message': 'Class not found'})
                class_id = class_.id
                msg = join_class(class_id, subject_, message.sender)
                flash(msg)
                db.session.delete(message)
                db.session.commit()
                return jsonify({'status': 'ok'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'status': 'error', 'message': str(e)})@message.route('/apply_to_teach/', methods=['POST'])
@message.route('/apply_to_teach/', methods=['POST'])
@login_required
def apply_to_teach():
    if request.method == 'POST':
        data = request.get_json()
        class_id = data['class_id']
        subject_ = data['subject']
        sender_id = data['sender']

        sender = User.query.filter_by(id=sender_id).first()
        if not sender:
            return jsonify({'status': 'error', 'message': '发送者信息错误'})

        class_ = ClassInfo.query.filter_by(id=class_id).first()
        if not class_:
            return jsonify({'status': 'error', 'message': '班级信息错误'})

        teacher_relationship = TeachingRelationship.query.filter_by(class_id=class_id, subject="班主任").first()
        if not teacher_relationship:
            return jsonify({'status': 'error', 'message': '班级信息错误，请联系管理员'})

        teacher_id = teacher_relationship.teacher_id
        message_type = MessageType.query.filter_by(message_type="任课申请").first()
        if not message_type:
            return jsonify({'status': 'error', 'message': '消息类型错误，请联系管理员'})

        message = Message(
            title="任课申请",
            content=f"{sender.realname}老师希望加入班级:{class_.class_name}:担任{subject_}老师",
            sender=sender.id,
            receiver=teacher_id,
            message_type=message_type.id,
            status=0
        )
        db.session.add(message)
        db.session.commit()

        flash("邀请已发送，请等待相关老师确认")
        return jsonify({'status': 'ok'})


