"""
Web app to provide feedback from and to students and teachers.
Author: Joseph Grace
This document contains app routes and initialisation.
"""

import os
import shutil
from zipfile import ZipFile, is_zipfile

from secrets import compare_digest, token_urlsafe
from passlib.hash import bcrypt
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta

#Own imports:
from permission_names import *
from constants import *
from tables import *
from helper_functions import *

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
    #return send_from_directory(f"{PROJECTS_FOLDER}/{project.project_id}/webgl/","index.html")
    return "Temporarily disabled"

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
@app.route("/project/<project_id_string>/invite/<invite_string>")
def invite(project_id_string, invite_string):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, NO_ACCESS)
    if project is None:
        abort(404)
    current_time = datetime.now(timezone.utc)
    share_link = ShareLinks.query.filter_by(url_string=invite_string,project_id=project.project_id).first()
    if share_link is None:
        abort(404)
    if share_link.user_limit != -1 and share_link.times_used >= share_link.user_limit:
        abort(404)
    if share_link.time_expires is not None and current_time > share_link.time_expires:
        abort(404)
    route = f"/project/{project.project_id}"
    existing_access = project.access_level(current_user.user_id)
    if share_link.access_level_granted <= existing_access:
        return redirect(route)
    
    share_link.times_used += 1
    project.assign_project_access(current_user.user_id, min(SUB_OWNER, share_link.access_level_granted))
    db.session.commit()
    return redirect(route)

@login_required
@app.route("/project/<project_id_string>/createShareLink", methods=["POST"])
def create_share_link(project_id_string):
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
    if project is None:
        abort(404)
    route = f"/project/{project.project_id}"
    if request.method == "POST":
        form = request.form
        access_string = form.get("access", None)
        access_level_granted = access_from_string.get(access_string, None)
        if access_level_granted is None:
            return redirect(f"/project/{project.project_id}")
        do_limit = form.get("do_limit", None) == "do_limit"
        if do_limit:
            try:
                user_limit = int(form.get("user_limit", 20))
            except ValueError:
                user_limit = 20
        else:
            user_limit = -1
        current_time = datetime.now(timezone.utc)
        expirable = form.get("expirable", None) == "expirable"
        if expirable:
            try:
                days = max(0, int(form.get("days", 7)))
                hours = max(0, int(form.get("hours", 0)))
                minutes = max(0, int(form.get("minutes", 0)))
                duration = timedelta(days=days, hours=hours, minutes=minutes)
            except ValueError:
                duration = timedelta(days=7)
            
            time_expires = current_time + duration
        else:
            time_expires = None
        print(access_level)
        print(do_limit)
        print(user_limit)
        print(expirable)
        print(time_expires, flush=True)
        url_string = token_urlsafe(SHARE_URL_SIZE)
        share_link = ShareLinks(url_string=url_string,
                                project_id=project.project_id,
                                access_level_granted=access_level_granted,
                                time_created=current_time,
                                time_expires=time_expires,
                                user_limit=user_limit)
        
        project.update_time()
        db.session.add(share_link)
        db.session.commit()
    return redirect(route)
    


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