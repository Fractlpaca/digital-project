"""
Web app to provide feedback from and to students and teachers.
Author: Joseph Grace
Contains helper functions.
"""

import os

from secrets import choice
from datetime import datetime, timedelta

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
            access_level = project.access_level(current_user)
        else:
            access_level = project.default_access
        if access_level < threshold_access:
            abort(404)
            #To prevent knoledge of existence of project
        return (project, access_level, is_logged_in)

def format_time_delta(time_delta):
    if time_delta.days>=365:
        years = time_delta.days//365.2422
        return f"{years} year{'s' if years!=1 else ''} ago"
    elif time_delta.days>=7:
        weeks = time_delta.days//7
        return f"{weeks} week{'s' if weeks!=1 else ''} ago"
    elif time_delta.days>=1:
        days = time_delta.days
        return f"{days} day{'s' if days!=1 else ''} ago"
    elif time_delta.seconds>=3600:
        hours = time_delta.seconds//3600
        return f"{hours} hours{'s' if hours!=1 else ''} ago"
    elif time_delta.seconds>=60:
        minutes = time_delta.seconds//60
        return f"{minutes} minute{'s' if minutes!=1 else ''} ago"
    else:
        return "Less than a minute ago"

def set_download_name(project_id, download_info):
    """Takes  download_info 3-tuple, writes to download info file"""
    filename, username, time = download_info
    time = datetime.strftime(time, TIME_FORMAT)
    project_folder = os.path.join(PROJECTS_FOLDER, str(project_id))
    log_name = os.path.join(project_folder, "downloads.txt")
    try:
        download_log = open(log_name, "a")
    except:
        return
    download_log.write(f"{filename},{username},{time}\r\n")

def get_download_info(project_id):
    """Returns set of 3-tuples, (filename, username, time)"""
    project_folder = os.path.join(PROJECTS_FOLDER, str(project_id))
    log_name = os.path.join(project_folder, "downloads.txt")
    try:
        download_log = open(log_name, "r")
    except:
        return set()
    else:
        log_text = download_log.readlines()
        download_log.close()
        file_list = set()
        for entry in log_text:
            try:
                file_name, username, time = entry.strip().split(",")
            except ValueError:
                continue
            else:
                print(time, flush=True)
                time = datetime.strptime(time, TIME_FORMAT)
                time = time.replace(tzinfo=timezone.utc)
                file_list.add((file_name, username, time))
        return file_list

def unique_download_filename(project_id, filename):
    new_filename = filename
    existing_filenames = [line[0] for line in get_download_info(project_id)]
    split_filename = filename.split(".")
    first_name = split_filename[0]
    extensions = ".".join(split_filename[1:])
    counter = 0
    while new_filename in existing_filenames:
        new_filename = f"{first_name}({counter}).{extensions}"
        counter+=1
    return new_filename

def delete_download(project_id, filename):
    project_folder = os.path.join(PROJECTS_FOLDER, str(project_id))
    download_folder = os.path.join(project_folder, "downloads")
    file_path = os.path.join(download_folder, filename)
    if not os.path.exists(file_path):
        return
    os.remove(file_path)
    download_info=get_download_info(project_id)
    for entry in download_info:
        if entry[0]==filename:
            download_info.remove(entry)
            break
    log_name = os.path.join(project_folder, "downloads.txt")
    download_log = open(log_name, "w")
    for entry in download_info:
        try:
            filename, username, time = entry
        except ValueError:
            continue
        else:
            download_log.write(f"{filename},{username},{time.strftime(TIME_FORMAT)}\r\n")
    download_log.close()
    

def get_download(project_id, filename):
    project_folder = os.path.join(PROJECTS_FOLDER, str(project_id))
    download_folder = os.path.join(project_folder, "downloads")
    file_path = os.path.join(download_folder, filename)
    if not os.path.exists(file_path):
        return None
    return send_from_directory(download_folder, filename, as_attachment=True)
    

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