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
from access_names import *
from constants import *
from tables import *
from helper_functions import *


@app.route("/")
def index():
    """
    Home route.
    Restrictions: None
    """
    is_logged_in = current_user.is_authenticated
    user = current_user if is_logged_in else None
    public_projects = Projects.query.filter(Projects.default_access>=CAN_VIEW).all()
    return render_template("index.html",
                           is_logged_in=is_logged_in,
                           user=user,
                           public_projects=public_projects)



@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Route to register an account.
    Restrictions: None
    """
    if request.form:
        username = request.form.get("username")
        if Users.query.filter_by(username=username).first() is not None:
            #Username already exists
            print("Error 1", flush=True)
        else:
            password_plaintext = request.form.get("password")
            password_hash = bcrypt.hash(password_plaintext, rounds=BCRYPT_ROUNDS)
            new_user = Users(username=request.form.get("username"),
                             password_hash=password_hash)
            db.session.add(new_user)
            db.session.commit()
            logout_user()
            login_user(new_user)
            return redirect(url_for("dashboard"))
    is_logged_in = current_user.is_authenticated
    username = current_user.username if is_logged_in else None
    return render_template("register.html", is_logged_in=is_logged_in, username=username)



@app.route("/login", methods = ["GET", "POST"])
def login():
    """
    Route to login.
    Restrictions: None
    """
    logout_user()
    if request.form:
        username = request.form.get("username")
        user = Users.query.filter_by(username=username).first()
        password_plaintext = request.form.get("password")
        if Users.query.filter_by(username=username).first() is None:
            #User does not exist
            print("Error 2", flush=True)
        else:
            if bcrypt.verify(password_plaintext,user.password_hash):
                login_user(user)
                return redirect(url_for("dashboard"))
            else:
                #Wrong password
                print("Error 3", flush=True)
                #Error 2 and 3 must be presented as the same error for security reasons.
    return render_template("login.html", is_logged_in=False)    


login_manager.login_view = "login"


@app.route("/logout")
def logout():
    """
    Route to logout user.
    Restrictions: None.
    """
    logout_user()
    return redirect("/")



@app.route("/dashboard")
@login_required
def dashboard():
    """
    User's dashboard.
    Displays projects owned by them and shared with them.
    Restrictions: Authenticated
    """
    user_id = current_user.get_id()
    projects_owned = current_user.projects_owned
    projects_shared = ProjectPermissions.query.filter(ProjectPermissions.user_id==user_id, CAN_VIEW <= ProjectPermissions.access_level, ProjectPermissions.access_level< OWNER).all()
    projects_shared = [project_access.project for project_access in projects_shared]
    other_projects = Projects.query.filter(or_(Projects.default_access >= CAN_VIEW,Projects.student_access >= CAN_VIEW)).all()
    return render_template("dash.html",
                           user=current_user,
                           projects_owned=projects_owned,
                           projects_shared = projects_shared,
                           other_projects = other_projects,
                           is_logged_in=True)



@app.route("/search")
def search():
    """
    Route for search querys.
    Displays list of projects partially matching the query.
    Restrictions: None
    """
    is_logged_in = current_user.is_authenticated
    user = current_user if is_logged_in else None
    search_text = request.args.get("search","").strip().lower()
    if is_logged_in:
        public_projects = Projects.query.filter(or_(Projects.student_access>=CAN_VIEW, Projects.default_access>=CAN_VIEW)).all()
    else:
        public_projects = Projects.query.filter(Projects.default_access>=CAN_VIEW).all()
    results=[]
    for project in public_projects:
        if search_text in str(project.name).lower() or search_text in str(project.tags).lower():
            results.append(project)
    return render_template("search.html",
                           is_logged_in=is_logged_in,
                           user=user,
                           results=results)  



@app.route("/newProject", methods=["GET", "POST"])
@login_required
def newProject():
    """
    Form submission creates new project and redirects user to the project page.
    Restrictions: Authenticated
    """
    if request.method == "POST":
        name = request.form.get("name","Untitled Project")
        owner_id = current_user.user_id
        new_project = create_project(name,owner_id)
        return redirect("/project/{}".format(new_project.project_id))
    return render_template("newProject.html")



@app.route("/project/<project_id_string>", methods=["GET", "POST"])
def project(project_id_string):
    """
    Route for a project.
    Displays content of project as well as comments and metadata.
    Users with appropiate access may edit the project though this page.
    Restrictions: None (Some page content may be restricted by template)
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string,CAN_VIEW)
    if project is None:
        abort(404)    
    access_level_string = access_messages[access_level]
    route=f"/project/{project.project_id}"
    access_pairs = project.user_access_pairs()
    download_info = list(project.get_download_info())
    current_time=datetime.now(TIMEZONE)
    download_info.sort(key=lambda x:(current_time-x[2],x[0],x[1]))
    download_info =[(filename, username, format_time_delta(datetime.now(timezone.utc)-time)) for filename, username, time in download_info]
    share_links = ShareLinks.query.filter(ShareLinks.project_id==project.project_id, ShareLinks.access_level_granted<=access_level)
    base_template_args = {
        "is_logged_in": is_logged_in,
        "user": (current_user if is_logged_in else None),
        "site_access": (current_user.site_access if is_logged_in else 0),
        "current_time": current_time,
        "format_time_delta": format_time_delta
    }
    project_template_args={
        "project": project,
        "access_level": access_level,
        "route": route,
        "authors": project.authors.replace(",",", "),
        "tags_list": project.tags.split(","),
        "tags": project.tags.replace(",", ", "),
        "description": project.get_description(),
        "download_info": download_info,
        "share_links": share_links,
        "comments": project.comments,
        "access_from_string": access_from_string,
        "access_descriptions": access_descriptions,
        "access_pairs": access_pairs
    }
    content_type=project.content_type
    return render_template("content/game.html",
                           **base_template_args,
                           **project_template_args)



