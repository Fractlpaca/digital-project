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

#Imports for Google Login
from oauthlib.oauth2 import WebApplicationClient
import requests
import json


#Own imports:
from access_names import *
from constants import *
from tables import *
from helper_functions import *


client = WebApplicationClient(GOOGLE_CLIENT_ID)

@app.route("/")
def index():
    """
    Home route.
    Restrictions: None
    """
    is_logged_in = current_user.is_authenticated
    user = current_user if is_logged_in else None
    #Filter projects by public projects and sort by activity: latest first.
    public_projects = Projects.query.filter(Projects.default_access>=CAN_VIEW).order_by(Projects.time_updated.desc()).all()
    return render_template("index.html",
                           is_logged_in=is_logged_in,
                           user=user,
                           public_projects=public_projects)



@app.route("/login")
def login():
    """
    Redirect user to google login.
    Code taken from article: 'https://realpython.com/flask-google-login/'.
    Restrictions: None
    """
    #Logout user:
    logout_user()

    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

login_manager.login_view = "login"



@app.route("/login/callback")
def login_callback():
    """
    Log user in once they are verified by google.
    Code taken from 'https://realpython.com/flask-google-login/'
    """
    # Get authorization code Google sent back to you
    code = request.args.get("code")
    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    # Prepare and send a request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))
    # Now that you have tokens (yay) let's find and hit the URL
    # from Google that gives you the user's profile information,
    # including their Google profile image and email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    # You want to make sure their email is verified.
    # The user authenticated with Google, authorized your
    # app, and now you've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        if users_email.split("@")[1] not in ALLOWED_EMAIL_DOMAINS:
            return "Please log in with a school account.", 400
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["name"]
    else:
        return "User email not available or not verified by Google.", 400

    #Own code follows:

    #Check if user exists:
    user = Users.query.filter_by(user_id=unique_id).first()

    if user is None:
        #Create user
        user = Users(user_id=unique_id,
                    name=users_name,
                    email=users_email,
                    profile_pic_url=picture)
        db.session.add(user)
        db.session.commit()

    #Log user in

    login_user(user, remember=True)
    #Redirect to user's dashboard.
    return redirect(url_for("dashboard"))


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
    #Sort projects by latest first
    projects_owned.sort(key=lambda x:x.time_updated, reverse=True)

    #Filter project permissions for shared projects
    projects_shared = ProjectPermissions.query.filter(ProjectPermissions.user_id==user_id, CAN_VIEW <= ProjectPermissions.access_level, ProjectPermissions.access_level< OWNER).all()

    #Extract projects from project permissions
    projects_shared = [project_access.project for project_access in projects_shared]

    #Sort projects by latest first
    projects_shared.sort(key=lambda x:x.time_updated, reverse=True)

    #Public projects
    #other_projects = Projects.query.filter(or_(Projects.default_access >= CAN_VIEW,Projects.student_access >= CAN_VIEW)).order_by(Projects.time_updated.desc()).all()
    return render_template("dash.html",
                           user=current_user,
                           projects_owned=projects_owned,
                           projects_shared = projects_shared,
                           #other_projects = other_projects,
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
    #Get public projects
    if is_logged_in:
        public_projects = Projects.query.filter(or_(Projects.student_access>=CAN_VIEW, Projects.default_access>=CAN_VIEW)).all()
    else:
        public_projects = Projects.query.filter(Projects.default_access>=CAN_VIEW).all()
    results=[]
    #Filter results
    for project in public_projects:
        if search_text in str(project.name).lower() or search_text in str(project.tags).lower():
            results.append(project)
    #Sort results by alphabetical order, then latest first.
    results.sort(key=lambda x:x.time_updated, reverse=True)
    results.sort(key=lambda x:x.name)

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
    return render_template("newProject.html", user=current_user, is_logged_in=True)



@app.route("/project/<project_id_string>", methods=["GET", "POST"])
def project(project_id_string):
    """
    Route for a project.
    Displays content of project as well as comments and metadata.
    Users with appropiate access may edit the project though this page.
    Restrictions: None (Some page content may be restricted by template)
    """
    #Check valid and accessable project
    project, access_level, is_logged_in=handle_project_id_string(project_id_string,CAN_VIEW)
    if project is None:
        abort(404)
    route=f"/project/{project.project_id}"
    download_info = list(project.get_download_info())
    current_time=get_current_time()
    #Sort download info by most recent first, then alphabetical, then uploader name
    download_info.sort(key=lambda x:(current_time-x[2],x[0],x[1]))
    #Change time field to time difference string
    download_info =[(filename, name, format_time_delta(current_time-time)) for filename, name, time in download_info]
    share_links = ShareLinks.query.filter(ShareLinks.project_id==project.project_id, ShareLinks.access_level_granted<=access_level)
    base_template_args = {
        "is_logged_in": is_logged_in,
        "user": (current_user if is_logged_in else None),
        "site_access": (current_user.site_access if is_logged_in else NORMAL),
        "current_time": current_time,
        "format_time_delta": format_time_delta
    }
    #Project specific template parameters.
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
        "user_permissions": project.user_permissions
    }
    content_type=project.content_type
    return render_template("content/game.html",
                           **base_template_args,
                           **project_template_args)



