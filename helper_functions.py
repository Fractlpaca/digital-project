"""
Web app to provide feedback from and to students and teachers.
Author: Joseph Grace
Contains helper functions.
"""

import os

#Own imports:
from permission_names import *
from constants import *
from tables import *

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


def file_location(path):
    return os.path.join(APP_DIR, path)


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