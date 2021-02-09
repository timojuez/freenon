from pynput.mouse import Listener, Button, Controller
from ..tray.key_binding import send
from ..core.config import config


VOLUP = getattr(Button,config["MouseBinding"]["vol_up"])
VOLDOWN = getattr(Button,config["MouseBinding"]["vol_down"])


class Main(object):

    def on_click(self, x, y, button, pressed):
        if button not in (VOLUP, VOLDOWN):
            return
        button = button == VOLUP # to bool
        func = {True:"on_key_press",False:"on_key_release"}[pressed]
        send(dict(kwargs=dict(button=button), func=func))
            
    def __call__(self):
        print("WARNING: Mouse events that control the target are not being suppressed to other programs.")
        with Listener(on_click=self.on_click, suppress=False) as listener: #bug: suppress=True kills X
            listener.join()


def main():
    Main()()
    
if __name__ == "__main__":
    main()