@app.route("/deleteProject", methods=["POST"])
@login_required
def deleteProject():
    """
    Deletes given project on form submission.
    Restrictions: OWNER
    """

    project_id_string = request.form.get("project_id",None)
    if project_id_string is None:
        abort(404)

    project, access_level, is_logged_in=handle_project_id_string(project_id_string, OWNER)
    if project is None:
        abort(404)

    db.session.delete(project)
    db.session.commit()

    project_folder = project.folder()
    shutil.rmtree(project_folder)

    return redirect(url_for("dashboard"))




@app.route("/project/<project_id_string>/thumbnail")
def thumbnail(project_id_string):
    """
    Returns the project's thumbnail, or the default if it does not exist.
    Restrictions: CAN_VIEW
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_VIEW)
    if project is None:
        abort(404)
    #Check for thumbnails in project folder.
    for extension in THUMBNAIL_EXTENSIONS:
        if os.path.exists(f"projects/{project.project_id}/thumbnail"):
            return send_from_directory(f"projects/{project.project_id}","thumbnail")
    #Return default thumbnail if thumbnail not found
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
    current_time = get_current_time()
    if new_comment_text is not None and new_comment_text != "":
        new_comment = Comments(project_id=project.project_id,
                               user_id=current_user.user_id if is_logged_in else None,
                               time_commented=current_time,
                               text=new_comment_text)
        db.session.add(new_comment)
        db.session.commit()
        return render_template( "ajax_responses/comment.html",
                                comment=new_comment,
                                current_time=get_current_time(),
                                site_access=current_user.site_access,
                                format_time_delta=format_time_delta,
                                route=route
        )
    else:
        return "Comment may not be empty.",400



@app.route("/project/<project_id_string>/deleteComment",methods=["POST"])
@login_required
def deleteComment(project_id_string):
    """
    Form submission deletes comment.
    Restictions: Authenticated, Site Access: MOD
    """
    #Only mods/admins can delete comments
    if current_user.site_access < MOD:
        abort(403)

    project, access_level, is_logged_in=handle_project_id_string(project_id_string, NO_ACCESS)
    if project is None:
        abort(404)

    try:
        comment_id = int(request.form.get("comment_id",None))
        comment = Comments.query.filter_by(comment_id=comment_id).first()
    except TypeError:
        #In the case the comment_id was not an int
        comment = None
    if comment is not None:
        db.session.delete(comment)
        db.session.commit()
    else:
        return "Comment could not be found.", 404

    return "OK"



@app.route("/project/<project_id_string>/upload/content", methods=["POST"])
@login_required
def upload_content(project_id_string):
    """
    Route for uploading playable content.
    Restrictions: Authenticated, CAN_EDIT
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_EDIT)
    if project is None:
        abort(404)

    route = f"/project/{project.project_id}"
    project_folder = project.folder()

    content_type = request.form.get("type", None)
    file = request.files.get("file",None)
    if file is None or content_type is None:
        return "Invalid input.", 400
    if content_type == "game":
        if file.mimetype != "application/zip":
            return "WebGL content must be a zip file.", 400
        webgl_folder = os.path.join(project_folder,"webgl")

        #Delete contents of webgl folder
        shutil.rmtree(webgl_folder, ignore_errors=True)
        os.mkdir(webgl_folder)

        #Save zip file
        file_path = os.path.join(webgl_folder, "webgl_game.zip")
        file.save(file_path)

        #Extract files to webgl folder
        if is_zipfile(os.path.join(webgl_folder, "webgl_game.zip")):
            zipped_file = ZipFile(file_path, "r")
            zipped_file.extractall(path=webgl_folder)

        project.update_time()

        current_time=get_current_time().strftime("%s")
        ajax_response= f'<iframe id="player" src="/project/{project.project_id}/webgl?t={current_time}" title="Player"></iframe>'
        return ajax_response

    return "Unknown content type.", 400


