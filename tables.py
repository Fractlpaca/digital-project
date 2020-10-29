"""
Web app to provide feedback from and to students and teachers.
Author: Joseph Grace
Contains flask_sqlalchemy database and flask app initialisation.
"""

from flask import Flask, request, url_for, redirect, render_template, render_template_string, flash, session, abort, send_from_directory, send_file
from flask_login import UserMixin, LoginManager, login_required, login_user, logout_user, current_user
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, or_
from sqlalchemy.orm import relationship

from werkzeug.utils import secure_filename

from datetime import datetime, timezone, timedelta

#Own imports:
from access_names import *
from constants import *
from helper_functions import *


database_file = "sqlite:///{}".format(os.path.join(APP_DIR,"database.db")) #Get path to database file

app = Flask(__name__) #define app
app.config["SQLALCHEMY_DATABASE_URI"] = database_file #give path of database to app
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * UPLOAD_MAX_SIZE_MB
db = SQLAlchemy(app) #connect to database

#Using user structure for flask_login:
class Users(UserMixin, db.Model):
    __tablename__ = "users"

    #Columns
    user_id = Column(String, primary_key=True)
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    profile_pic_url = Column(Text, nullable=False)
    #username = Column(String(20), nullable=False, unique=True)
    #password_hash = Column(String(128), nullable = False)
    site_access = Column(Integer, default=0)

    def get_id(self):
        return str(self.user_id)
    
    #Relationships
    projects_owned = relationship("Projects", back_populates="owner")
    project_permissions = relationship("ProjectPermissions", back_populates="user")
    comments = relationship("Comments", back_populates="user")
    
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def user_loader(user_id):
    return Users.query.get(user_id)


