import os

from random import randint,seed
from time import time


def get_project_root_path():
    return os.path.dirname(os.path.dirname(__file__))

def get_random_int(start, end):
    seed(time())
    r = randint(start, end)
    return r

def tosca_type_parse(_type):
    tosca_type = _type.split(".", 2)
    if len(tosca_type) == 3:
        tosca_type_iter = iter(tosca_type)
        namespace = next(tosca_type_iter)
        category = next(tosca_type_iter)
        type_name = next(tosca_type_iter)
        return namespace, category, type_name
    return None, None, None
