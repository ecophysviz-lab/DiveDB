import os
from uuid import uuid4 as uuid


def get_tmpdir(base="/tmp"):
    tmpdir = os.path.join("/tmp", str(uuid()))
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)
    return tmpdir