class Projects(db.Model):
    __tablename__ = "projects"

    #Columns
    project_id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String, ForeignKey("users.user_id"), nullable = False)
    name = Column(String(50))
    default_access = Column(Integer, default=PROJECT_DEFAULT_ACCESS)
    student_access = Column(Integer, default=PROJECT_STUDENT_ACCESS)
    time_created = Column(DateTime)
    time_updated = Column(DateTime)
    #Comma seperated tags
    tags = Column(Text(), default="")
    #Comma seperated authors
    authors = Column(Text(), default="")
    content_type = Column(Text(), default="none", nullable=False)
    
    #Relationships
    user_permissions = relationship("ProjectPermissions", back_populates="project")
    share_links = relationship("ShareLinks", back_populates="project")
    comments = relationship("Comments", back_populates="project")
    owner = relationship("Users", back_populates="projects_owned")
    

    def route(self): return f"/project/{str(self.project_id)}"
    def thumbnail_route(self): return f"/project/{self.project_id}/thumbnail"
    def folder(self): return os.path.join(PROJECTS_FOLDER, str(self.project_id))


    def get_download(self, filename):
        """
        Returns the send_from_directory file with name 'filename' if the file exists in the
        project's downloads folder, else None.
        """
        project_folder = self.folder()
        download_folder = os.path.join(project_folder, "downloads")
        file_path = os.path.join(download_folder, filename)
        if not os.path.exists(file_path):
            return None
        return send_from_directory(download_folder, filename, as_attachment=True)


    def assign_project_access(self, user_id, access_level):
        """
        Assigns or modifies access level of user given by user_id to be the given access level.
        The user cannot be the owner of the project.
        Returns the modified or created ProjectPermissions object.
        """
        current_time = datetime.now(timezone.utc)
        existing_access = ProjectPermissions.query.filter_by(project_id=self.project_id, user_id=user_id).first()
        if existing_access is None:
            #Create new permission
            new_access = ProjectPermissions(project_id=self.project_id,
                                                user_id=user_id,
                                                access_level=access_level,
                                                time_assigned=current_time)
            db.session.add(new_access)
        elif existing_access.access_level != access_level and existing_access.access_level < OWNER:
            #Update the access level and time assigned.
            existing_access.access_level = access_level
            existing_access.time_assigned = current_time
        db.session.commit()
        #If a permission already existed, return modified access, else return new access.
        return existing_access or new_access
    

    def set_tags(self, tags):
        """
        Sets the tags of the project.
        Tags are stored as a comma-separated strings from the 'tags' list.
        """
        tag_set = set(tag.strip().lower() for tag in tags.split(","))
        if "" in tag_set:
            tag_set.remove("")
        self.tags=','.join(sorted(tag_set))
        db.session.commit()
        self.update_time()
    

    def set_authors(self, authors):
        """
        Sets the authors of the project.
        Authors are stored as a comma-separated strings from the 'authors' list.
        """
        author_list = set(author.strip() for author in authors.split(","))
        if "" in tag_set:
            tag_set.remove("")
        self.authors=','.join(sorted(author_list))
        db.session.commit()
        self.update_time()   
    

    def access_level(self, user=None):
        """
        Returns access level of user,
        or default access level if user is None.
        """
        if user is None:
            return self.default_access
        if user.site_access == ADMIN:
            return OWNER
        elif user.site_access == MOD:
            return CAN_COMMENT
        
        #Attempt to find project access:
        project_access = ProjectPermissions.query.filter_by(project_id=self.project_id,
                                                                user_id=user.user_id).first()
        if project_access is None:
            return max(self.student_access, self.default_access)
        return max(self.student_access,self.default_access,project_access.access_level)
    

    def update_time(self):
        """Updates last edit time of project."""
        current_time = get_current_time()
        self.time_updated = current_time
        db.session.commit()
    

    def get_description(self):
        """
        Returns text from the 'description.txt' file in the project folder.
        """
        project_dir = self.folder()
        description_file = os.path.join(project_dir,"description.txt")
        if not os.path.exists(description_file):
            return ""
        else:
            file = open(description_file, "r")
            text = file.read()
            file.close()
            return text
    

    def set_description(self, text):
        """
        Writes text to 'description.txt' file in project folder.
        """
        project_dir = self.folder()
        description_file = os.path.join(project_dir,"description.txt")
        file = open(description_file, "w")
        file.write(text)
        file.close()
        self.update_time()      


    def add_download_info(self, download_info):
        """Takes  download_info 3-tuple, writes to download info file."""
        filename, username, time = download_info
        #Format time to string
        time = time_to_string(time)
        project_folder = self.folder()
        log_name = os.path.join(project_folder, "downloads.txt")
        try:
            download_log = open(log_name, "a")
        except:
            return
        download_log.write(f"{filename},{username},{time}\r\n")
        self.update_time()


    def get_download_info(self):
        """Returns set of 3-tuples, (filename, username, time) from download log."""
        project_folder = self.folder()
        log_name = os.path.join(project_folder, "downloads.txt")
        try:
            download_log = open(log_name, "r")
        except:
            return set()
        
        log_text = download_log.readlines()
        download_log.close()
        file_set = set()
        for entry in log_text:
            try:
                filename, username, time = entry.strip().split(",")
            except ValueError:
                continue
            else:
                time = string_to_time(time)
                file_set.add((filename, username, time))
        return file_set


    def unique_download_filename(self, filename):
        """
        Returns a secure filename based on given filename
        which does not already exist in the project's downloads folder.
        """
        new_filename = secure_filename(filename)
        existing_filenames = set(line[0] for line in self.get_download_info())
        split_filename = filename.split(".")
        first_name = split_filename[0]
        extensions = ".".join(split_filename[1:])
        counter = 1
        while new_filename in existing_filenames:
            new_filename = secure_filename(f"{first_name}{counter}.{extensions}")
            counter+=1
        return new_filename


    def delete_download(self, filename):
        """
        Attemps to delete file with name 'filename' from the project's downloads folder.
        Returns ajax response.
        """
        project_folder = self.folder()
        download_info=self.get_download_info()
        for entry in download_info:
            if entry[0]==filename:
                download_info.remove(entry)
                break
        log_name = os.path.join(project_folder, "downloads.txt")

        #Rewrite download log
        download_log = open(log_name, "w")
        for entry in download_info:
            try:
                filename, username, time = entry
                time = time_to_string(time)
            except ValueError:
                continue
            except AttributeError:
                continue
            else:
                download_log.write(f"{filename},{username},{time}\r\n")
        download_log.close()

        download_folder = os.path.join(project_folder, "downloads")
        file_path = os.path.join(download_folder, filename)
        if not os.path.exists(file_path):
            return "File not found", 404
        os.remove(file_path)
        self.update_time()
        return "OK"