@app.route("/project/<project_id_string>/thumbnail")
def thumbnail(project_id_string):
    """
    Returns the project's thumbnail, or the default if it does not exist.
    Restrictions: CAN_VIEW
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_VIEW)
    if project is None:
        abort(404)
    for extension in THUMBNAIL_EXTENSIONS:
        if os.path.exists(f"projects/{project.project_id}/thumbnail.{extension}"):
            return send_from_directory(f"projects/{project.project_id}", f"thumbnail.{extension}")
    return send_from_directory(f"static/images","default_thumbnail.png")



@app.route("/project/<project_id_string>/comment", methods=["POST"])
@login_required
def comment(project_id_string):
    """
    Form submission posts comment to project.
    Restrictions: Authenticated, CAN_COMMENT
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_COMMENT)
    if project is None:
        abort(404)
    route = f"/project/{project.project_id}"
    
    new_comment_text = request.form.get("text", None)
    current_time = datetime.now(TIMEZONE)
    if new_comment_text is not None and new_comment_text != "":
        new_comment = Comments(project_id=project.project_id,
                               user_id=current_user.user_id if is_logged_in else None,
                               time_commented=current_time,
                               text=new_comment_text)
        db.session.add(new_comment)
        db.session.commit()
    
    return redirect(route)



@app.route("/project/<project_id_string>/deleteComment",methods=["POST"])
@login_required
def deleteComment(project_id_string):
    """
    Form submission deletes comment.
    Restictions: Authenticated, Site Access: MOD
    """
    if current_user.site_access < MOD:
        abort(403)    
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, NO_ACCESS)
    if project is None:
        abort(404)
    try:
        comment_id = int(request.form.get("comment_id",None))
        comment = Comments.query.filter_by(comment_id=comment_id).first()
    except TypeError:
        comment = None
    if comment is not None:
        db.session.delete(comment)
        db.session.commit()
    return redirect(f"/project/{project.project_id}")



