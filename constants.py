import os
from datetime import timezone

SECRET_KEY_FILENAME = "secretkey.dat"
BCRYPT_ROUNDS = 14

APP_DIR = os.path.dirname(os.path.abspath(__file__) ) #This is the directory of the project
PROJECTS_FOLDER = os.path.join(APP_DIR,"projects")

SHARE_URL_SIZE = 12

TIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f %Z"
TIMEZONE = timezone.utc

THUMBNAIL_EXTENSIONS = ["png","jpeg","jpg","gif"]