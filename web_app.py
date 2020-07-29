"""
Web app to provide feedback from and to students and teachers
Author: Joseph Grace
"""

import os
import shutil
from flask import Flask, request, url_for, redirect, render_template, render_template_string, flash, session, abort, send_from_directory, send_file
from flask_login import UserMixin, LoginManager, login_required, login_user, logout_user, current_user
from passlib.hash import bcrypt
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from zipfile import ZipFile, is_zipfile

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, or_
from sqlalchemy.orm import relationship

#Own imports:
from permission_names import *
from constants import *


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
    tags = Column(Text(), default="")
    authors = Column(Text(), default="")
    content_type = Column(Text(), default="none", nullable=False)
    
    user_permissions = relationship("ProjectPermissions", back_populates="project")
    
    def assign_project_access(self, user_id, access_level):
        """Assigns or modifies access level of user given by user_id"""
        current_time = datetime.now(timezone.utc)
        existing_permission = ProjectPermissions.query.filter_by(project_id=self.project_id, user_id=user_id).first()
        if existing_permission is None:
            new_permission = ProjectPermissions(project_id=self.project_id,
                                                user_id=user_id,
                                                access_level=access_level,
                                                time_assigned=current_time)
            db.session.add(new_permission)
        elif existing_permission.access_level != access_level:
            existing_permission.access_level = access_level
            existing_permission.time_assigned = current_time
        self.update_time()  
        db.session.commit()
    
    def set_tags(self, tags):
        tag_set = set(tag.strip().lower() for tag in tags.split(","))
        if "" in tag_set:
            tag_set.remove("")
        self.tags=','.join(sorted(tag_set))
        db.session.commit()
        self.update_time()
    
    def set_authors(self, authors):
        author_list = set(author.strip() for author in authors.split(","))
        self.authors=','.join(sorted(author_list))
        db.session.commit()
        self.update_time()   
    
    def access_level(self, user_id=None):
        """Returns access level of user given by user_id, or default access level if user_id is None"""
        if user_id is None:
            return self.default_access
        project_permission = ProjectPermissions.query.filter_by(project_id=self.project_id,
                                                                user_id=user_id).first()
        if project_permission is None:
            return self.student_access
        return project_permission.access_level
    
    def user_permission_pairs(self):
        """Returns list of tuples (user object, permission_level) sorted by permission level decreasing,
        then by username lexographically."""
        return sorted([(permission.user,permission.access_level) for permission in self.user_permissions],key=lambda x: (-x[1],x[0].username))
    
    def update_time(self):
        """Updates last edit time of project."""
        current_time = datetime.now(timezone.utc)
        self.time_updated = current_time
        db.session.commit()
    
    def get_description(self):
        project_dir = os.path.join(PROJECTS_FOLDER,str(self.project_id))
        description_file = os.path.join(project_dir,"description.txt")
        if not os.path.exists(description_file):
            return None
        else:
            file = open(description_file, "r")
            text = file.read()
            file.close()
            self.update_time()
            return text
    
    def set_description(self, text):
        project_dir = os.path.join(PROJECTS_FOLDER,str(self.project_id))
        description_file = os.path.join(project_dir,"description.txt")
        file = open(description_file, "w")
        file.write(text)
        file.close()
        self.update_time()       
    
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
                   content_type="none",
                   default_access=PROJECT_DEFAULT_ACCESS,
                   student_access=PROJECT_STUDENT_ACCESS,
                   class_access=PROJECT_CLASS_ACCESS,
                   teacher_access=PROJECT_TEACHER_ACCESS):
    """Creates and returns a Project Object with the given parameters"""
    current_time = datetime.now(timezone.utc)
    new_project = Projects(name=name,
                           owner_id=owner_id,
                           content_type=content_type,
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
    db.session.add(owner_permission_level)
    db.session.commit()
    return new_project



def handle_project_id_string(project_id_string, threshold_access=CAN_VIEW):
    """Takes project id string, and a threshold access the user must meet,
    and returns a 3-tuple (project object, access_level of user, whether user is logged in)"""
    is_logged_in = current_user.is_authenticated    
    try:
        project_id=int(project_id_string)    
    except ValueError:
        return (None, NO_ACCESS, is_logged_in)
    else:
        project = Projects.query.filter_by(project_id=project_id).first()
        if project is None:
            abort(404)
        if is_logged_in:
            access_level = project.access_level(current_user.user_id)
        else:
            access_level = project.default_access
        if access_level < threshold_access:
            abort(404)
            #To prevent knoledge of existence of project
        return (project, access_level, is_logged_in)


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
    if request.method == "POST":
        name = request.form.get("name","Untitled Project")
        owner_id = current_user.user_id
        new_project = create_project(name=name,
                                     owner_id=owner_id)
        return redirect("/project/{}".format(new_project.project_id))
    return render_template("newProject.html")


@app.route("/project/<project_id_string>", methods=["GET", "POST"])
def project(project_id_string):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string,CAN_VIEW)
    if project is None:
        abort(404)    
    access_level_string = access_messages[access_level]
    route=f"/project/{project.project_id}"
    permission_pairs = project.user_permission_pairs()
    permission_pair_names = [(user.username, permission_descriptions[permission]) for user, permission in permission_pairs]
    print(permission_pair_names, flush=True)
    template_args = {"project": project,
                     "is_logged_in": is_logged_in,
                     "username": (current_user.username if is_logged_in else None),
                     "access_level": access_level,
                     "access_level_string": access_level_string,
                     "route": route,
                     "upload_route": f"{route}/upload",
                     "permission_pair_names": permission_pair_names,
                     "authors": project.authors.replace(",",", "),
                     "tags_list": project.tags.split(","),
                     "tags": project.tags.replace(",", ", "),
                     "description": project.get_description()
    }
    content_type=project.content_type
    return render_template("content/game.html",
                           **template_args)


