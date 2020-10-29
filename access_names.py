"""
Web app to provide feedback from and to students and teachers.
Author: Joseph Grace
Access level constants to be used in access level columns of database.
"""

BANNED = -1 #Has been manually banned
NO_ACCESS = 0 #Invisible
CAN_VIEW = 2
CAN_COMMENT = 3
CAN_EDIT = 5
SUB_OWNER = 6 #Meta-editing priveleges eg. Renaming, deleting
OWNER = 7 #Original creator of object

access_from_string={
    "BANNED": BANNED,
    "NO_ACCESS": NO_ACCESS,
    "CAN_VIEW": CAN_VIEW,
    "CAN_COMMENT": CAN_COMMENT,
    "CAN_EDIT": CAN_EDIT,
    "SUB_OWNER": SUB_OWNER,
    "OWNER": OWNER
}

access_messages = {
    BANNED: "You have been banned from viewing this project.",
    NO_ACCESS: "Cease and desist.",
    CAN_VIEW: "View only.",
    CAN_COMMENT: "Commenting enabled.",
    CAN_EDIT: "You may edit this content.",
    SUB_OWNER: "You are an owner.",
    OWNER: "You are the primary owner."
}

access_descriptions = {
    BANNED: "Totaly Banned",
    NO_ACCESS: "No Access",
    CAN_VIEW: "View Only",
    CAN_COMMENT: "View and Comment",
    CAN_EDIT: "Collaborator",
    SUB_OWNER: "Owner",
    OWNER: "Primary Owner"
}

#Project access levels
PROJECT_DEFAULT_ACCESS = NO_ACCESS
PROJECT_STUDENT_ACCESS = NO_ACCESS
PROJECT_CLASS_ACCESS   = CAN_COMMENT
PROJECT_TEACHER_ACCESS = SUB_OWNER


#User heirachy
NORMAL=0
MOD=1
ADMIN=2