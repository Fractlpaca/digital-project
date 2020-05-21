"""
Web app to provide feedback from and to students and teachers
Author: Joseph Grace
Version: 1.2
Updated 19/05/2020
"""

import os
from flask import Flask, request, url_for, redirect, render_template, flash, session, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from flask_login import UserMixin, LoginManager, login_required, login_user, logout_user, current_user
from passlib.hash import bcrypt
from datetime import datetime, timezone

#Own imports:
from permission_names import *

#HASHKEY_FILENAME = "hashkey.dat"
SECRET_KEY_FILENAME = "secretkey.dat"
BCRYPT_ROUNDS = 14

APP_DIR = os.path.dirname(os.path.abspath(__file__) ) #This is the directory of the project
PROJECTS_FOLDER = os.path.join(APP_DIR,"projects")
ALLOWED_FILE_EXTENSIONS = ["mp3","txt","docx","pdf","gif","jpg","png","zip","tar","tar.gz",]
database_file = "sqlite:///{}".format(os.path.join(APP_DIR,"database.db")) #Get path to database file

app = Flask(__name__) #define app
app.config["SQLALCHEMY_DATABASE_URI"] = database_file #give path of database to app
db = SQLAlchemy(app) #connect to database

#Using user structure for flask_login:
class Users(UserMixin, db.Model):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(20), nullable=False, unique=True)
    password_hash = Column(String(128), nullable = False)
    site_access = Column(Integer, default=0)
    def get_id(self):
        return str(self.user_id)
    projects_owned = relationship("Projects", back_populates="owner")
    project_permissions = relationship("ProjectPermissions")

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def user_loader(user_id):
    return Users.query.get(int(user_id))


class Projects(db.Model):
    __tablename__ = "projects"
    project_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50))
    owner_id = Column(Integer, ForeignKey("users.user_id"), nullable = False)
    owner = relationship("Users", back_populates="projects_owned")
    default_access = Column(Integer, default=PROJECT_DEFAULT_ACCESS)
    student_access = Column(Integer, default=PROJECT_STUDENT_ACCESS)
    time_created = Column(DateTime)
    time_updated = Column(DateTime)
    user_permissions = relationship("ProjectPermissions")

