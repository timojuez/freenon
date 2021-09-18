import sys, os, argparse, pkgutil, re
from contextlib import suppress
from ..core.config import config, FILE
from ..schemes.auto import discover_target, check_target
from .. import NAME, PKG_NAME, Target


def autostart():
    if input("Add %s to autostart for current user? [Y/n] "%NAME) == "n": return
    return autostart_win() if sys.platform.startswith("win") else autostart_gnu()


def autostart_win():
    import getpass
    bat_path = r'C:\Users\%s\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup'%getpass.getuser()
    with open("%s\\%s.bat"%(bat_path, PKG_NAME), "w") as fp:
        fp.write(r'start "" %s' % os.path.realpath(__file__)) # TODO: file path


def autostart_gnu():
    desktop = pkgutil.get_data(__name__,"../share/hificon_tray.desktop").decode()
    with open(os.path.expanduser("~/.config/autostart/%s_tray.desktop"%PKG_NAME), "w") as fp:
        fp.write(desktop)


def source_setup():
    target = Target()
    if config.source not in target.features: return
    if input("On your amp, select the input source that this device is connected to and press "
        "ENTER. This setting is used by the auto power function. [s]kip? ") == "s": return
    with target: source = target.features[config.source].get()
    print("Registered input source `%s`."%source)
    config.setlist("Amp", "source", [source])


def zone_setup():
    target = Target()
    comp = re.compile("^zone(\d*)_volume$")
    zones = [match.groups()[0] for key in target.features.keys()
        for match in [comp.match(key)] if match]
    if not zones: return
    while True:
        ans = input("Which amp zone do you want to control with the %s icon? [M]ain/%s "
            %(NAME, "/".join(map(lambda e:"[%s]"%e, zones))))
        if ans in zones or ans in ("","M","m"):
            for f_id in ("power","source","volume","muted"):
                config["Amp"]["%s_feature_id"%f_id] = "zone%s_%s"%(ans,f_id) if ans in zones else f_id
            break


def discover_target_prompt():
    def set_target(uri): config["Target"]["uri"] = uri
    try: uri = discover_target()
    except Exception as e:
        print("%s: %s"%(type(e).__name__, e))
        while True:
            host = input("Enter target IP: ")
            if uri := check_target(host): return set_target(uri)
            else: print("Cannot connect to host.")
    else: set_target(uri)


class Main(object):

    def __init__(self):
        self.parser = argparse.ArgumentParser(description='%s Setup Tool'%NAME)
        for args in Setup.getTasks(): self.add_bool_arg(*args)
        self.parser.add_argument("-v",'--verbose', default=False, action='store_true', help='Verbose mode')
        self.args = self.parser.parse_args()
        
    def add_bool_arg(self, arg, func, help, default=True):
        group = self.parser.add_mutually_exclusive_group()
        group.add_argument("--%s"%arg, default=default, action="store_true",
            help = "%s (default)"%help if default else help)
        group.add_argument("--no-%s"%arg, dest=arg, action="store_false",
            help="" if default else "(default)")
    
    def __call__(self):
        Setup.setup([a for a in Setup.getTasks() if getattr(self.args, a[0])])


class BasicSetup:
    add_tasks = [
        # arg,      func,           help,               default
        ("discover", discover_target_prompt, "Discover amp automatically", True),
    ]
    

class TraySetup(BasicSetup):
    add_tasks = [
        ("autostart", autostart, "Add tray icon to autostart", True),
        ("zone-setup", zone_setup, "Specify a zone to be controlled by this app", True),
        ("source-setup", source_setup, "Connect an input source to the computer", True),
    ]


class Setup(TraySetup, BasicSetup):

    @classmethod
    def configured(self): return os.path.exists(FILE)
    
    @classmethod
    def getTasks(self): return [task 
        for C in filter(lambda C:"add_tasks" in C.__dict__, reversed(self.__mro__)) for task in C.add_tasks]

    @classmethod
    def setup(self, tasks=None):
        """ tasks is in the form of @all_tasks """
        tasks = tasks or self.getTasks()
        if os.path.exists(FILE) and input("This will modify `%s`. Proceed with setup? [y/N] "%FILE) != "y":
            return
        for arg, func, help, default in tasks:
            try: func()
            except Exception as e:
                print("Exception in %s: %s"%(arg,repr(e)))
            print()
        print("done. The service needs to be (re)started.")


def main(): Main()()
if __name__ == "__main__":
    main()

