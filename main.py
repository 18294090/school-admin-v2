from app import create_app, db, bootstrap 
from app.models import Permission,User,Role,Difficult,MessageType,Message
from flask_login import current_user
app = create_app('default')
# 创建一个上下文处理器
@app.context_processor
def inject_model_data():
    # 在这里可以获取model.py中的变量并传入模板
    return dict(Permission=Permission)

@app.context_processor

def inject_message():
    if current_user.is_authenticated:
        msg=Message.query.filter(Message.receiver==current_user.id).all()
    else:
        msg=[]
    return dict(msg=msg)


    
app.app_context().push()
with app.app_context():
    db.create_all()
    teacher = Role.query.filter_by(role='teacher').first()
    if not teacher:
        teacher = Role(role='teacher',permissions=Permission.submit_job+Permission.create_class+Permission.publish_job+Permission.attendance_management)
        db.session.add(teacher)
        db.session.commit()
        print('Teacher Role created successfully')
    admin = Role.query.filter_by(role='admin').first()
    if not admin:
        admin = Role(role='admin',permissions=253)
        db.session.add(admin)
        db.session.commit()
        print('Admin Role created successfully')
    master_teacher = Role.query.filter_by(role='HeadTeacher').first()
    if not master_teacher:
        master_teacher = Role(role='HeadTeacher',permissions=109)
        db.session.add(master_teacher)
        db.session.commit()
        print('Master teacher Role created successfully')
    headTeacher = Role.query.filter_by(role='HeadSubject').first()
    if not headTeacher:
        headTeacher = Role(role='HeadSubject',permissions=Permission.submit_job+Permission.create_class+Permission.publish_job)
        db.session.add(headTeacher)
        db.session.commit()
        print('Head of subject Role created successfully')
    student= Role.query.filter_by(role='student').first()
    if not student:
        student = Role(role='student',permissions=Permission.submit_job)
        db.session.add(student)
        db.session.commit()
        print('Student Role created successfully')
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin',realname='管理员', password='123456', role_id=Role.query.filter(Role.role=='admin').first().id)
        db.session.add(admin)
        db.session.commit()
        print('Admin User created successfully')
    else:
        print('Admin User already exists')
    diff=Difficult.query.filter(Difficult.difficult=='简单').first()
    if not diff:
        diff=Difficult(difficult='简单')
        db.session.add(diff)
        db.session.commit()
        print('Difficult created successfully')
    diff=Difficult.query.filter(Difficult.difficult=='一般').first()
    if not diff:
        diff=Difficult(difficult='一般')
        db.session.add(diff)
        db.session.commit()
        print('Difficult created successfully')
    diff=Difficult.query.filter(Difficult.difficult=='困难').first()
    if not diff:
        diff=Difficult(difficult='困难')
        db.session.add(diff)
        db.session.commit()
        print('Difficult created successfully')
    message_type=MessageType.query.filter(MessageType.message_type=='公告').first()
    if not message_type:
        message_type=MessageType(message_type='公告')
        db.session.add(message_type)
        db.session.commit()
        print('message_type created successfully')
    message_type=MessageType.query.filter(MessageType.message_type=='通知').first()
    if not message_type:
        message_type=MessageType(message_type='通知')
        db.session.add(message_type)
        db.session.commit()
        print('message_type created successfully')
    message_type=MessageType.query.filter(MessageType.message_type=='任课邀请').first()
    if not message_type:
        message_type=MessageType(message_type='任课邀请')
        db.session.add(message_type)
        db.session.commit()
        print('message_type created successfully')
    message_type=MessageType.query.filter(MessageType.message_type=='请假申请').first()
    if not message_type:
        message_type=MessageType(message_type='请假申请')
        db.session.add(message_type)
        db.session.commit()
        print('message_type created successfully')
   
