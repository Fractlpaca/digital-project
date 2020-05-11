"""
Access level constants to be used in access level columns of database.
Author: Joseph Grace
Last Edited 11/05/2020
Note only projects are being implemented currently.
"""

NO_ACCESS = 0 #Invisible
CAN_SEE = 1 #Contents not viewable
CAN_VIEW = 2
CAN_COMMENT = 3
CAN_SUBMIT = 4 #Only relevant to assignments
CAN_EDIT = 5
SUB_OWNER = 6 #Meta-editing priveleges eg. Renaming, deleting
OWNER = 7 #Original creator of object

#Project access levels
PROJECT_DEFAULT_ACCESS = CAN_SEE
PROJECT_STUDENT_ACCESS = CAN_SEE
PROJECT_CLASS_ACCESS   = CAN_COMMENT
PROJECT_TEACHER_ACCESS = SUB_OWNER

#Discussion access levels
DISCUSSION_DEFAULT_ACCESS = NO_ACCESS
DISCUSSION_STUDENT_ACCESS = CAN_SEE
DISCUSSION_CLASS_ACCESS   = CAN_COMMENT
DISCUSSION_TEACHER_ACCESS = SUB_OWNER

#Assignment acces levels
ASSIGNMENT_DEFAULT_ACCESS = NO_ACCESS
ASSIGNMENT_STUDENT_ACCESS = NO_ACCESS
ASSIGNMENT_CLASS_ACCESS   = CAN_SUBMIT
ASSIGNMENT_TEACHER_ACCESS = SUB_OWNER

#Class access levels
CLASS_DEFAULT_ACCESS = CAN_SEE
CLASS_STUDENT_ACCESS = CAN_SEE
CLASS_CLASS_ACCESS   = CAN_VIEW #No comments on classes
CLASS_TEACHER_ACCESS = SUB_OWNER

#It is possible teacher access will be implicit