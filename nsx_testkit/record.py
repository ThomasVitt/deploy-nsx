import json
import os

from .normalize import normalize


def save(calls, path, ordered=False):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(normalize(calls, ordered=ordered), f, indent=2, sort_keys=True)
        f.write("\n")