@app.route("/project/<project_id_string>/upload/download", methods=["POST"])
@login_required
def upload_download(project_id_string):
    """
    Route for uploading downloadable files.
    Restrictions: Authenticated, CAN_EDIT
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_EDIT)
    if project is None:
        abort(404)

    route = f"/project/{project.project_id}"
    project_folder = project.folder()
    file = request.files.get("file",None)
    if file is None:
        return "Invalid input.", 400


    #Ensure downloads folder exists
    download_folder = os.path.join(project_folder, "downloads")
    if not os.path.exists(download_folder):
        os.mkdir(download_folder)

    filename = request.form.get("filename", None)
    filename = secure_filename(filename or file.filename)
    filename = project.unique_download_filename(filename)

    file_path = os.path.join(download_folder, filename)
    file.save(file_path)
    download_data = (filename, current_user.name, datetime.now(timezone.utc))
    project.add_download_info(download_data)

    return render_template( "ajax_responses/download.html",
                            filename=filename,
                            username=current_user.name,
                            time="Less than a minute ago",
                            access_level=access_level,
                            access_from_string=access_from_string,
                            project=project,
                            route=route
    )


@app.route("/project/<project_id_string>/webgl",methods=["GET"])
def webGL(project_id_string):
    """
    Returns a send_from_directory of the webgl content ('index.html' file).
    Restrictions: CAN_VIEW
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, CAN_VIEW)
    if project is None:
        abort(404)

    if not os.path.exists(f"{PROJECTS_FOLDER}/{project.project_id}/webgl/index.html"):
        #The game files are missing.
        return "<i>Sorry, there is nothing to display.</i>"
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
    project_dir = project.folder()
    content_dir = os.path.join(project_dir,"webgl")
    #Only the folders provided by the game build may be accessed.
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
    project_dir = project.folder()
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
    return project.delete_download(request.form.get("filename",""))



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
        added_email = request.form.get("email", None)
        if added_email is None:
            return "Email input error.", 400
        if added_email == "":
            return "Email may not be blank.", 400
        added_user = Users.query.filter_by(email=added_email).first()
        if added_user is None:
            return "User has not registered with that email.", 404

        existing_access = project.access_level(added_user)
        if existing_access >= access_level:
            return VIOLATION_ERROR
        new_access = access_from_string.get(request.form.get("access_level", None),None)
        if new_access is None:
            return "Invalid access level.", 400
        if new_access < NO_ACCESS or new_access > SUB_OWNER:
            return "Invalid access level.", 400
        user_access = project.assign_project_access(added_user.user_id, new_access)
        return str(user_access.access_id) + render_template( "ajax_responses/access_row.html",
            route=route,
            access_level=access_level,
            user_access=user_access,
            access_descriptions=access_descriptions,
            access_from_string=access_from_string)

    else:
        return "Form not recieved, please reload."



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
        access_id = request.form.get("access_id", None)
        if access_id is not None:
            existing_access = ProjectPermissions.query.filter_by(access_id=access_id).first()
            if existing_access is None:
                return "Permission not found.", 404
            if existing_access.access_level >= access_level:
                return "You do not have permission to delete this access.", 403
            else:
                db.session.delete(existing_access)
                db.session.commit()
                return "OK"

    return "User not found.", 404



