from fastapi.templating import Jinja2Templates
import os

templates = Jinja2Templates(directory="templates")
_static_cache = {}

def static_version(path):
    if path in _static_cache:
        return _static_cache[path]
    value = os.path.getmtime(path)
    _static_cache[path] = value
    return value

templates.env.globals["static_version"] = static_version