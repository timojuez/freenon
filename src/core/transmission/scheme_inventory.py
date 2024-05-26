import importlib, sys, traceback
from . import SchemeType

schemes = {
    "denon": ".denon.Denon",
    "emulate": ".emulate.Emulate",
    "dummyemulate": ".emulate.DummyEmulate",
    "telnet": ".telnet.Telnet",
    "auto": ".auto.Auto",
    "repeat": ".repeat.Repeat",
    "yamaha": ".yamaha.Yamaha",
}


def get_schemes():
    for key in schemes.keys():
        try: Scheme = get_scheme(key)
        except: traceback.print_exc()
        else: yield Scheme


def get_scheme(cls_path):
    """ @cls_path str: Key in .schemes.schemes or "module.class" """
    try: cls_or_path_ = schemes[cls_path]
    except KeyError: cls_or_path_ = cls_path
    if isinstance(cls_or_path_, str):
        if "." not in cls_or_path_:
            schemes_str = ", ".join(schemes.keys())
            raise ValueError(f"cls_path must be {schemes_str} or MODULE.CLASS but was '{cls_path}'.")
        module_path, cls = cls_or_path_.rsplit(".", 1)
        root_module = __package__.rsplit(".", 2)[0]
        module = importlib.import_module(module_path, f"{root_module}.schemes")
        Scheme = getattr(module, cls)
    else: Scheme = cls_or_path_
    Scheme.scheme_id = cls_path
    assert(issubclass(Scheme, SchemeType))
    return Scheme


def register_scheme(key, cls_or_path):
    if key in schemes:
        sys.stderr.write(f"WARNING: Overwriting scheme with key = '{key}'\n")
    schemes[key] = cls_or_path