@app.route("/project/<project_id_string>/createShareLink", methods=["POST"])
@login_required
def create_share_link(project_id_string):
    """
    Form submission creates a sharable link.
    Restrictions: Authenticated, SUB_OWNER.
    Possibly to be deprecated.
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
    if project is None:
        abort(404)
    route = project.route()

    form = request.form
    access_string = form.get("access", None)
    access_level_granted = access_from_string.get(access_string, None)
    if access_level_granted is None:
        return "Input Error", 400
    do_limit = form.get("do_limit", None) == "do_limit"
    if do_limit:
        try:
            user_limit = int(form.get("user_limit", 20))
        except ValueError:
            user_limit = 20
    else:
        user_limit = -1
    current_time = get_current_time()
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

    return share_link.url_string + render_template("ajax_responses/share_link.html",
        project=project,
        share_link=share_link,
        route=route,
        access_descriptions=access_descriptions)

@app.route("/project/<project_id_string>/deleteShareLink", methods=["POST"])
@login_required
def delete_share_link(project_id_string):
    """
    Form submission deletes shareable link.
    Restrictions: Authenticated, SUB_OWNER.
    Possibly to be deprecated.
    """
    project, access_level, is_logged_in=handle_project_id_string(project_id_string, SUB_OWNER)
    if project is None:
        abort(404)
    route = project.route()

    form = request.form
    share_link_url = form.get("share_link_url", None)
    if share_link_url is None:
        return "Input Error", 400
    share_link = ShareLinks.query.filter_by(url_string=share_link_url).first()
    if share_link is None:
        return "Link not found", 404
    if share_link.project_id != project.project_id:
        return "Link not found", 404

    db.session.delete(share_link)
    db.session.commit()
    return "OK"




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
    if share_link.project_id != project.project_id:
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
    if setting in ["private","school","public"]:
        if setting == "private":
            project.default_access=NO_ACCESS
            project.student_access=NO_ACCESS
        elif setting == "school":
            project.default_access=NO_ACCESS
            project.student_access=CAN_COMMENT
        else:
            project.default_access = CAN_VIEW
            project.student_access = CAN_COMMENT
        db.session.commit()
        return render_template('ajax_responses/share_info.html', project=project, access_descriptions=access_descriptions)
    else:
        return "Invalid share setting.", 400



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
            project.update_time()
            db.session.commit()
            return "OK"

        authors = form.get("authors", "")
        if authors != "":
            project.set_authors(authors)
            return ", ".join(project.authors.split(","))

        description = form.get("description", "")
        if description != "":
            project.set_description(description)
            return "OK"

        tags = form.get("tags", "")
        if tags != "":
            project.set_tags(tags)
            return render_template("ajax_responses/paragraph_list.html", items=project.tags.split(","))

        thumbnail_file = request.files.get("thumbnail")

        new_thumbnail_path = os.path.join(project.folder(), "new_thumbnail")
        thumbnail_path = os.path.join(project.folder(), "thumbnail")
        if thumbnail_file is not None:
            if thumbnail_file.mimetype.split("/")[1] in THUMBNAIL_EXTENSIONS:
                thumbnail_file.save(new_thumbnail_path)
                #Check size:
                thumbnail_size = os.stat(new_thumbnail_path).st_size
                if thumbnail_size > 1000 * 1000 * MAX_THUMBNAIL_SIZE_MB:
                    #Size too large: delete thumbnail file.
                    os.remove(new_thumbnail_path)
                    return f"File too large (Max {MAX_THUMBNAIL_SIZE_MB}MB)", 413
                else:
                    #Commit file to thumbnail
                    os.rename(new_thumbnail_path, thumbnail_path)
                    project.update_time()
                    return "OK"
            else:
                #Thumbnail not saved.
                return "Invalid file type.", 400


    return "Request not understood. Try reloading.", 400


#Setup and read neccessary files

if not os.path.exists(file_location(SECRET_KEY_FILENAME)):
    #Create session secret key
    generate_key(SECRET_KEY_FILENAME, 24)
app.secret_key = get_key(SECRET_KEY_FILENAME)

if not os.path.exists(file_location(database_file)):
    db.create_all()


if __name__ == "__main__":
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        if not os.path.exists(file_location("google_client_details.txt")):
            exit("Google client details missing from environment and file.")

        try:
            google_client_details_file = open("google_client_details.txt","r")
            GOOGLE_CLIENT_ID = google_client_details_file.readline().strip().rstrip()
            GOOGLE_CLIENT_SECRET = google_client_details_file.readline().strip().rstrip()
        except:
            exit("Error reading google client details file.")

        if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
            exit("Invalid google client details.")

    #print(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,flush=True)

    app.run(ssl_context='adhoc', debug=True)
    #app.run(host="192.168.1.8", ssl_context='adhoc', debug=False)