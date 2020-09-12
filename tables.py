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

from datetime import datetime, timezone

#Own imports:
from access_names import *
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
    comments = relationship("Comments", back_populates="user")
    
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
    share_links = relationship("ShareLinks", back_populates="project")
    comments = relationship("Comments", back_populates="project")
    
    def route(self): return f"/project/{self.project_id}"
    def folder(self): return f"projects/{self.project_id}"
    def thumbnail_route(self): return f"/project/{self.project_id}/thumbnail"
    
    def assign_project_access(self, user_id, access_level):
        """Assigns or modifies access level of user given by user_id"""
        current_time = datetime.now(timezone.utc)
        existing_access = ProjectPermissions.query.filter_by(project_id=self.project_id, user_id=user_id).first()
        if existing_access is None:
            new_access = ProjectPermissions(project_id=self.project_id,
                                                user_id=user_id,
                                                access_level=access_level,
                                                time_assigned=current_time)
            db.session.add(new_access)
        elif existing_access.access_level != access_level:
            existing_access.access_level = access_level
            existing_access.time_assigned = current_time
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
    
    def access_level(self, user=None):
        """Returns access level of user given by user_id, or default access level if user_id is None"""
        if user is None:
            return self.default_access
        if user.site_access == ADMIN:
            return OWNER
        project_access = ProjectPermissions.query.filter_by(project_id=self.project_id,
                                                                user_id=user.user_id).first()
        if project_access is None:
            return max(self.student_access, self.default_access)
        return max(self.student_access,self.default_access,project_access.access_level)
    
    def user_access_pairs(self):
        """Returns list of tuples (user object, access_level) sorted by access level decreasing,
        then by username lexographically."""
        return sorted([(access.user,access.access_level) for access in self.user_permissions],key=lambda x: (-x[1],x[0].username))
    
    def update_time(self):
        """Updates last edit time of project."""
        current_time = datetime.now(timezone.utc)
        self.time_updated = current_time
        db.session.commit()
    
    def get_description(self):
        project_dir = os.path.join(PROJECTS_FOLDER,str(self.project_id))
        description_file = os.path.join(project_dir,"description.txt")
        if not os.path.exists(description_file):
            return ""
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


class ShareLinks(db.Model):
    __tablename__ = "share_links"
    url_string = Column(String(SHARE_URL_SIZE), primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"))
    access_level_granted = Column(Integer, default=CAN_VIEW)
    time_created = Column(DateTime)
    time_expires = Column(DateTime, default=None)
    user_limit = Column(Integer, default=-1)
    times_used = Column(Integer, default=0)
    
    project = relationship("Projects", back_populates="share_links")


class Comments(db.Model):
    __tablename__ = "comments"
    comment_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    time_commented = Column(DateTime)
    text = Column(Text)

    def get_time_commented(self):
        return self.time_commented.replace(tzinfo=TIMEZONE)
    
    project = relationship("Projects", back_populates="comments")
    user = relationship("Users", back_populates="comments")


class AdminView(ModelView):
    def is_accessible(self):
        if current_user.is_authenticated:
            return current_user.site_access >= ADMIN
        return False


admin = Admin(app)
admin.add_view(AdminView(Users, db.session))
admin.add_view(AdminView(Projects, db.session))
admin.add_view(AdminView(Comments, db.session))
