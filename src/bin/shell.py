import argparse, os, sys
from threading import Thread
from .. import Amp, VERSION


class CLI(object):
    
    def __init__(self):
        parser = argparse.ArgumentParser(description='Controller for Network Amp - CLI')
        parser.add_argument("command", nargs="*", type=str, help='CLI command')
        parser.add_argument('--host', type=str, default=None, help='Amp IP or hostname')
        parser.add_argument('--protocol', type=str, default=None, help='Amp protocol')
        group = parser.add_mutually_exclusive_group(required=False)
        group.add_argument('--return', dest="ret", type=str, metavar="CMD", default=None, help='Return line that starts with CMD')
        group.add_argument('-f','--follow', default=False, action="store_true", help='Monitor amp messages')
        parser.add_argument('--verbose', '-v', action='count', default=0, help='Verbose mode')
        self.args = parser.parse_args()
        
    def __call__(self):
        amp = Amp(self.args.host, protocol=self.args.protocol, verbose=self.args.verbose)
        with amp: self.start(amp)

    def start(self, amp):
        if self.args.follow or len(self.args.command) == 0:
            print("$_ HIFI SHELL %s (%s)\n"%(VERSION, amp.prompt))
            amp.bind(on_disconnected=self.on_disconnected)
            amp.bind(on_receive_raw_data=self.receive)
            for cmd in self.args.command:
                print(cmd)
                amp.send(cmd)
            while True:
                try: cmd = input().strip()
                except (KeyboardInterrupt, EOFError): break
                cmd = amp.send(cmd)
            return
        for cmd in self.args.command:
            matches = (lambda cmd:cmd.startswith(self.args.ret)) if self.args.ret else None
            r = amp(cmd,matches=matches)
            if r: print(r)
        
    def receive(self, data): print(data)
    
    def on_disconnected(self):
        print("\nConnection closed", file=sys.stderr)
        exit()
        

main = lambda:CLI()()
if __name__ == "__main__":
    main()