class ProjectPermissions(db.Model):
    __tablename__ = "project_permissions"
    project_id = Column(Integer, ForeignKey("projects.project_id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    access_level = Column(Integer)
    time_assigned = Column(DateTime)


def create_project(name,
                   owner_id,
                   default_access=PROJECT_DEFAULT_ACCESS,
                   student_access=PROJECT_STUDENT_ACCESS,
                   class_access=PROJECT_CLASS_ACCESS,
                   teacher_access=PROJECT_TEACHER_ACCESS):
    current_time = datetime.now(timezone.utc)
    new_project = Projects(name=name,
                           owner_id=owner_id,
                           time_created=current_time,
                           default_access=default_access,
                           student_access=student_access)
    db.session.add(new_project)
    db.session.commit()
    owner_permission_level = ProjectPermissions(user_id=owner_id,
                                                project_id=new_project.project_id,
                                                access_level=OWNER,
                                                time_assigned=current_time)
    project_folder = os.mkdir(os.path.join(PROJECTS_FOLDER,str(new_project.project_id)))
    db.session.add(owner_permission_level)
    db.session.commit()
    return new_project


def update_project_time(project_id):
    current_time = datetime.now(timezone.utc)
    project = Projects.query.filter_by(project_id=project_id).first()
    if not project is None:
        project.time_updated = current_time
        db.session.commit()

def assign_project_access(project_id, user_id, access_level):
    existing_permission = ProjectPermissions.filter_by(project_id=project_id).first
    if existing_permission is None:
        new_permission = ProjectPermissions(project_id=project_id,
                                            user_id=user_id,
                                            access_level=access_level)
        db.session.add(new_permission)
    elif existing_permision.access_level != access_level:
        existing_permission.access_level = access_level
    db.session.commit()
    

@app.route("/")
def index():
    print(current_user is None, flush=True)
    is_logged_in = current_user.is_authenticated
    username = current_user.username if is_logged_in else None
    return render_template("index.html", is_logged_in=is_logged_in, username=username)

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dash.html", username=current_user.username, projects_owned=current_user.projects_owned, is_logged_in=True)

@app.route("/register", methods=["GET", "POST"])
def register():
    print("Register", request.form, flush=True)
    if request.form:
        print("Form recieved", flush=True)
        username = request.form.get("username")
        if not Users.query.filter_by(username=username).first() is None:
            print("Error 1", flush=True)
        else:
            password_plaintext = request.form.get("password")
            password_hash = bcrypt.hash(password_plaintext, rounds=BCRYPT_ROUNDS)
            new_user = Users(username=request.form.get("username"),
                             password_hash=password_hash)
            db.session.add(new_user)
            db.session.commit()
            print("Added new user:",new_user, flush=True)
            logout_user()
            login_user(new_user)
            return redirect(url_for("dashboard"))
    is_logged_in = current_user.is_authenticated
    username = current_user.username if is_logged_in else None
    return render_template("register.html", is_logged_in=is_logged_in, username=username)

@app.route("/login", methods = ["GET", "POST"])
def login():
    logout_user()
    if request.form:
        username = request.form.get("username")
        user = Users.query.filter_by(username=username).first()
        password_plaintext = request.form.get("password")
        if Users.query.filter_by(username=username).first() is None:
            print("Error 2", flush=True)
        else:
            if bcrypt.verify(password_plaintext,user.password_hash):
                login_user(user)
                return redirect(url_for("dashboard"))
            else:
                print("Error 3", flush=True)
                #Error 2 and 3 must be presented as the same error for security reasons.
    return render_template("login.html", is_logged_in=False)    

@app.route("/logout")
def logout():
    print("Logged out user", current_user, flush=True)
    logout_user()
    return redirect("/")

@app.route("/newProject", methods=["GET", "POST"])
@login_required
def newProject():
    if request.args:
        name = request.args.get("name","Untitled Project")
        owner_id = current_user.user_id
        new_project = create_project(name=name,
                                     owner_id=owner_id)
        return redirect("/project/{}".format(new_project.project_id))
    return redirect("/dashboard")
        
@app.route("/project/<project_id_string>", methods=["GET", "POST"])
def project(project_id_string):
    project_id = int(project_id_string)
    project = Projects.query.filter_by(project_id=project_id).first()
    if project is None:
        abort(404)
    is_logged_in = current_user.is_authenticated
    if is_logged_in:
        permission = ProjectPermissions.query.filter_by(user_id=current_user.user_id, project_id=project_id).first()
        if permission is None:
            access_level = project.student_access
        else:
            access_level = permission.access_level
    else:
        access_level = project.default_access
    access_level_string = access_message[access_level]
    if access_level < CAN_VIEW:
        abort(404)
        #To prevent knoledge of existence of project
    project_dir = os.path.join(PROJECTS_FOLDER, str(project_id))
    if request.args:
        download_filename=request.args.get("filename", None)
        if download_filename is not None:
            print("Sending File From",project_dir, download_filename,flush=True)
            return send_from_directory(project_dir, download_filename,as_attachment=True)
        return redirect(f"/project/{project_id_string}")
    return render_template("project.html",
                           project=project,
                           is_logged_in=is_logged_in,
                           username=(current_user.username if is_logged_in else None),
                           access_level=access_level,
                           access_level_string=access_level_string)

def generate_key(filename, size):
    file = open(filename,"wb")
    print(os.urandom(size))
    file.write(os.urandom(size))
    file.close()
    
def get_key(filename):
    file = open(filename,"rb")
    key = file.read()
    file.close()
    return key

def file_location(path):
    return os.path.join(APP_DIR, path)

if __name__ == "__main__":
    #if not os.path.exists(file_location(HASHKEY_FILENAME)):
        ##Create password hash key
        #generate_key(HASHKEY_FILENAME, 64)
    if not os.path.exists(file_location(SECRET_KEY_FILENAME)):
        #Create session secret key
        generate_key(SECRET_KEY_FILENAME, 24)
    app.secret_key = get_key(SECRET_KEY_FILENAME)
    if not os.path.exists(file_location(database_file)):
        db.create_all()
    app.run(debug=True)