@app.route("/project/<project_id_string>/webgl",methods=["GET"])
def webGL(project_id_string):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_VIEW)
    if project is None:
        abort(404)    
    return send_from_directory(f"{PROJECTS_FOLDER}/{project.project_id}/webgl/","index.html")
    #return "Temporarily disabled"

@app.route("/project/<project_id_string>/<folder>/<path:path>",methods=["GET"])
def gamedata(project_id_string, folder, path):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_VIEW)
    if project is None:
        abort(404)
    project_dir = os.path.join(PROJECTS_FOLDER, str(project.project_id))
    content_dir = os.path.join(project_dir,"webgl")
    if folder not in ["TemplateData", "Build"]: abort(404)
    inner_path = os.path.realpath(os.path.join(content_dir, folder))
    inner_path = os.path.realpath(os.path.join(inner_path, path))
    print(inner_path, flush=True)
    if not inner_path.startswith(content_dir):
        abort(403)
    if not os.path.exists(inner_path):
        abort(404)
    return send_from_directory(content_dir, os.path.join(folder,path))

@app.route("/project/<project_id_string>/edit", methods=["GET","POST"])
@login_required
def editProject(project_id_string):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_EDIT)
    if project is None:
        abort(404)    
    if request.method == "POST":
        form = request.form
        title = form.get("title", "")
        if title != "":
            project.name = title
        
        authors = form.get("authors", "")
        if authors != "":
            project.set_authors(authors)
        
        description = form.get("description", "")
        if description != "":
            project.set_description(description)
        
        tags = form.get("tags", "")
        if tags != "":
            project.set_tags(tags)
        
    return redirect(f"/project/{project.project_id}")

@app.route("/project/<project_id_string>/upload", methods=["POST"])
def upload(project_id_string):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_EDIT)
    if project is None:
        abort(404)
    route = f"/project/{project.project_id}"
    project_folder = os.path.join(PROJECTS_FOLDER,str(project.project_id))
    webgl_folder = os.path.join(project_folder,"webgl")
    if request.method == "POST":
        content_type = request.form.get("type", None)
        file = request.files.get("file",None)
        if content_type is None or file is None:
            return redirect(f"/project/{project.project_id}")
        if content_type == "game":
            if file.mimetype != "application/zip":
                return redirect(route)
            shutil.rmtree(webgl_folder, ignore_errors=True)
            os.mkdir(webgl_folder)
            file_path = os.path.join(webgl_folder, "webgl_game.zip")
            file.save(file_path)
            #Unzip file:
            if is_zipfile(os.path.join(webgl_folder, "webgl_game.zip")):
                zipped_file = ZipFile(file_path, "r")
                zipped_file.extractall(path=webgl_folder)
            
    return redirect(route)
    
    
@login_required
@app.route("/project/<project_id_string>/permission", methods=["POST"])
def projectPermission(project_id_string):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
    if project is None:
        abort(404)    
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
                project.assign_project_access(added_user.user_id, new_access)
    return redirect(f"/project/{project_id}")

@login_required
@app.route("/project/<project_id_string>/setAuthors", methods=["POST"])
def setAuthors(project_id_str):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
    if project is None:
        abort(404)    
    author_names = request.form.get("names","")
    project.setAuthors(author_names)
    return redirect(f"/project/{project_id}")

@login_required
@app.route("/project/<project_id_string>/setTags", methods=["POST"])
def setTags(project_id_string):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
    if project is None:
        abort(404)    
    author_names = request.form.get("tags","")
    project.setTags(tags)
    return redirect(f"/project/{project_id}")

@login_required
@app.route("/project/<project_id_string>/changeName", methods=["POST"])
def changeName(project_id_string):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
    if project is None:
        abort(404)    
    new_name = request.form.get("name","Untitled")
    project.name = new_name
    db.session.commit()
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