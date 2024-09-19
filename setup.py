#!/usr/bin/env python3

import os
from distutils.core import setup


script_dir = os.path.dirname(os.path.realpath(__file__))
with open(f"{script_dir}/src/info.py") as fp: exec(fp.read())

setup(name=PKG_NAME,
      version=VERSION,
      description='Network Amp Controlling Software',
      author=AUTHOR,
      author_email='timo.juez@gmail.com',
      url=URL,
      license='GNU General Public License v3 or later (GPLv3+)',
      packages=[PKG_NAME],
      package_dir={PKG_NAME: "src"},
      install_requires=["argparse", "pyyaml"],
      extras_require={
        "tray": [
            "PyGObject",
            "pycairo",
            "pynput",
            "python-xlib; sys_platform=='linux'",
            "pulsectl; sys_platform=='linux'",
        ],
        "menu": [
            "kivy"
        ],
      },
      include_package_data=True,
      entry_points={'console_scripts': [
        'hifish = %(name)s.hifish:main'%dict(name=PKG_NAME),
        "%(name)s_server = %(name)s.server:main"%dict(name=PKG_NAME),
        "%(name)s_menu_control = %(name)s.menu:main"%dict(name=PKG_NAME),
        '%(name)s_tray_control = %(name)s.tray:main'%dict(name=PKG_NAME),
        '%(name)s_setup = %(name)s.tray.setup:main'%dict(name=PKG_NAME),
      ]},
)

