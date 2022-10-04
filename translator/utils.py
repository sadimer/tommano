import os
import itertools
from random import randint, seed
from time import time
from itertools import groupby



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


def str_dots_to_dict(str, param):
    arr = str.split('.')[::-1]
    res = {}
    new_res = {}
    if arr[0] != '[0]' and arr[0] != '0' and arr[0] != '[]':
        res[arr[0]] = param
    else:
        res = [param]
    for i in range(1, len(arr)):
        if arr[i] != '[0]' and arr[i] != '0' and arr[i] != '[]':
            new_res[arr[i]] = res
        else:
            new_res = [res]
        res = new_res
        new_res = {}
    return res


def str_dots_to_arr(str):
    return str.split('.')


def deep_update_dict(source, overrides):
    assert isinstance(source, dict)
    assert isinstance(overrides, dict)

    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(source.get(k), dict):
            source[k] = deep_update_dict(source.get(k, {}), v)
        elif isinstance(v, (list, set, tuple)) and isinstance(source.get(k), type(v)):
            type_save = type(v)
            source[k] = type_save(itertools.chain(iter(source[k]), iter(v)))
            if isinstance(source[k], list):
                tmp = []
                [tmp.append(x) for x in source[k] if x not in tmp]
                source[k] = tmp
        else:
            source[k] = v
    return source


def generate_random_subnet():
    addr3 = get_random_int(0, 255)
    variant = get_random_int(0, 3)
    if variant == 0:
        addr2 = 168
        addr1 = 192
    elif variant == 1:
        addr2 = get_random_int(16, 31)
        addr1 = 172
    else:
        addr2 = get_random_int(0, 255)
        addr1 = 10
    return str(addr1) + '.' + str(addr2) + '.' + str(addr3) + '.0/24'


def next_int():
    i = 1
    while True:
        i += 1
        yield i