"""
Web app to provide feedback from and to students and teachers.
Author: Joseph Grace
Contains helper functions.
"""

import os

from secrets import choice
from datetime import datetime, timezone, timedelta

import requests

#Own imports:
from access_names import *
from constants import *
    


def get_current_time():
    """Returns the current time as an offset-aware datetime object in UTC"""
    return datetime.now(TIMEZONE)



def time_to_string(datetime_object):
    """Returns the datetime object formatted to TIME_FORMAT in timezone TIMEZONE"""
    datetime_utc = datetime_object.astimezone(TIMEZONE)
    return datetime_utc.strftime(TIME_FORMAT)



def string_to_time(datetime_string):
    """
    Returns offset-aware datetime object (timezone TIMEZONE) from string.
    Warning: timezone of string will be ignored, and will be assumed to be TIMEZONE
    """
    time = datetime.strptime(datetime_string, TIME_FORMAT)
    time = time.replace(tzinfo=TIMEZONE)
    return time



def format_time_delta(time_delta):
    """
    Returns a string representing the given time_delta.
    String is formatted as '{x} {unit}('s) ago' or 'Less than a minute ago'.
    """
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
        return f"{hours} hour{'s' if hours!=1 else ''} ago"
    elif time_delta.seconds>=60:
        minutes = time_delta.seconds//60
        return f"{minutes} minute{'s' if minutes!=1 else ''} ago"
    else:
        return "Less than a minute ago"



def file_location(path):
    """Takes path from app directory and returns absolute path."""
    return os.path.join(APP_DIR, path)



def generate_key(filename, size):
    """
    Generates a random key consisting of 'size' random bytes,
    and writes to the file.
    """
    file = open(filename,"wb")
    print(os.urandom(size))
    file.write(os.urandom(size))
    file.close()



def get_key(filename):
    """
    Reads and returns a key from a file as binary data.
    """
    file = open(filename,"rb")
    key = file.read()
    file.close()
    return key



def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()