@app.route("/project/<project_id_string>/upload", methods=["POST"])
@login_required
def upload(project_id_string):
    """
    Route for uploading downloadable files or playable content.
    Restrictions: Authenticated, CAN_EDIT
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_EDIT)
    if project is None:
        abort(404)
    route = f"/project/{project.project_id}"
    project_folder = os.path.join(PROJECTS_FOLDER,str(project.project_id))
    if request.method == "POST":
        content_type = request.form.get("type", None)
        file = request.files.get("file",None)
        if file is None or content_type is None:
            return redirect(route)
        if content_type == "game":
            if file.mimetype != "application/zip":
                return redirect(route)
            webgl_folder = os.path.join(project_folder,"webgl")            
            shutil.rmtree(webgl_folder, ignore_errors=True)
            os.mkdir(webgl_folder)
            file_path = os.path.join(webgl_folder, "webgl_game.zip")
            file.save(file_path)
            #Unzip file:
            if is_zipfile(os.path.join(webgl_folder, "webgl_game.zip")):
                zipped_file = ZipFile(file_path, "r")
                zipped_file.extractall(path=webgl_folder)
        elif content_type == "downloadable":
            download_folder = os.path.join(project_folder, "downloads")
            if not os.path.exists(download_folder):
                os.mkdir(download_folder)

            filename = request.form.get("filename", None)
            filename = secure_filename(filename or file.filename) 
            filename = project.unique_download_filename(filename)
            
            file_path = os.path.join(download_folder, filename)
            file.save(file_path)
            download_data = (filename, current_user.username, datetime.now(timezone.utc))
            project.set_download_name(download_data)
    return redirect(route)



@app.route("/project/<project_id_string>/webgl",methods=["GET"])
def webGL(project_id_string):
    """
    Returns a send_from_directory of the webgl content ('index.html' file).
    Restrictions: CAN_VIEW
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_VIEW)
    if project is None:
        abort(404)
    return send_from_directory(f"{PROJECTS_FOLDER}/{project.project_id}/webgl","index.html")
    #return "Temporarily disabled"



@app.route("/project/<project_id_string>/<folder>/<path:path>",methods=["GET"])
def gamedata(project_id_string, folder, path):
    """
    Route to serve WebGL content. Returns requested files from within webgl folder.
    Restrictions: CAN_VIEW
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_VIEW)
    if project is None:
        abort(404)
    project_dir = os.path.join(PROJECTS_FOLDER, str(project.project_id))
    content_dir = os.path.join(project_dir,"webgl")
    if folder not in ["TemplateData", "Build"]: abort(404)
    inner_path = os.path.realpath(os.path.join(content_dir, folder))
    inner_path = os.path.realpath(os.path.join(inner_path, path))
    if not inner_path.startswith(content_dir):
        abort(403)
    if not os.path.exists(inner_path):
        abort(404)
    return send_from_directory(content_dir, os.path.join(folder,path))



@app.route("/project/<project_id_string>/download",methods=["GET","POST"])
def download(project_id_string):
    """
    Route to download requested file from the project's downloads folder.
    Restrictions: CAN_VIEW
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_VIEW)
    if project is None:
        abort(404)
    project_dir = os.path.join(PROJECTS_FOLDER, str(project.project_id))    
    download_folder = os.path.join(PROJECTS_FOLDER,"downloads")
    download = project.get_download(request.form.get("filename",""))
    if download is None:
        return redirect(f"/project/{project.project_id}")
    else:
        return download



@app.route("/project/<project_id_string>/deleteDownload",methods=["POST"])
@login_required
def deleteDownload(project_id_string):
    """
    Route to delete requested file from the project's downloads folder.
    Restrictions: Authenticated, CAN_EDIT
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_EDIT)
    if project is None:
        abort(404)
    project.delete_download(request.form.get("filename",""))
    return redirect(f"/project/{project.project_id}")



@app.route("/project/<project_id_string>/access", methods=["POST"])
@login_required
def projectAccess(project_id_string):
    """
    Submission of form sets a specific user's access for the project,
    provided the existing access and requested access does not exceed SUB_OWNER.
    Restrictions: Authenticated, SUB_OWNER
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
    if project is None:
        abort(404) 
    route = f"/project/{project.project_id}"
    if request.form:
        added_username = request.form.get("username", None)
        if added_username is not None:
            added_user = Users.query.filter_by(username=added_username).first()
            if added_user is not None:
                existing_access = project.access_level(added_user)
                if existing_access >= access_level:
                    return redirect(route)
                new_access = access_from_string.get(request.form.get("access_level", None),None)
                if new_access is None:
                    return redirect(route)
                if new_access < NO_ACCESS or new_access > SUB_OWNER:
                    return redirect(route)
                project.assign_project_access(added_user.user_id, new_access)
    return redirect(route)



