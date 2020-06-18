"""
Web app to provide feedback from and to students and teachers
Author: Joseph Grace
Version: 1.3
Updated 08/06/2020
"""

import os
import shutil
from flask import Flask, request, url_for, redirect, render_template, flash, session, abort, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, or_
from sqlalchemy.orm import relationship
from flask_login import UserMixin, LoginManager, login_required, login_user, logout_user, current_user
from passlib.hash import bcrypt
from datetime import datetime, timezone
from werkzeug.utils import secure_filename

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
    project_permissions = relationship("ProjectPermissions", back_populates="user")

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
    user_permissions = relationship("ProjectPermissions", back_populates="project")
    def access_level(self, user_id=None):
        if user_id is None:
            return self.default_access
        project_permission = ProjectPermissions.query.filter_by(project_id=self.project_id,
                                                                user_id=user_id).first()
        if project_permission is None:
            return self.student_access
        return project_permission.access_level
    
    def user_permission_pairs(self):
        return sorted([(permission.user,permission.access_level) for permission in self.user_permissions],key=lambda x: (-x[1],x[0]))

class ProjectPermissions(db.Model):
    __tablename__ = "project_permissions"
    project_id = Column(Integer, ForeignKey("projects.project_id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    access_level = Column(Integer)
    time_assigned = Column(DateTime)
    project = relationship("Projects", back_populates="user_permissions")
    user = relationship("Users", back_populates="project_permissions")


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
    project_folder = os.path.join(PROJECTS_FOLDER,str(new_project.project_id))
    os.mkdir(project_folder)
    project_filesystem = os.path.join(project_folder,"filesystem")
    os.mkdir(project_filesystem)
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
    current_time = datetime.now(timezone.utc)
    existing_permission = ProjectPermissions.query.filter_by(project_id=project_id, user_id=user_id).first()
    if existing_permission is None:
        new_permission = ProjectPermissions(project_id=project_id,
                                            user_id=user_id,
                                            access_level=access_level,
                                            time_assigned=current_time)
        db.session.add(new_permission)
    elif existing_permission.access_level != access_level:
        existing_permission.access_level = access_level
        existing_permission.time_assigned = current_time
    db.session.commit()
    update_project_time(project_id)

@app.route("/")
def index():
    print(current_user is None, flush=True)
    is_logged_in = current_user.is_authenticated
    username = current_user.username if is_logged_in else None
    return render_template("index.html", is_logged_in=is_logged_in, username=username)

@app.route("/dashboard")
@login_required
def dashboard():
    user_id = current_user.get_id()
    projects_owned = current_user.projects_owned
    projects_shared = ProjectPermissions.query.filter(ProjectPermissions.user_id==user_id, CAN_VIEW <= ProjectPermissions.access_level, ProjectPermissions.access_level< OWNER).all()
    projects_shared = [project_permission.project for project_permission in projects_shared]
    other_projects = Projects.query.filter(or_(Projects.default_access >= CAN_VIEW,Projects.student_access >= CAN_VIEW)).all()
    print(projects_owned,projects_shared,other_projects,flush=True)
    return render_template("dash.html",
                           username=current_user.username,
                           projects_owned=projects_owned,
                           projects_shared = projects_shared,
                           other_projects = other_projects,
                           is_logged_in=True)

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


def handle_project_id(project_id, threshold_access=CAN_VIEW):
    project = Projects.query.filter_by(project_id=project_id).first()
    if project is None:
        abort(404)
    is_logged_in = current_user.is_authenticated
    if is_logged_in:
        access_level = project.access_level(current_user.user_id)
    else:
        access_level = project.default_access
    if access_level < threshold_access:
        abort(404)
        #To prevent knoledge of existence of project
    return (project, access_level, is_logged_in)

@app.route("/project/<project_id_string>", methods=["GET", "POST"])
def project(project_id_string):
    project_id = int(project_id_string)
    project, access_level, is_logged_in=handle_project_id(project_id)
    access_level_string = access_messages[access_level]
    #project_dir = os.path.join(PROJECTS_FOLDER, str(project_id))
    #filesystem_dir = os.path.join(project_dir,"file_system")
    view_route = f"/project/{project_id}/view/"
    permission_route = f"/project/{project_id}/permission"
    permission_pairs = project.user_permission_pairs()
    permission_pair_names = [(user.username, permission_descriptions[permission]) for user, permission in permission_pairs]
    print(permission_pair_names, flush=True)
    return render_template("project.html",
                           project=project,
                           is_logged_in=is_logged_in,
                           username=(current_user.username if is_logged_in else None),
                           access_level=access_level,
                           access_level_string=access_level_string,
                           view_route=view_route,
                           permission_route=permission_route,
                           permission_pair_names=permission_pair_names)


@app.route("/project/<project_id_string>/view/",methods=["GET"])
@app.route("/project/<project_id_string>/view/<path:path>",methods=["GET"])
def viewProject(project_id_string, path=""):
    print("Directory is",path+".",flush=True)
    project_id=int(project_id_string)
    base_url = f"/project/{project_id}/view/{path}"
    project, access_level, is_logged_in=handle_project_id(project_id)
    project_dir = os.path.join(PROJECTS_FOLDER, str(project_id))
    filesystem_dir = os.path.join(project_dir,"filesystem")   
    inner_path = os.path.realpath(os.path.join(filesystem_dir, path))
    print(inner_path, flush=True)
    if not inner_path.startswith(filesystem_dir):
        abort(403)
    if not os.path.exists(inner_path):
        abort(404)
    parent_directories = [("root", f"/project/{project_id}/view")]
    folders = path.strip("/").split("/")
    if folders == [""]: folders = []
    for i in range(len(folders)):
        parent_directories.append((folders[i], f"/project/{project_id}/view/"+"/".join(folders[:i+1])))
    print(parent_directories, flush=True)
    if os.path.isdir(inner_path):
        files = os.listdir(inner_path)
        folder_urls = []
        file_urls = []
        for file in files:
            possible_dir = os.path.join(inner_path, secure_filename(file))
            if os.path.isdir(possible_dir):
                folder_urls.append((file, f"{base_url}/{file}"))
            else:
                file_urls.append((file, f"{base_url}/{file}"))
        if access_level < CAN_EDIT:
            collaborator = False
            upload_url = None
            create_url = None
            delete_url = None
        else:
            collaborator = True
            upload_url = f"/project/{project_id}/upload/{path}"
            create_url = f"/project/{project_id}/create/{path}"
            delete_url = f"/project/{project_id}/delete/{path}"
        return render_template("viewFolder.html",
                               parent_directories=parent_directories,
                               folder_name=path.split("/")[-1],
                               folder_urls=folder_urls,
                               file_urls=file_urls,
                               collaborator=collaborator,
                               upload_url=upload_url,
                               create_url=create_url,
                               delete_url=delete_url)
    else:
        if request.args.get("download", None) is not None:
            return send_file(inner_path, as_attachment=True)
        download_url = f"{base_url}?download"
        return render_template("viewFile.html",
                               parent_directories=parent_directories,
                               filename=path.split("/")[-1],
                               download_url=download_url)


@app.route("/project/<project_id_string>/upload/", methods=["GET", "POST"])
@app.route("/project/<project_id_string>/upload/<path:path>", methods=["GET", "POST"])
def uploadToProject(project_id_string, path=""):
    print("Directory is",path+".",flush=True)
    project_id=int(project_id_string)
    base_url = f"/project/{project_id}/view/{path}"
    project, access_level, is_logged_in=handle_project_id(project_id, CAN_EDIT)
    project_dir = os.path.join(PROJECTS_FOLDER, str(project_id))
    filesystem_dir = os.path.join(project_dir,"filesystem")   
    inner_path = os.path.realpath(os.path.join(filesystem_dir, path))
    print(inner_path, flush=True)
    if not inner_path.startswith(filesystem_dir):
        abort(403)
    if not os.path.exists(inner_path):
        abort(404)    
    if request.method=="POST":
        file = request.files["file"]
        filename = secure_filename(file.filename)
        print(type(file), flush=True)
        file.save(os.path.join(inner_path,filename))
        update_project_time(project_id)
    return redirect(f"/project/{project_id}/view/{path}")


@app.route("/project/<project_id_string>/create/", methods=["GET", "POST"])
@app.route("/project/<project_id_string>/create/<path:path>", methods=["GET", "POST"])
def createProjectDir(project_id_string, path=""):
    print("Directory is",path+".",flush=True)
    project_id=int(project_id_string)
    #base_url = f"/project/{project_id}/view/{path}"
    project, access_level, is_logged_in=handle_project_id(project_id, CAN_EDIT)
    if request.method == "POST":
        project_dir = os.path.join(PROJECTS_FOLDER, str(project_id))
        filesystem_dir = os.path.join(project_dir,"filesystem")   
        outer_path = os.path.realpath(os.path.join(filesystem_dir, path))
        new_dir = os.path.realpath("/"+request.form.get("dir", "/")).strip("/")
        if new_dir == "":
            return redirect(f"/project/{project_id}/view/{path}")
        absolute_path = os.path.realpath(os.path.join(outer_path, new_dir))
        print("paths:",outer_path,new_dir, absolute_path, flush=True)
        if not absolute_path.startswith(filesystem_dir):
            abort(403)
        os.makedirs(absolute_path, exist_ok=True)
        return redirect(f"/project/{project_id}/view/{path}/{new_dir}")
    return redirect(f"/project/{project_id}/view/{path}")  


@app.route("/project/<project_id_string>/delete/", methods=["GET", "POST"])
@app.route("/project/<project_id_string>/delete/<path:path>", methods=["GET", "POST"])
def deleteProjectObject(project_id_string, path=""):
    print("Directory is",path+".",flush=True)
    project_id=int(project_id_string)
    #base_url = f"/project/{project_id}/view/{path}"
    project, access_level, is_logged_in=handle_project_id(project_id, CAN_EDIT)
    if request.method == "POST":
        project_dir = os.path.join(PROJECTS_FOLDER, str(project_id))
        filesystem_dir = os.path.join(project_dir,"filesystem")   
        outer_path = os.path.realpath(os.path.join(filesystem_dir, path))
        delete_path = os.path.realpath("/"+request.form.get("name", "/")).strip("/")
        if delete_path == "":
            return redirect(f"/project/{project_id}/view/{path}")
        absolute_path = os.path.realpath(os.path.join(outer_path, delete_path))
        print("paths:",outer_path, delete_path, absolute_path, flush=True)
        if (not absolute_path.startswith(filesystem_dir)) or absolute_path == filesystem_dir:
            abort(403)
        if os.path.exists(absolute_path):
            if os.path.isdir(absolute_path):
                shutil.rmtree(absolute_path)
            else:
                os.remove(absolute_path)
    return redirect(f"/project/{project_id}/view/{path}")

@login_required
@app.route("/project/<project_id_string>/permission", methods=["GET", "POST"])
def projectPermission(project_id_string):
    project_id=int(project_id_string)
    project, access_level, is_logged_in=handle_project_id(project_id, SUB_OWNER)
    if request.form:
        added_username = request.form.get("username", None)
        if added_username is not None:
            added_user = Users.query.filter_by(username=added_username).first()
            if added_user is not None:
                existing_access = project.access_level(added_user.user_id)
                if existing_access >= access_level:
                    return redirect(f"/project/{project_id}")
                new_access = int(request.form.get("access_level", None))
                print(added_user.username, new_access,flush=True)
                if new_access < NO_ACCESS or new_access > SUB_OWNER:
                    return redirect(f"/project/{project_id}")
                assign_project_access(project_id, added_user.user_id, new_access)
    return redirect(f"/project/{project_id}")


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