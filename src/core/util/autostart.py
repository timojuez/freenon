""" Provides a platform independent Autostart class that sets and unsets
a Python module to autostart """

import os, sys

__all__ = ["Autostart"]


class _Autostart:
    path = None

    def __init__(self, name, module=__package__, terminal=False):
        self.name = name
        self.module = module
        self.terminal = terminal

    def get_active(self): return os.path.exists(self.path)

    def set_active(self, value): self.activate() if value else self.deactivate()

    def activate(self): raise NotImplementedError()

    def deactivate(self):
        try: os.remove(self.path)
        except FileNotFoundError: pass


class AutostartWin(_Autostart):

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        import getpass
        user = getpass.getuser()
        self.path = (f"C:\\Users\\{user}\\AppData\\Roaming\\Microsoft\\Windows"
            f"\\Start Menu\\Programs\\Startup\\{self.name}.bat")

    def activate(self):
        cmd = "python.exe -m {self.module}" if self.terminal \
            else "pythonw.exe -m {self.module} 1>NUL 2>&1"
        with open(self.path, "w") as fp:
            fp.write(f'start "" "{cmd}"')


class AutostartGnu(_Autostart):

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.path = os.path.expanduser(f"~/.config/autostart/{self.name}.desktop")

    def activate(self):
        content = "\n".join([
            "[Desktop Entry]",
            "Encoding=UTF-8",
            "Type=Application",
            f"Name={self.name}",
            f"Exec=/usr/bin/env -S python3 -m {self.module}",
            "StartupNotify=false",
            f"Terminal={str(self.terminal).lower()}",
            "Hidden=false",
            "X-GNOME-Autostart-enabled=true",
        ])
        with open(self.path, "w") as fp:
            fp.write(content)


Autostart = AutostartWin if sys.platform.startswith("win") else AutostartGnu

