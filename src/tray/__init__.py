import argparse
from .. import NAME
from .setup import Setup


def main():
    parser = argparse.ArgumentParser(description='%s tray icon'%NAME)
    parser.add_argument('--setup', default=False, action="store_true", help='Run initial setup')
    parser.add_argument('-t', '--target', metavar="URI", type=str, default=None, help='Target URI')
    parser.add_argument('--verbose', '-v', action='count', default=0, help='Verbose mode')
    args = parser.parse_args()
    
    if not Setup.configured() or args.setup: Setup.setup()
    from .tray import main
    main(args)


if __name__ == "__main__": main()

