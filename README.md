# HiFiCon Network Amp Controlling Software
### Free High Freedelity for Your Computer

## Features
- Denon De Luxe: Control your Denon amp's power and master volume with your laptop
- Hificon icon: Volume control tray icon
- Mouse and keyboard volume key support
- Amplifier notifications screen overlay
- Automatic amplifier discovery
- Automatic power control
	- Switching the amplifier on when sound starts playing
	- Switching the amplifier off when sound stops or computer shuts down/suspends
- Hifi shell: Send custom commands to the amp and program your own hifi script
- Compatibility: Needs only the amp's telnet interface
- Platform independent
- Easily control your AVR – even far away from remote control distance


## Requirements
- Denon/Marantz AVR compatible, connected via LAN/Wifi (tested with Denon X1400H)
- Python 3 and Pip

Optional:

**For automatic amplifier discovery:**
- Private nameserver on LAN
- nmap and net-tools

**For automatic power control:**
- SystemD
- Pulseaudio

**For mouse and keyboard volume key support**
- Any platform


## Install

### Ubuntu and other GNU OS
Install the requirements:

`sudo apt-get install python3-dev python3-pip nmap net-tools python3-gi`

Cloning this repository in the current directory and installing via pip:

`$ git clone https://github.com/timojuez/hificon.git hificon && pip3 install --user wheel && pip3 install --user ./hificon/[autosetup,gnu_desktop] && rm -R ./hificon && hificon_setup --keys`

### Proprietary OS
On Mac/Windows, download and install Python3 with Pip.
Then execute:

`$ git clone https://github.com/timojuez/hificon.git hificon && pip3 install --user wheel && pip3 install --user ./hificon/[autosetup,nongnu_desktop] && rm -R ./hificon && hificon_setup`

To connect the extra mouse buttons, start `hificon_mouse_binding`. You may want to add the command to autostart.

### Uninstall
To uninstall: `pip3 uninstall hificon`

Ggf remove the lines after ## HIFICON in ~/.xbindkeysrc and restart xbindkeys.


### Configuration
See configuration options in ~/.hificon.cfg and src/share/hificon.cfg.default.


## Usage

Note that this program is still in development and therefore try it first with all sound output stopped.

### Graphical Main Application
Start the main application:
`hificon`

You may want to add the command to autostart.


### Hifi Shell
Plain commands can be sent to the amp

`hifi_sh -c [command]`

Hifi scripts can be executed:

`hifi_sh FILE.hifi`

See the ./examples/.


## Development

### Support for other AVR brands
It is possible to implement the support for other AVR brands like Yamaha, Pioneer, Onkyo. This software can connect your computer to any network amp that communicates via telnet. See src/protocol/* as an example. See also "protocol" parameter in config and in hifi_sh.

### Custom amp control software
It is possible to create a customised controller that keeps your own program synchronised with the amp.
See ./examples/custom_app.py

If your development only relies on sending commands to the amp, your requirement is purely the hificon package and optionally hificon[autosetup].

### Test own software on Denon AVRs
For testing purposes, there is a Denon AVR software dummy that acts like the amp's Telnet protocol. Try it with `hifi_shell --protocol .dummy`.


## Limitations
- Currently only Denon protocol devices are being supported.
- If you do not have a nameserver in your LAN or hificon_setup cannot find your Denon device, add the amp's IP address as "Host = [IP]" under [Amp] to .hificon.cfg in your user directory.
- This program is currently only controlling the sound channels alltogether. Controlling e.g. left and right channel separately is to be implemented.
- If you are on a GNU OS and the key binding does not work, you can try the setup for proprietary OS.

