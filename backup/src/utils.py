import socket
import datetime
import time
from urllib import urlopen


def single_or_none(list):
    if len(list) != 1:
        return None
    volume = list.itervalues().next()
    return volume


def single(list):
    result = single_or_none(list)
    if result is None:
        raise Exception("Only images with exactly one EBS volumes are currently supported")
    return result


def get_my_ip():
    return urlopen('http://whatismyip.com/automation/n09230945.asp').read()


def get_time(dt_str):
    # http://stackoverflow.com/questions/127803/how-to-parse-iso-formatted-date-in-python/127825#127825
    dt, _, us= dt_str.partition(".")
    dt= datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
    us= int(us.rstrip("Z"), 10)
    return dt + datetime.timedelta(microseconds=us)


def get_current_utc_time():
    return datetime.datetime.fromtimestamp(time.mktime(time.gmtime()))


def resolveIp(target):
    ip = repr(socket.gethostbyname_ex(target)[2][0])
    return ip