@app.route("/project/<project_id_string>/deleteAccess", methods=["POST"])
@login_required
def deleteProjectAccess(project_id_string):
    """
    Route for deleting requested specific user access.
    Restrictions: Authenticated, SUB_OWNER
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
    if project is None:
        abort(404) 
    route = f"/project/{project.project_id}"
    if request.form:
        added_username = request.form.get("username", None)
        if added_username is not None:
            added_user = Users.query.filter_by(username=added_username).first()
            if added_user is not None:
                existing_access = ProjectPermissions.query.filter_by(user_id=added_user.user_id,project_id=project.project_id).first()
                if existing_access.access_level >= access_level:
                    return redirect(route)
                else:
                    db.session.delete(existing_access)
                    db.session.commit()
    return redirect(route)



@app.route("/project/<project_id_string>/createShareLink", methods=["POST"])
@login_required
def create_share_link(project_id_string):
    """
    Form submission creates a sharable link.
    Restrictions: Authenticated, SUB_OWNER.
    """
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



@app.route("/project/<project_id_string>/invite/<invite_string>")
@login_required
def invite(project_id_string, invite_string):
    """
    A valid invite string will grant the current user an access to a project,
    then redirect them to that project.
    Restrictions: Authenticated
    """
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
    existing_access = project.access_level(current_user)
    if share_link.access_level_granted <= existing_access:
        return redirect(route)
    
    share_link.times_used += 1
    project.assign_project_access(current_user.user_id, min(SUB_OWNER, share_link.access_level_granted))
    db.session.commit()
    return redirect(route)



@app.route("/project/<project_id_string>/simpleShare",methods=["POST"])
@login_required
def simpleShare(project_id_string):
    """
    Configures project default access levels to a preset.
    Restrictions: Authenticated
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
    if project is None:
        abort(404)
    setting = request.form.get("setting", None)
    if setting is not None:
        if setting == "private":
            project.default_access=NO_ACCESS
            project.student_access=NO_ACCESS
        elif setting == "class":
            project.default_access=NO_ACCESS
            project.student_access=CAN_COMMENT
        elif setting == "public":
            project.default_access = CAN_VIEW
            project.student_access = CAN_COMMENT
    db.session.commit()
    return redirect(f"/project/{project.project_id}")



@app.route("/project/<project_id_string>/edit", methods=["GET","POST"])
@login_required
def editProject(project_id_string):
    """
    Route for editing title, tags, authors, description, and thumbnail of project.
    Restrictions: Authenticated, SUB_OWNER
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
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
        
        thumbnail_file = request.files.get("thumbnail")
        thumbnail_path = os.path.join(PROJECTS_FOLDER,str(project.project_id))
        thumbnail_path = os.path.join(thumbnail_path, "thumbnail")
        if thumbnail_file is not None:
            for extension in THUMBNAIL_EXTENSIONS:
                if thumbnail_file.mimetype==f"image/{extension}":
                    thumbnail_file.save(f"{thumbnail_path}.{extension}")
        project.update_time()
         
    return redirect(f"/project/{project.project_id}")





if __name__ == "__main__":
    if not os.path.exists(file_location(SECRET_KEY_FILENAME)):
        #Create session secret key
        generate_key(SECRET_KEY_FILENAME, 24)
    app.secret_key = get_key(SECRET_KEY_FILENAME)
    if not os.path.exists(file_location(database_file)):
        db.create_all()
    

    app.run(debug=True)