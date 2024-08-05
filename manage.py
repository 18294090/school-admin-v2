from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from app import app, db
from app.models import user, role

manager = Manager(app)
migrate = Migrate(app, db)

@manager.command
def create_admin_user():
    admin = user.query.filter_by(username='admin').first()
    student=user.query.filter_by(username='student').first()
    if not admin:
        admin = user(username='admin', password='123456', role='admin')
        db.session.add(admin)
        db.session.commit()
        print('Admin user created successfully')
    else:
        print('Admin user already exists')

    if not student:
        student = user(username='student',realname='学生用户', password='younverguesstheword', role='student')
        db.session.add(student)
        db.session.commit()
        print('Student user created successfully')

@manager.command
def create_role():
    student = role.query.filter_by(name='student').first()
    if not student:
        student = role(name='student',permissions=0)
        db.session.add(student)
        db.session.commit()
        print('Student role created successfully')
    teacher = role.query.filter_by(name='teacher').first()
    if not teacher:
        teacher = role(name='teacher',permissions=5)
        db.session.add(teacher)
        db.session.commit()
        print('Teacher role created successfully')
    admin = role.query.filter_by(name='admin').first()
    if not admin:
        admin = role(name='admin',permissions=2)
        db.session.add(admin)
        db.session.commit()
        print('Admin role created successfully')
    master_teacher = role.query.filter_by(name='master_teacher').first()
    if not master_teacher:
        master_teacher = role(name='master_teacher',permissions=109)
        db.session.add(master_teacher)
        db.session.commit()
        print('Master teacher role created successfully')
    headTeacher = role.query.filter_by(name='教研组长').first()
    if not headTeacher:
        headTeacher = role(name='教研组长',permissions=7)
        db.session.add(headTeacher)
        db.session.commit()
        print('Head teacher role created successfully')

@manager.command
def create_all():
    db.create_all()
    create_role()
    create_admin_user()


if __name__ == '__main__':
    manager.run()