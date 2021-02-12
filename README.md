# HiFiCon Network Amplifier Server and Client Software
### This software provides high level Python variable bindings for an underlying asynchronous data transportation. It comes with three different client programs.


## Features
- HiFiCon Tray Control*
    - Control attributes via tray icon
    - Mouse and keyboard volume key support
    - Notifications OSD
    - Automatic amp power control
	    - Switching the amplifier on when sound starts playing**
	    - Switching the amplifier off when sound stops or computer shuts down/suspends
- HiFiCon Control Menu*
    - Control attributes in a standalone app
- HiFiSh HiFi Shell: Send custom commands and run your own hifi script
- Automatic amplifier discovery*
- Platform independent
- Easily control your AVR – even far away from remote control distance
- Amp server software

*Requires an implemented protocol

**Requires pulseaudio


## Preliminaries

**A target** is an entity associated to a protocol. Amplifiers will be called target in this document.
**Attributes** are variables that a target's protocol provides. It can be volume, power, etc.


### Supported Protocols
- Denon; Denon/Marantz AVR compatible (tested with Denon X1400H); scheme: `denon://IP:PORT`
- Raw Telnet; Reads telnet data without further interpretation; scheme: `raw_telnet://IP:PORT`
- Emulator; Emulates any other protocol; scheme: `emulator:PROTOCOL`
- Plain Emulator; Emulator that skips network; scheme: `plain_emulator:PROTOCOL`


### Requirements on the Client
- Python 3 and Pip

**Amplifiers**
- The amplifier needs to be connected via LAN/Wifi

**For automatic power control:**
- SystemD
- Pulseaudio


### Requirements on Server
- Python 3 and Pip


## Install

### Ubuntu and other GNU OS
Install the requirements:

`sudo apt-get install python3-dev python3-pip python3-gi`

Cloning this repository in the current directory and installing via pip:

`$ git clone https://github.com/timojuez/hificon.git hificon && pip3 install --user wheel && pip3 install --user ./hificon/[gnu_desktop] && rm -R ./hificon && python3 -m hificon`

### Proprietary OS
On Mac/Windows, download and install Python3 with Pip.
Then execute:

`$ git clone https://github.com/timojuez/hificon.git hificon && pip3 install --user wheel && pip3 install --user ./hificon/[nongnu_desktop] && rm -R ./hificon && python3 -m hificon`

To connect the extra mouse buttons, start `hificon_mouse_binding`. You may want to add the command to autostart.

### Uninstall
To uninstall: `pip3 uninstall hificon`

Ggf remove the lines after ## HIFICON in ~/.xbindkeysrc and restart xbindkeys.


### Configuration
See configuration options in ~/.hificon/main.cfg and src/share/main.cfg.default.


## Usage

Note that this program is still in development and therefore try it first with all sound output stopped.

### Tray Control
Start the HiFi Icon:
`python3 -m hificon.tray`


### Control Menu

The menu lets you control all available attributes, e.g. sound mode, input, power, Audyssey settings, single speaker volume, etc. (depending on your target).

`python3 -m hificon.menu`



### HiFi Shell
HiFiSh is the HiFi Shell and it offers its own language called PyFiHiFi. PyFiHiFi is a Python dialect that is customised for programming with HiFiCon. It can read and write the attributes or run e.g. remote control actions (depending on the target).

#### Starting the shell
Calling `hifish` without arguments will start the prompt.
To execute a command from bash, call `hifish -c '[command]'`.
Hifi scripts can be executed by `hifish FILE.hifi`

See also `hifish -h` and the ./examples/.

#### High level commands
High level attributes are not protocol (resp. amp manufacturer) specific and start with a `$`. 
Example: `$volume=40`
To see what attributes are being supported, type `help()` or call `hifish --protocol .emulator -c 'help()'`

#### Raw commands
Raw commands can be sent to the target like `MV50` or `PWON`. If your command contains a space or special character (`;`) or if you need it's return value, use the alternative way `$"COMMAND"`. 

#### PyFiHiFi Language
HiFiSh compiles the code into Python as described below. The Python code assumes the following:
```
import time
from hificon import Target
__return__ = None
__wait__ = .1
target = Target()
```

| HiFiSh | Python |
| --- | --- |
| `$"X"` or `$'X'` | `target.query("X", __return__); time.sleep(__wait__)` |
| `$X` | `target.X` |
| `wait(X)` | `time.sleep(X)` |

If `__return__` is a callable, `$""` will return the received line from the target where `__return__(line) == True`.


### Server Software
You can implement an own protocol and start the server by running `python3 -m hificon.telnet_server --listen-host 0.0.0.0 --listen-port 23 --target PROTOCOL_MODULE.CLASS`

If the prefix `emulator:` is being added to `--target`, a dummy server will be run for testing. You can connect to it using the clients mentioned above.


## Development

### Support for other AVR brands
It is possible to implement the support for other AVR brands like Yamaha, Pioneer, Onkyo. It is easy to connect to any network device that communicates via telnet. See src/protocol/* as an example. See also "target" parameter in config and in hifish. Hint: `hifish --target raw_telnet://IP:PORT -f` prints all data received from `IP` via telnet.

### Reverse Engineering a Target
`hifish -f` opens a shell and prints all received data. Meanwhile change settings on the target e.g. with a remote and observe on what it prints. This may help you to program an own protocol.

### Custom Client Software
It is possible to create an own program that controls the target and keeps being synchronised with it.
See ./examples/custom_app.py

Your requirement will be the hificon package.


### AVR Emulator
For testing purposes, there is a server emulator software. The Denon AVR software emulator acts nearly like the amp's Telnet protocol. Try it out: `python3 -m hificon.telnet_server --target emulator:PROTOCOL --listen-port PORT` and connect to it e.g. via HiFiSh: `hifish --target PROTOCOL://127.0.0.1:PORT`.

Example: `python3 -m hificon.telnet_server --target emulator:denon --listen-port 1234`

You can also emulate the HiFi Shell directly: `hifish --target emulator:denon`


## Troubleshoot
- If HiFiCon cannot find your device, add its URI as "uri = PROTOCOL://IP:PORT" under [Target] to ~/.hificon/main.cfg in your user directory.
- If you are on a GNU OS and the key binding does not work, you can try the setup for proprietary OS.
- If your device lets you connect only once but you would like to run several HiFiCon programs at the same time, run `python3 -m hificon.telnet_server -r --target auto --listen-port 1234`. In the programs, set `localhost:1234` as your target.

