import argparse, time, sys, os
from .core.transmission.shared_vars import NumericVar
from . import Target, hifish


class Main:
    
    def __init__(self):
        script = os.path.basename(__file__)
        parser = argparse.ArgumentParser(description=f'Tool for creating a HiFi script for HiFiSh. It can record target changes to repeat the actions later by calling the HiFi script. Writes to stdout. Example: {script} > batch.hifi && hifish batch.hifi')
        subparsers = parser.add_subparsers(help='sub-command help', dest="command", required=True)
        parser_full = subparsers.add_parser('full', help='Include all supported shared variables')
        parser_record = subparsers.add_parser('record', help='Record changes in shared variables')
        group = parser_record.add_mutually_exclusive_group(required=False)
        group.add_argument("--relative", action="store_true", help="For numeric values, denote only the difference instead of absolute value")
        group.add_argument("-r", "--raw", action="store_true", help="Use low level commands")
        parser_full.add_argument("-r", "--raw", action="store_true", help="Use low level commands")

        parser.add_argument('-t', '--target', metavar="URI", type=str, default=None, help='Target URI')
        parser.add_argument('--verbose', '-v', action='count', default=0, help='Verbose mode')
        args = parser.parse_args()
        self.raw = args.raw
        self.relative = getattr(args, "relative", False)
        with Target(args.target, verbose=args.verbose) as self.t:
            self.append(f"#!/usr/bin/env -S python3 -m {hifish.__name__}")
            self.append("#")
            self.append(f"# CREATED WITH {script}")
            self.append("#")
            self.append()
            if args.command == "full":
                self.start_recording()
                for call in set([var.call for var in self.t.shared_vars.values() if var.call]):
                    self.append(f"\n# sent ${repr(call)}")
                    self.t.send(call)
                    time.sleep(.2)
                time.sleep(3)
            else:
                if self.relative:
                    [var.async_poll() for var in self.t.shared_vars.values() if isinstance(var, NumericVar)]
                    time.sleep(2)
                self.start_recording()
                print("Recording... Press ENTER to stop", file=sys.stderr)
                print(file=sys.stderr)
                try: input()
                except KeyboardInterrupt: pass

    def append(self, s=""):
        print(s)
        sys.stdout.flush()

    def start_recording(self):
        if self.raw: self.t.bind(on_receive_raw_data=lambda data: self.append(f"${repr(data)}"))
        else: self.t.bind(on_shared_var_change = self.record_parsed)

    def record_parsed(self, var_id, value):
        prev = self.t.shared_vars[var_id]._prev_val
        if self.relative and prev and isinstance(self.t.shared_vars[var_id], NumericVar):
            self.append(f"${var_id} += {repr(value-prev)}")
        else: self.append(f"${var_id} = {repr(value)}")


if __name__ == '__main__': Main()