class ProjectPermissions(db.Model):
    __tablename__ = "project_permissions"

    #Columns
    access_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"))
    user_id = Column(String, ForeignKey("users.user_id"))
    access_level = Column(Integer)
    time_assigned = Column(DateTime)

    #Relationships
    project = relationship("Projects", back_populates="user_permissions")
    user = relationship("Users", back_populates="project_permissions")


class ShareLinks(db.Model):
    __tablename__ = "share_links"

    #Columns
    url_string = Column(String(SHARE_URL_SIZE), primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"))
    access_level_granted = Column(Integer, default=CAN_VIEW)
    time_created = Column(DateTime)
    time_expires = Column(DateTime, default=None)
    user_limit = Column(Integer, default=-1)
    times_used = Column(Integer, default=0)
    
    #Relationships
    project = relationship("Projects", back_populates="share_links")


class Comments(db.Model):
    __tablename__ = "comments"

    #Columns
    comment_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    user_id = Column(String, ForeignKey("users.user_id"))
    time_commented = Column(DateTime)
    text = Column(Text)

    def get_time_commented(self):
        """
        Returns the time of comment creation as an aware datetime object.
        The datetime object will be assumed to be in the timezone TIMEZONE.
        """
        return self.time_commented.replace(tzinfo=TIMEZONE)
    
    #Relationships
    project = relationship("Projects", back_populates="comments")
    user = relationship("Users", back_populates="comments")


class AdminView(ModelView):
    def is_accessible(self):
        """Returns whether the current user is an administrator."""

        if current_user.is_authenticated:
            return current_user.site_access >= ADMIN
        return False

#Setup for flask_admin
admin = Admin(app)
admin.add_view(AdminView(Users, db.session))
admin.add_view(AdminView(Projects, db.session))
admin.add_view(AdminView(Comments, db.session))


#Project Helper Functions

def create_project(name,
                   owner_id,
                   content_type="none",
                   default_access=PROJECT_DEFAULT_ACCESS,
                   student_access=PROJECT_STUDENT_ACCESS,
                   class_access=PROJECT_CLASS_ACCESS):
    """Creates and returns a Project Object with the given parameters"""
    current_time = datetime.now(timezone.utc)
    new_project = Projects(name=name,
                           owner_id=owner_id,
                           content_type=content_type,
                           time_created=current_time,
                           time_updated=current_time,
                           default_access=default_access,
                           student_access=student_access)
    db.session.add(new_project)
    db.session.commit()
    owner_access_level = ProjectPermissions(user_id=owner_id,
                                                project_id=new_project.project_id,
                                                access_level=OWNER,
                                                time_assigned=current_time)
    project_folder = os.path.join(PROJECTS_FOLDER,str(new_project.project_id))
    os.mkdir(project_folder)
    db.session.add(owner_access_level)
    db.session.commit()
    return new_project



def handle_project_id_string(project_id_string, threshold_access=CAN_VIEW):
    """Takes project id string, and a threshold access the user must meet,
    and returns a 3-tuple (project object, access_level of user, whether user is logged in)"""
    is_logged_in = current_user.is_authenticated    
    try:
        project_id=int(project_id_string)    
    except ValueError:
        #project_id was not valid
        abort(400)
    else:
        project = Projects.query.filter_by(project_id=project_id).first()
        if project is None:
            #Project with given id does not exist.
            abort(404)
        if is_logged_in:
            access_level = project.access_level(current_user)
        else:
            access_level = project.default_access
        if access_level < threshold_access:
            #Access denied
            abort(403)
        return (project, access_level, is_logged_in)