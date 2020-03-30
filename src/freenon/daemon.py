#!/usr/bin/env python3
import argparse, pulsectl
from .libdaemon import PluginInterface, EventHandler


class AbstractPulse(object):
    def __init__(self): self.pulse = pulsectl.Pulse("Freenon")
    
    
class PulsePlugin(AbstractPulse,PluginInterface):
    sink = 0

    def __init__(self, maxvol):
        super(PulsePlugin,self).__init__()
        self.maxvol = maxvol
    
    def getVolume(self):
        """ Set AVR volume and mute according to Pulse """
        sink = self.pulse.sink_list()[self.sink]
        volume = sink.volume.value_flat*self.maxvol
        return volume
        
    def getMuted(self):
        sink = self.pulse.sink_list()[self.sink]
        return bool(sink.mute)
        
    def update_volume(self, volume):
        volume = volume/self.maxvol
        self.pulse.volume_set_all_chans(
            self.pulse.sink_list()[self.sink], volume)
        print("[Pulse] setting volume to %0.2f"%volume)
    
    def update_muted(self, muted):
        self.pulse.mute(self.pulse.sink_list()[self.sink],muted)


class PulseListener(AbstractPulse):
    """ Listen for pulseaudio change events """

    def __call__(self, el):
        #self.pulse.event_mask_set('all')
        self.pulse.event_mask_set(pulsectl.PulseEventMaskEnum.sink)
        self.pulse.event_callback_set(self.callback)
        while True:
            try: self.pulse.event_listen()
            except KeyboardInterrupt: return
            el.on_plugin_change()

    def callback(self, ev):
        if not (ev.facility == pulsectl.PulseEventFacilityEnum.sink
            and ev.t == pulsectl.PulseEventTypeEnum.change): return
        #print('Pulse event:', ev)
        raise pulsectl.PulseLoopStop
    
    
class Main(object):
    
    def __init__(self):
        parser = argparse.ArgumentParser(description='Sync pulseaudio to Denon AVR')
        parser.add_argument('--maxvol', type=int, metavar="0..98", required=True, help='Equals 100%% volume in pulse')
        parser.add_argument("-v",'--verbose', default=False, action='store_true', help='Verbose mode')
        self.args = parser.parse_args()
        
    def __call__(self):
        el = EventHandler(PulsePlugin(self.args.maxvol), verbose=self.args.verbose)
        PulseListener()(el)


main = lambda:Main()()    
if __name__ == "__main__":
    main()

