"""
Compatible with Denon Firmware Version 4600-6121-1061-3085
"""

import sys, math
from urllib.parse import urlparse
from threading import Timer
from decimal import Decimal, InvalidOperation
from ..core import features, SocketScheme
from ..core.transmission.types import ClientType, ServerType


ZONES = [2, 3, 4]
QUICK_SELECT_KEYS = [1, 2, 3, 4]

SPEAKERS = [
    ('FL', 'front_left', 'Front Left'),
    ('FR', 'front_right', 'Front Right'),
    ('C', 'center', 'Center'),
    ('SW', 'subwoofer', 'Subwoofer'),
    ('SL', 'surround_left', 'Surround Left'),
    ('SR', 'surround_right', 'Surround Right'),
    ('SBL', 'surround_back_l', 'Surround Back L'),
    ('SBR', 'surround_back_r', 'Surround Back R'),
    ('SB', 'surround_back', 'Surround Back'),
    ('FHL', 'front_height_l', 'Front Height L'),
    ('FHR', 'front_height_r', 'Front Height R'),
    ('FWL', 'front_wide_l', 'Front Wide L'),
    ('FWR', 'front_wide_r', 'Front Wide R'),
    ('TFL', 'top_front_l', 'Top Front L'),
    ('TFR', 'top_front_r', 'Top Front R'),
    ('TML', 'top_middle_l', 'Top Middle L'),
    ('TMR', 'top_middle_r', 'Top Middle R'),
    ('FDL', 'front_atmos_l', 'Front Atmos L'),
    ('FDR', 'front_atmos_r', 'Front Atmos R'),
    ('SDL', 'surround_atmos_l', 'Surround Atmos L'),
    ('SDR', 'surround_atmos_r', 'Surround Atmos R'),
]

SPEAKERS_2 = [
    ('FL', 'front_left', 'Front Left'),
    ('FR', 'front_right', 'Front Right'),
    ('CEN', 'center', 'Center'),
    ('SL', 'surround_left', 'Surround Left'),
    ('SR', 'surround_right', 'Surround Right'),
    ('SBL', 'surround_back_l', 'Surround Back L'),
    ('SBR', 'surround_back_r', 'Surround Back R'),
    ('SB', 'surround_back', 'Surround Back'),
    ('FHL', 'front_height_l', 'Front Height L'),
    ('FHR', 'front_height_r', 'Front Height R'),
    ('FWL', 'front_wide_l', 'Front Wide L'),
    ('FWR', 'front_wide_r', 'Front Wide R'),
    ('TFL', 'top_front_l', 'Top Front L'),
    ('TFR', 'top_front_r', 'Top Front R'),
    ('TML', 'top_middle_l', 'Top Middle L'),
    ('TMR', 'top_middle_r', 'Top Middle R'),
    ('FDL', 'front_atmos_l', 'Front Atmos L'),
    ('FDR', 'front_atmos_r', 'Front Atmos R'),
    ('SDL', 'surround_atmos_l', 'Surround Atmos L'),
    ('SDR', 'surround_atmos_r', 'Surround Atmos R'),
]

SPEAKER_PAIRS = [
    ("FRO", "front", "Front"),
    ("SUA", "surround", "Surround"),
    ("CEN", "center", "Center"),
    ("SBK", "surround_back", "Surround Back"),
    ("FRH", "front_height", "Front Height"),
    ("TFR", "top_front", "Top Front"),
    ("TPM", "top_middle", "Top Middle"),
    ("FRD", "front_atmos", "Front Atmos"),
    ("SUD", "surround_atmos", "Surround Atmos"),
]

SPEAKER_PAIRS_2 = [
    ("FRO", "front", "Front"),
    ("SUR", "surround", "Surround"),
    ("CEN", "center", "Center"),
    ("SBK", "surround_back", "Surround Back"),
    ("FRH", "front_height", "Front Height"),
    ("TFR", "top_front", "Top Front"),
    ("TPM", "top_middle", "Top Middle"),
    ("FRD", "front_atmos", "Front Atmos"),
    ("SUD", "surround_atmos", "Surround Atmos"),
]

EQ_BOUNDS = ["63 Hz", "125 Hz", "250 Hz", "500 Hz", "1 kHz", "2 kHz", "4 kHz", "8 kHz", "16 kHz"]

EQ_OPTIONS = [
    ("ALL", "all", "All Channels", [("ALL", "all", "(all ch.)")]),
    ("LRS", "lr", "Left+Right", SPEAKER_PAIRS_2),
    ("EAC", "channel", "Each Channel", SPEAKERS_2)
]

SOURCES = [
    ('PHONO', 'phono', 'Phono'),
    ('CD', 'cd', 'CD'),
    ('TUNER', 'tuner', 'Tuner'),
    ('DVD', 'dvd', 'DVD'),
    ('BD', 'bluray', 'Blu-ray'),
    ('TV', 'tv', 'TV'),
    ('SAT/CBL', 'cbl', 'CBL/SAT'),
    ('MPLAY', 'mediaplayer', 'Media Player'),
    ('GAME', 'game', 'Game'),
    ('HDRADIO', 'hdradio', 'HD Radio'),
    ('NET', 'heos', 'Heos'),
    ('PANDORA', 'pandora', 'Pandora'),
    ('SIRIUSXM', 'siriusxm', 'Sirius XM'),
    ('SPOTIFY', 'spotify', 'Spotify'),
    ('LASTFM', 'lastfm', 'Last FM'),
    ('FLICKR', 'flickr', 'Flickr'),
    ('IRADIO', 'iradio', 'IRadio'),
    ('SERVER', 'server', 'Server'),
    ('FAVORITES', 'favourites', 'Favourites'),
    ('AUX1', 'aux1', 'AUX 1'),
    ('AUX2', 'aux2', 'AUX 2'),
    ('AUX3', 'aux3', 'AUX 3'),
    ('AUX4', 'aux4', 'AUX 4'),
    ('AUX5', 'aux5', 'AUX 5'),
    ('AUX6', 'aux6', 'AUX 6'),
    ('AUX7', 'aux7', 'AUX 7'),
    ('BT', 'bluetooth', 'Bluetooth'),
    ('USB/IPOD', 'usbipod', 'USB/Ipod'),
    ('USB', 'usb', 'USB'),
    ('IPD', 'ipd', 'IPD'),
    ('IRP', 'irp', 'IRP'),
    ('FVP', 'fvp', 'FVP')
]

INPUTS = {
    ("ANA", "AN", "analog", "Analog"),
    ("DIN", "OP", "digital", "Digital"),
    ("VDO", "VD", "video", "Video"),
    ("HDM", "HD", "hdmi", "HDMI"),
}

Category = type("Category", tuple(), dict(
    GENERAL = "General",
    VOLUME = "Volume",
    INPUT = "Input",
    SPEAKERS = "Speakers",
    AUDIO = "Audio",
    VIDEO = "Video",
    BASS = "Bass",
    EQUALIZER = "Equalizer",
    AUDYSSEY = "Audyssey",
    ECO = "Eco",
    **{f"ZONE_{zone}": f"Zone {zone}" for zone in ZONES}
))

DUMMY_MODEL = "X7800H"


class Denon(SocketScheme):
    description = "Denon/Marantz AVR compatible (tested with Denon X1400H)"
    _pulse = "CV?" # workaround for denon to retrieve CV?

    def __init__(self, *args, **xargs):
        self._power_features = []
        super().__init__(*args, **xargs)

    @classmethod
    def new_client_by_ssdp(cls, response, *args, **xargs):
        if "denon" in response.st.lower() or "marantz" in response.st.lower():
            host = urlparse(response.location).hostname
            port = 23 # TODO
            return cls.new_client(host, port, *args, **xargs)

    def query(self, cmd, matches=None):
        """
        Send command to target
        @cmd str: function[?|param]
        @matches callable: return received line where matches(line) is True
        """
        _function = cmd.upper().replace("?","")
        if "?" not in cmd: return self.send(cmd)
        class _Feature(SelectFeature):
            id=None
            function=_function
            matches = lambda self, data: (matches(data) if matches else super().matches(data))
        _Feature.__name__ = _function
        f = _Feature(self)
        f.wait_poll(force=True)
        return "%s%s"%(_function, f.get())
    
    def send(self, cmd): super().send(cmd.upper() if cmd == cmd.lower() else cmd)


class _DenonFeature:
    """ Handles Denon format "@function@value" """
    
    function = None #str, Denon function command
    call = property(lambda self: "%s?"%self.function)
    
    def serialize(self, value):
        return ["%s%s"%(self.function, self.serialize_val(value))]
    
    def serialize_val(self, value): return value

    def unserialize(self, data):
        assert(len(data) == 1)
        param = data[0][len(self.function):]
        return self.unserialize_val(param)

    def unserialize_val(self, data): return data
        
    def matches(self, cmd):
        return cmd.startswith(self.function) #and " " not in cmd.replace(self.function,"",1)


class DenonFeature(_DenonFeature):
    """ Forbid consume() when power is off """

    def consume(self, data):
        if isinstance(self.target, ClientType): return super().consume(data)
        def func(device_power):
            if device_power.get() == True:
                super(DenonFeature, self).consume(data)
        self.target.schedule(func, requires=(DevicePower.id,))


class _Translation:
    translation = {} #{return_string:value} unserialize return_string to value / serialize vice versa

    options = property(lambda self: list(self.translation.values()))
    
    def unserialize_val(self, val): return self.translation.get(val,val)
        
    def serialize_val(self, val):
        return {val:key for key,val in self.translation.items()}.get(val,val)


class _Bool(_Translation):
    translation = {"ON":True, "OFF":False}


######### Data Types

class SelectFeature(_Translation, DenonFeature, features.SelectFeature): pass

class DynamicSelectFeature(SelectFeature):
    """ SelectFeature that reads its translation property from another feature """
    translation_source = None # Feature Class

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        if getattr(self.translation_source, "type", None) != dict:
            raise TypeError(f"{self.id}.translation_source must be set to a feature of type dict.")
        self.translation = self.translation.copy()
        self.target.features[self.translation_source.id].bind(self.on_translation_change)

    def on_translation_change(self, translation):
        strip = lambda d: {k:v.strip() for k, v in d.items()}
        with self._lock:
            if self.is_set():
                old = self.serialize(self._val)
                self.translation.update(strip(translation))
                self._val = self.unserialize(old)
                self.on_change(self._val) # cause listeners to update from self.translation
            else:
                self.translation.update(strip(translation))

    def consume(self, data):
        self.target.schedule(lambda *_: super(DynamicSelectFeature, self).consume(data),
            requires=(self.translation_source.id,))

    def remote_set(self, *args, **xargs):
        self.target.schedule(lambda *_: super(DynamicSelectFeature, self).remote_set(*args, **xargs),
            requires=(self.translation_source.id,))


class NumericFeature(DenonFeature):
    """ add UP/DOWN value decoding capability """
    step = 1

    def unserialize_val(self, val):
        if val == "UP": return self.get()+self.step
        elif val == "DOWN": return self.get()-self.step
        else: raise ValueError(f"Invalid value `{val}` for feature `{self.id}`")


class DecimalFeature(NumericFeature, features.DecimalFeature):
    step = Decimal('.5')
    min = 0
    max = 98

    def __str__(self): return "%0.1f"%self.get() if self.is_set() else super().__str__()

    @classmethod
    def _roundVolume(self, vol): return self.step*round(vol/self.step)

    def unserialize_val(self, val):
        return Decimal(val.ljust(3,"0"))/10 if val.isnumeric() else super().unserialize_val(val)

    def serialize_val(self, val):
        val = self._roundVolume(val)
        return "%02d"%val if val%1 == 0 else "%03d"%(val*10)


class IntFeature(NumericFeature, features.IntFeature):
    
    def serialize_val(self, val):
        longestValue = max(abs(self.max),abs(self.min))
        digits = math.ceil(math.log(longestValue+1,10))
        return ("%%0%dd"%digits)%val
    
    def unserialize_val(self, val):
        return int(val) if val.isnumeric() else super().unserialize_val(val)

class PowerFeature(_Bool, _DenonFeature, features.BoolFeature): pass

class ZonePowerFeature(PowerFeature):

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.target._power_features.append(self.id)

    def on_change(self, val):
        super().on_change(val)
        if not isinstance(self.target, ServerType): return
        def func(*power_features):
            self.target.features.device_power.set(any([f.get() for f in power_features]))
        self.target.schedule(func, requires=self.target._power_features)


class BoolFeature(_Bool, DenonFeature, features.BoolFeature): pass

class RelativeInt(IntFeature):
    min = -6
    max = 6

    def serialize_val(self, val): return super().serialize_val(val+50)

    def unserialize_val(self, val):
        return super().unserialize_val(val)-50 if val.isnumeric() else super().unserialize_val(val)


class RelativeDecimal(DecimalFeature):
    min = -12
    max = 12

    def serialize_val(self, val): return super().serialize_val(val+50)

    def unserialize_val(self, val):
        return super().unserialize_val(val)-50 if val.isnumeric() else super().unserialize_val(val)


class _LooseNumericFeature:
    """ Value where the target does not always send a numeric """
    
    def matches(self, data):
        try:
            assert(super().matches(data))
            self.unserialize([data])
            return True
        except (TypeError, ValueError, AssertionError, InvalidOperation): return False


class LooseDecimalFeature(_LooseNumericFeature, RelativeDecimal): pass

class LooseIntFeature(_LooseNumericFeature, IntFeature): pass

class LooseBoolFeature(BoolFeature):
    """ Value where the target does not always send a boolean """

    def matches(self,data):
        return super().matches(data) and isinstance(self.unserialize([data]), bool)

    def on_change(self, val):
        super().on_change(val)
        if val == True: self.target.send(self.call) # make target send the nonbool value TODO: only once


class ListFeature(DenonFeature, features.Feature):
    type = list
    TERMINATOR = "END"

    def is_complete(self, buf):
        b = [self.parent.unserialize(buf[-1:])] if self.parent else buf[-1:]
        return super().unserialize(b) == self.TERMINATOR
    def serialize(self, value):
        return [y for x in map(super().serialize, [*value, self.TERMINATOR]) for y in x]
    def unserialize(self, l):
        return [super(ListFeature, self).unserialize([e]) for e in l[:-1]]


class FeatureBlock(features.FeatureBlock, DenonFeature, features.Feature): pass


######### Features implementation (see Denon CLI protocol)

class BlockTerminator(features.PresetValueMixin, DenonFeature, features.Feature):
    function = ""
    value = "END"
    def matches(self, data): super().matches(data) and self.unserialize([data]) == self.value


@Denon.add_feature(overwrite=True)
class Fallback(Denon.features.fallback):
    """ hide known messages from AVR """
    name = Denon.features.fallback.name


@Denon.add_feature
class Volume(DecimalFeature):
    category = Category.VOLUME
    function = "MV"

    def matches(self, data): return data.startswith(self.function) and (
        data[len(self.function):].isnumeric() or data[len(self.function):] in ["UP", "DOWN"])


@Denon.add_feature
class Maxvol(DecimalFeature): #undocumented
    name = "Max. Vol."
    category = Category.VOLUME
    function="MVMAX "
    call="MV?"
    default_value = 98
    def remote_set(self, val, **xargs): raise RuntimeError("Cannot set MVMAX! Set '%s' instead."%VolumeLimit.name)

@Denon.add_feature
class VolumeLimit(SelectFeature): #undocumented
    category = Category.VOLUME
    function="SSVCTZMALIM "
    call = "SSVCTZMA ?"
    translation = {"OFF":"Off", "060":"60", "070":"70", "080":"80"}
    def on_change(self, val):
        super().on_change(val)
        self.target.features.maxvol.async_poll(force=True)

class _SpeakerConfig(SelectFeature):
    category = Category.SPEAKERS
    call = "SSSPC ?"
    translation = {"SMA":"Small","LAR":"Large","NON":"None"}

@Denon.add_feature
class FrontSpeakerConfig(_SpeakerConfig): #undocumented
    function = "SSSPCFRO "
    
@Denon.add_feature
class SurroundSpeakerConfig(_SpeakerConfig): #undocumented
    function = "SSSPCSUA "
    
@Denon.add_feature
class CenterSpeakerConfig(_SpeakerConfig): #undocumented
    function = "SSSPCCEN "
    
@Denon.add_feature
class SurroundBackSpeakerConfig(_SpeakerConfig): #undocumented
    function = "SSSPCSBK "
    
@Denon.add_feature
class FrontHeightSpeakerConfig(_SpeakerConfig): #undocumented
    function = "SSSPCFRH "
    
@Denon.add_feature
class TopFrontSpeakerConfig(_SpeakerConfig): #undocumented
    function = "SSSPCTFR "
    
@Denon.add_feature
class TopMiddleSpeakerConfig(_SpeakerConfig): #undocumented
    function = "SSSPCTPM "
    
@Denon.add_feature
class FrontAtmosSpeakerConfig(_SpeakerConfig): #undocumented
    function = "SSSPCFRD "
    
@Denon.add_feature
class SurroundAtmosSpeakerConfig(_SpeakerConfig): #undocumented
    function = "SSSPCSUD "
    
@Denon.add_feature
class SubwooferSpeakerConfig(_SpeakerConfig): #undocumented
    function = "SSSPCSWF "
    translation = {"YES":"Yes","NO":"No"}

@Denon.add_feature
class DevicePower(PowerFeature):
    category = Category.GENERAL
    function = "PW"
    translation = {"ON":True,"STANDBY":False}
    dummy_value = True

    def on_change(self, val):
        super().on_change(val)
        if not isinstance(self.target, ServerType): return
        def func(*power_features):
            if val == True:
                if not any([f.get() for f in power_features]) and len(power_features) >= 1:
                    power_features[0].set(True)
            else:
                for f in power_features: f.set(False)
        self.target.schedule(func, requires=self.target._power_features)


@Denon.add_feature
class Muted(BoolFeature):
    category = Category.VOLUME
    function = "MU"

@Denon.add_feature
class SourceNames(ListFeature): #undocumented
    """
    SSFUN ?
    SSFUNSAT/CBL CBL/SAT
    SSFUNMPLAY Media Player
    SSFUN END    
    """
    category = Category.INPUT
    type = dict
    TERMINATOR = " END"
    function = "SSFUN"
    call = "SSFUN ?"
    default_value = {code: "% -12s"%name for code, f_id, name in SOURCES}
    def remote_set(self, *args, **xargs): raise RuntimeError("Cannot set value! Set source instead")
    def serialize(self, d): return super().serialize([" ".join(e) for e in d.items()])
    def unserialize(self, data): return dict([line.split(" ",1) for line in super().unserialize(data)])


@Denon.add_feature
class Source(DynamicSelectFeature):
    category = Category.INPUT
    function = "SI"
    translation_source = SourceNames
    translation = {"NET":"Heos", "BT":"Bluetooth", "USB":"USB"}

    def _send(self, *args, **xargs):
        super()._send(*args, **xargs)
        if isinstance(self.target, ClientType):
            self.async_poll()


@Denon.add_feature(overwrite=True)
class Name(features.ServerToClientFeatureMixin, SelectFeature): #undocumented
    default_value = "Denon AVR"
    dummy_value = f"Dummy {DUMMY_MODEL}"
    function = "NSFRN "


@Denon.add_feature
class SpeakerLevelBlock(FeatureBlock):
    function = "SSLEV"
    call = "SSLEV ?"
    category = Category.SPEAKERS


for code, f_id, name in SPEAKERS:
    @Denon.add_feature(parent=SpeakerLevelBlock)
    class SpeakerLevel(RelativeDecimal): #undocumented
        name = f"{name} Level"
        id = f"{f_id}_level"
        category = Category.SPEAKERS
        function = f"{code} "


@Denon.add_feature(parent=SpeakerLevelBlock)
class SpeakerLevelBlockTerminator(BlockTerminator):
    value = " END"
    category = Category.SPEAKERS


@Denon.add_feature
class ChannelVolumeBlock(FeatureBlock):
    function = "CV"
    category = Category.VOLUME


for code, f_id, name in SPEAKERS:
    @Denon.add_feature(parent=ChannelVolumeBlock)
    class ChannelVolume(RelativeDecimal):
        name = f"{name} Volume"
        id = f"{f_id}_volume"
        category = Category.VOLUME
        function = f"{code} "


@Denon.add_feature(parent=ChannelVolumeBlock)
class ChannelVolumeBlockTerminator(BlockTerminator):
    category = Category.VOLUME


@Denon.add_feature
class MainZonePower(ZonePowerFeature):
    id = "power"
    category = Category.GENERAL
    function = "ZM"
    dummy_value = True

@Denon.add_feature
class RecSelect(SelectFeature): function = "SR"

@Denon.add_feature
class InputMode(SelectFeature):
    category = Category.INPUT
    translation = {"AUTO":"Auto", "HDMI":"HDMI", "DIGITAL":"Digital", "ANALOG": "Analog"}
    function = "SD"

@Denon.add_feature
class DigitalInput(SelectFeature):
    category = Category.INPUT
    function = "DC"
    translation = {"AUTO":"Auto", "PCM": "PCM", "DTS":"DTS"}
    
@Denon.add_feature
class VideoSelect(SelectFeature):
    name = "Video Select Mode"
    category = Category.VIDEO
    function = "SV"
    translation = {"DVD":"DVD", "BD": "Blu-Ray", "TV":"TV", "SAT/CBL": "CBL/SAT", "DVR": "DVR", "GAME": "Game", "GAME2": "Game2", "V.AUX":"V.Aux", "DOCK": "Dock", "SOURCE":"cancel", "OFF":"Off"}

@Denon.add_feature
class Sleep(IntFeature):
    min = 0 # 1..120, 0 will send "OFF"
    max = 120
    name = "Main Zone Sleep (minutes)"
    function = "SLP"
    def serialize_val(self, val): return "OFF" if val==0 else super().serialize_val(val)
    def unserialize_val(self, val): return 0 if val=="OFF" else super().unserialize_val(val)

@Denon.add_feature
class SoundMode(SelectFeature): #undocumented
    category = Category.GENERAL
    function = "SSSMG "
    translation = {"MOV":"Movie", "MUS":"Music", "GAM":"Game", "PUR":"Pure"}
    translation_inv = {"Movie":"MSMOVIE", "Music":"MSMUSIC", "Game":"MSGAME", "Pure":"MSDIRECT"}
    
    def serialize(self, value):
        if isinstance(self.target, ClientType): return [self.translation_inv[value]]
        else: return super().serialize(value)

    def on_change(self, val):
        super().on_change(val)
        self.target.features.sound_mode_setting.async_poll(force=True)
        self.target.features.sound_mode_settings.async_poll(force=True)


class _SoundModeSettings:
    category = Category.GENERAL
    function = 'OPSML '


@Denon.add_feature
class SoundModeCall(_SoundModeSettings, DenonFeature, features.Feature):
    def is_set(self): return True
    def matches(self, data): return False
    def remote_set(self, *args, **xargs): raise NotImplementedError()
    def set(self, *args, **xargs): raise NotImplementedError()

    def resend(self):
        if isinstance(self.target, ServerType):
            self.target.schedule(lambda f: f.resend(), requires=(SoundModeSettings.id,))
        else: super().resend()


@Denon.add_feature
class SoundModeSettings(_SoundModeSettings, ListFeature): # according to current sound mode #undocumented
    type = dict
    call = None
    dummy_value = {"010":"Stereo", "020":"Dolby Surround", "030":"DTS Neural:X", "040":"DTS Virtual:X", "050":"Multi Ch Stereo", "061":"Mono Movie", "070":"Virtual"}

    def poll_on_client(self, *args, **xargs):
        self.target.features[SoundModeCall.id].poll_on_client(*args, **xargs)

    def serialize(self, d):
        return super().serialize(
            ["".join([key[:2], str(int(self.target.features.sound_mode_setting.get() == val)), val])
            for key, val in d.items()])

    def unserialize(self, data): return {e[:3]: e[3:] for e in super().unserialize(data)}

    def resend(self):
        self.target.schedule(lambda f: super(SoundModeSettings, self).resend(),
            requires=("sound_mode_setting",))

    def remote_set(self, *args, **xargs):
        self.target.schedule(lambda f: super(SoundModeSettings, self).remote_set(*args, **xargs),
            requires=("sound_mode_setting",))


@Denon.add_feature
class SoundModeSetting(_SoundModeSettings, SelectFeature):
    call = None
    dummy_value = "Stereo"

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.target.features.sound_mode_settings.bind(self.on_sound_modes_change)

    def poll_on_client(self, *args, **xargs):
        self.target.features[SoundModeCall.id].poll_on_client(*args, **xargs)

    def on_sound_modes_change(self, sound_modes):
        self.translation = sound_modes
        if self.is_set():
            self.on_change(self.get()) # cause listeners to update from self.translation
        
    def matches(self, data): return super().matches(data) and data[len(self.function)+2] == "1"
    def serialize_val(self, val): return "%s1%s"%(super().serialize_val(val)[:2], val)
    def unserialize_val(self, data): return data[3:]

    def _send(self, *args, **xargs):
        if isinstance(self.target, ClientType): return super()._send(*args, **xargs)
        else:
            self.target.schedule(lambda *_: self.target.features.sound_mode_settings.resend(),
                requires=(SoundModeSettings.id,))


@Denon.add_feature
class TechnicalSoundMode(SelectFeature):
    category = Category.GENERAL
    function = "MS"
    translation = {"MOVIE":"Movie", "MUSIC":"Music", "GAME":"Game", "DIRECT": "Direct", "PURE DIRECT":"Pure Direct", "STEREO":"Stereo", "STANDARD": "Standard", "DOLBY DIGITAL":"Dolby Digital", "DTS SURROUND":"DTS Surround", "MCH STEREO":"Multi ch. Stereo", "ROCK ARENA":"Rock Arena", "JAZZ CLUB":"Jazz Club", "MONO MOVIE":"Mono Movie", "MATRIX":"Matrix", "VIDEO GAME":"Video Game", "VIRTUAL":"Virtual",
        "VIRTUAL:X":"DTS Virtual:X","NEURAL:X":"DTS Neural:X","DOLBY SURROUND":"Dolby Surround","M CH IN+DS":"Multi Channel In + Dolby S.", "M CH IN+NEURAL:X": "Multi Channel In + DTS Neural:X", "M CH IN+VIRTUAL:X":"Multi Channel In + DTS Virtual:X", "MULTI CH IN":"Multi Channel In", #undocumented
    }

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        if isinstance(self.target, ServerType): self.bind(on_change=self.update_sound_mode)

    def update_sound_mode(self, val):
        sound_mode = self.target.features.sound_mode
        if val in sound_mode.options: sound_mode.set(val)

    def matches(self, data): return super().matches(data) and not data.startswith("MSQUICK")
    def on_change(self, val):
        super().on_change(val)
        self.target.features["%s_volume"%SPEAKERS[0][1]].async_poll(force=True)
        self.target.features.sound_mode_setting.async_poll(force=True)


@Denon.add_feature
class QuickSelectNames(ListFeature): #undocumented
    function = 'SSQSNZMA'
    call = 'SSQSNZMA ?'
    TERMINATOR = " END"
    type = dict
    default_value = {str(i): f"Quick Select {i}" for i in QUICK_SELECT_KEYS}
    def serialize(self, val): return super().serialize([f"QS{i} {name}" for i, name in val.items()])
    def unserialize(self, data):
        return dict(sorted([(l[2], l[4:]) for l in super().unserialize(data)]))


class _QuickSelect(DynamicSelectFeature):
    function="MSQUICK"
    translation_source = QuickSelectNames


@Denon.add_feature
class QuickSelect(_QuickSelect):
    name = "Quick Select (load)"
    call="MSQUICK ?"
    def get(self): return "(None)" if super().get() == "0" else super().get()
    def matches(self, data): return super().matches(data) and not data.endswith("MEMORY")


@Denon.add_feature
class QuickSelectStore(features.ClientToServerFeatureMixin, _QuickSelect):
    name = "Quick Select (save)"
    
    # for server:
    def matches(self, data): return super().matches(data) and data.endswith("MEMORY")
    def serialize_val(self, value): return f"{value} MEMORY"
    def unserialize_val(self, data): return data.split(" ",1)[0]
    
    def on_change(self, val):
        super().on_change(val)
        self.target.features.quick_select.set(val)
        
    def resend(self):
        self.target.schedule(lambda quick_select: quick_select.resend(), requires=("quick_select",))


@Denon.add_feature
class QuickSelectSourcesBlock(FeatureBlock): #undocumented
    function = "SSQSSZMA"
    call = f"{function} ?"


for i in QUICK_SELECT_KEYS:
    @Denon.add_feature(parent=QuickSelectSourcesBlock)
    class QuickSelect(DynamicSelectFeature): #undocumented
        id = f"quick_select_source_{i}"
        name = f"Quick Select {i}: Source"
        function = f"QS{i} "
        translation_source = SourceNames


@Denon.add_feature
class HdmiMonitor(SelectFeature):
    name = "HDMI Monitor auto detection"
    category = Category.VIDEO
    function = "VSMONI"
    call = "VSMONI ?"
    translation = {"MONI1":"OUT-1", "MONI2":"OUT-2"}
    
@Denon.add_feature
class Asp(SelectFeature):
    name = "ASP mode"
    function = "VSASP"
    call = "VSASP ?"
    translation = {"NRM":"Normal", "FUL":"Full"}
    
class _Resolution(SelectFeature):
    category = Category.VIDEO
    translation = {"48P":"480p/576p", "10I":"1080i", "72P":"720p", "10P":"1080p", "10P24":"1080p:24Hz", "AUTO":"Auto"}

@Denon.add_feature
class Resolution(_Resolution):
    function = "VSSC"
    call = "VSSC ?"
    def matches(self, data): return super().matches(data) and not data.startswith("VSSCH")
    
@Denon.add_feature
class HdmiResolution(_Resolution):
    name = "HDMI Resolution"
    function = "VSSCH"
    call = "VSSCH ?"

@Denon.add_feature
class HdmiAudioOutput(SelectFeature):
    name = "HDMI Audio Output"
    category = Category.VIDEO
    function = "VSAUDIO "
    translation = {"AMP":"to Amp", "TV": "to TV"}
    
@Denon.add_feature
class VideoProcessingMode(SelectFeature):
    category = Category.VIDEO
    function = "VSVPM"
    call = "VSVPM ?"
    translation = {"AUTO":"Auto", "GAME":"Game", "MOVI": "Movie"}
    
@Denon.add_feature
class ToneControl(BoolFeature):
    category = Category.GENERAL
    function = "PSTONE CTRL "
    
@Denon.add_feature
class SurroundBackMode(SelectFeature):
    name = "Surround Back SP Mode"
    function = "PSSB:"
    call = "PSSB: ?"
    translation = {"MTRX ON": "Matrix", "PL2x CINEMA":"Cinema", "PL2x MUSIC": "Music", "ON":"On", "OFF":"Off"}
    
@Denon.add_feature
class CinemaEq(BoolFeature):
    name = "Cinema Eq."
    function = "PSCINEMA EQ."
    call = "PSCINEMA EQ. ?"

@Denon.add_feature
class Mode(SelectFeature):
    function = "PSMODE:"
    call = "PSMODE: ?"
    translation = {"MUSIC":"Music","CINEMA":"Cinema","GAME":"Game","PRO LOGIC":"Pro Logic"}
    
@Denon.add_feature
class FrontHeight(BoolFeature):
    function = "PSFH:"
    call = "PSFH: ?"

@Denon.add_feature
class Pl2hg(SelectFeature):
    name = "PL2z Height Gain"
    function = "PSPHG "
    translation = {"LOW":"Low","MID":"Medium","HI":"High"}
    
@Denon.add_feature
class SpeakerOutput(SelectFeature):
    function = "PSSP:"
    call = "PSSP: ?"
    translation = {"FH":"F. Height", "FW":"F. Wide", "SB":"S. Back"}
    
@Denon.add_feature
class MultEq(SelectFeature):
    name = "MultEQ XT mode"
    category = Category.AUDYSSEY
    function = "PSMULTEQ:"
    call = "PSMULTEQ: ?"
    translation = {"AUDYSSEY":"Audyssey", "BYP.LR":"L/R Bypass", "FLAT":"Flat", "MANUAL":"Manual", "OFF":"Off"}
    
@Denon.add_feature
class DynamicEq(BoolFeature):
    category = Category.AUDYSSEY
    function = "PSDYNEQ "
    
@Denon.add_feature
class ReferenceLevel(SelectFeature):
    category = Category.AUDYSSEY
    function = "PSREFLEV "
    translation = {"0":"0 dB","5":"5 dB","10":"10 dB","15":"15 dB"}
    
@Denon.add_feature
class DynamicVolume(SelectFeature):
    category = Category.AUDYSSEY
    function = "PSDYNVOL "
    options = ["Off","Light","Medium","Heavy"]
    translation = {"LIT":"Light","MED":"Medium","HEV":"Heavy", #undocumented
        "NGT":"Heavy", "EVE":"Medium", "DAY":"Light","OFF":"Off"}
    
@Denon.add_feature
class AudysseyDsx(SelectFeature):
    name = "Audyssey DSX"
    category = Category.AUDYSSEY
    function = "PSDSX "
    translation = {"ONH":"On (Height)", "ONW":"On (Wide)","OFF":"Off"}
    
@Denon.add_feature
class StageWidth(IntFeature): function = "PSSTW "

@Denon.add_feature
class StageHeight(IntFeature): function = "PSSTH "
    
@Denon.add_feature
class Bass(RelativeInt):
    category = Category.GENERAL
    function = "PSBAS "
    
@Denon.add_feature
class Treble(RelativeInt):
    category = Category.GENERAL
    function = "PSTRE "
    
@Denon.add_feature
class Drc(SelectFeature):
    function = "PSDRC "
    translation = {"AUTO":"Auto", "LOW":"Low", "MID":"Medium", "HI":"High", "OFF":"Off"}

@Denon.add_feature
class DynamicCompression(SelectFeature):
    function = "PSDCO "
    translation = {"LOW":"Low", "MID":"Medium", "HI":"High", "OFF":"Off"}

@Denon.add_feature
class Lfe(IntFeature):
    name = "LFE"
    category = Category.AUDIO
    function = "PSLFE "
    min=-10
    max=0
    def unserialize_val(self, val): return super().unserialize_val(val)*-1
    def serialize_val(self, val): return super().serialize_val(val*-1)

@Denon.add_feature
class EffectLevel(IntFeature): function = "PSEFF "
    
@Denon.add_feature
class Delay(IntFeature):
    category = Category.AUDIO
    max=999
    function = "PSDEL "
    
@Denon.add_feature
class Afd(BoolFeature):
    name = "AFDM"
    function = "PSAFD "
    
@Denon.add_feature
class Panorama(BoolFeature): function = "PSPAN "

@Denon.add_feature
class Dimension(IntFeature): function = "PSDIM "

@Denon.add_feature
class CenterWidth(IntFeature): function = "PSCEN "
    
@Denon.add_feature
class CenterImage(IntFeature): function = "PSCEI "
    
@Denon.add_feature
class Subwoofer(BoolFeature):
    category = Category.BASS
    function = "PSSWR "

class _SubwooferAdjustment: #undocumented
    category = Category.BASS
    #category = Category.AUDIO
    function = "PSSWL "
    name = "Subwoofer Adjustment"

@Denon.add_feature
class SubwooferAdjustmentActive(_SubwooferAdjustment, LooseBoolFeature): pass

@Denon.add_feature
class SubwooferAdjustment(_SubwooferAdjustment, LooseDecimalFeature): pass

class _DialogLevel: #undocumented
    category = Category.AUDIO
    function = "PSDIL "
    name = "Dialog Level"

@Denon.add_feature
class DialogLevelActive(_DialogLevel, LooseBoolFeature): pass

@Denon.add_feature
class DialogLevel(_DialogLevel, LooseDecimalFeature): pass

@Denon.add_feature
class RoomSize(SelectFeature):
    function = "PSRSZ "
    translation = {e:e for e in ["S","MS","M","ML","L"]}
    
@Denon.add_feature
class AudioDelay(IntFeature):
    category = Category.AUDIO
    max = 999
    function = "PSDELAY "

@Denon.add_feature
class Restorer(SelectFeature):
    name = "Audio Restorer"
    category = Category.AUDIO
    function = "PSRSTR "
    translation = {"OFF":"Off", "MODE1":"Mode 1", "MODE2":"Mode 2", "MODE3":"Mode 3"}
    
@Denon.add_feature
class FrontSpeaker(SelectFeature):
    function = "PSFRONT"
    translation = {" SPA":"A"," SPB":"B"," A+B":"A+B"}

@Denon.add_feature
class CrossoverBlock(FeatureBlock):
    function = "SSCFR"
    call = "SSCFR ?"
    category = Category.SPEAKERS

@Denon.add_feature(parent=CrossoverBlock)
class Crossover(SelectFeature): #undocumented
    name = "Crossover Speaker Select"
    category = Category.SPEAKERS
    function = " "
    translation = {"ALL":"All","IDV":"Individual"}
    def matches(self, data): return super().matches(data) and "END" not in data

class _Crossover(SelectFeature): #undocumented
    category = Category.SPEAKERS
    translation = {x:"%d Hz"%int(x)
        for x in ["040","060","080","090","100","110","120","150","200","250"]}

@Denon.add_feature(parent=CrossoverBlock)
class CrossoverAll(_Crossover): #undocumented
    name = "Crossover (all)"
    function = "ALL "

for code, f_id, name in SPEAKER_PAIRS:
    @Denon.add_feature(parent=CrossoverBlock)
    class CrossoverSpeaker(_Crossover): #undocumented
        name = f"Crossover ({name})"
        id = f"crossover_{f_id}"
        function = f"{code} "

@Denon.add_feature(parent=CrossoverBlock)
class CrossoverBlockTerminator(BlockTerminator):
    value = " END"
    category = Category.SPEAKERS


@Denon.add_feature
class SubwooferMode(SelectFeature): #undocumented
    category = Category.BASS
    function = "SSSWM "
    translation = {"L+M":"LFE + Main", "LFE":"LFE"}
    
@Denon.add_feature
class LfeLowpass(SelectFeature): #undocumented
    name = "LFE Lowpass Freq."
    category = Category.BASS
    function = "SSLFL "
    translation = {x:"%d Hz"%int(x) 
        for x in ["080","090","100","110","120","150","200","250"]}

@Denon.add_feature
class Display(SelectFeature):
    function = "DIM "
    translation = {"BRI":"Bright","DIM":"Dim","DAR":"Dark","OFF":"Off"}

@Denon.add_feature
class Idle(features.ServerToClientFeatureMixin, BoolFeature): #undocumented
    """
    Information on Audio Input Signal
    Value seems to indicate if amp is playing something via HDMI
    """
    category = Category.INPUT
    function = "SSINFAISSIG "
    translation = {"01": True, "02": False, "12": True} #01: analog, 02: PCM

    def matches(self, data): return super().matches(data) and isinstance(self.unserialize([data]), bool)


@Denon.add_feature
class Bitrate(features.ServerToClientFeatureMixin, SelectFeature):
    category = Category.INPUT
    function = "SSINFAISFSV "
    translation = {"NON": "-", "441": "44.1 kHz", "48K": "48 kHz"}
    dummy_value = "441"


@Denon.add_feature
class SampleRate(SelectFeature): #undocumented
    """ Information on Audio Input Signal Sample Rate """
    category = Category.INPUT
    function = "SSINFAISFV "


@Denon.add_feature
class AutoStandby(SelectFeature):
    category = Category.ECO
    function = "STBY"
    translation = {"OFF":"Off","15M":"15 min","30M":"30 min","60M":"60 min"}


@Denon.add_feature
class AmpAssign(SelectFeature): #undocumented
    category = Category.SPEAKERS
    function = "SSPAAMOD "
    call = "SSPAA ?"
    translation = {"FRB": "Front B", "BIA": "Bi-Amping", "NOR": "Surround Back", "FRH": "Front Height", "TFR": "Top Front", "TPM": "Top Middle", "FRD": "Front Dolby", "SUD": "Surround Dolby", **{"ZO%s"%zone:"Zone %s"%zone for zone in ZONES}}


@Denon.add_feature
class OsdBlock(FeatureBlock):
    category = Category.VIDEO
    function = "SSOSD"
    call = f"{function} ?"


@Denon.add_feature(parent=OsdBlock)
class VolumeOsd(SelectFeature): #undocumented
    category = Category.VIDEO
    function = "VOL "
    translation = {"TOP":"Top","BOT":"Bottom","OFF":"Off"}


@Denon.add_feature(parent=OsdBlock)
class InfoOsd(BoolFeature): #undocumented
    category = Category.VIDEO
    function = "TXT "


@Denon.add_feature(parent=OsdBlock)
class OsdFormat(SelectFeature): #undocumented
    category = Category.VIDEO
    function = "FMT "
    dummy_value = "PAL"


@Denon.add_feature(parent=OsdBlock)
class OsdPbs(SelectFeature): #undocumented
    category = Category.VIDEO
    function = "PBS "
    dummy_value = "ALW"


@Denon.add_feature
class HdmiRcSelect(SelectFeature): #undocumented
    function = "SSHOSRSS "
    call = "SSHOS ?"
    translation = {"POS":"Power On + Source", "SSO":"Only Source"}


@Denon.add_feature
class HdmiControl(BoolFeature): #undocumented
    function = "SSHOSCON "
    call = "SSHOS ?"


@Denon.add_feature
class Language(SelectFeature): #undocumented
    function = "SSLAN "
    translation = {"DEU":"German", "ENG":"English", "ESP":"Spanish", "POL":"Polish", "RUS": "Russian",
        "FRA":"French", "ITA":"Italian", "NER":"Dutch", "SVE":"Swedish"}


@Denon.add_feature
class EcoMode(SelectFeature): #undocumented
    category = Category.ECO
    function = "ECO"
    translation = {"AUTO":"Auto","ON":"On","OFF":"Off"}


@Denon.add_feature
class InputVisibilityBlock(FeatureBlock):
    function = "SSSOD"
    call = "SSSOD ?"


for code, f_id, name in SOURCES:
    @Denon.add_feature(parent=InputVisibilityBlock)
    class InputVisibility(BoolFeature): #undocumented
        name = f"Enable {name} Input"
        id = f"enable_{f_id}"
        category = Category.INPUT
        function = f"{code} "
        translation = {"USE":True, "DEL":False}


@Denon.add_feature(parent=InputVisibilityBlock)
class InputVisibilityBlockTerminator(BlockTerminator):
    value = " END"


@Denon.add_feature
class SourceVolumeLevelBlock(FeatureBlock):
    function = f"SSSLV"
    call = f"SSSLV ?"
    category = Category.INPUT


for code, f_id, name in SOURCES:
    @Denon.add_feature(parent=SourceVolumeLevelBlock)
    class SourceVolumeLevel(RelativeInt): #undocumented
        name = f"{name} Volume Level"
        id = f"{f_id}_volume_level"
        category = Category.INPUT
        min = -12
        max = 12
        function = f"{code} "
        def remote_set(self, *args, **xargs):
            super().remote_set(*args, **xargs)
            self.async_poll(force=True) #Denon workaround: missing echo


@Denon.add_feature(parent=SourceVolumeLevelBlock)
class SourceVolumeLevelBlockTerminator(BlockTerminator):
    value = " END"
    category = Category.INPUT


@Denon.add_feature
class SpeakerDistanceBlock(FeatureBlock):
    category = Category.SPEAKERS
    function = "SSSDE"
    call = f"{function} ?"


@Denon.add_feature(parent=SpeakerDistanceBlock)
class SpeakerDistanceStep(SelectFeature): #undocumented
    category = Category.SPEAKERS
    function = "STP "
    translation = {"01M": "0.1m", "02M": "0.01m", "01F": "1ft", "02F": "0.1ft"}


for code, f_id, name in SPEAKERS:
    @Denon.add_feature(parent=SpeakerDistanceBlock)
    class SpeakerDistance(IntFeature): #undocumented
        name = f"{name} Distance"
        id = f"{f_id}_distance"
        category = Category.SPEAKERS
        min = 0
        max = 1800
        function = f"{code} "


@Denon.add_feature(parent=SpeakerDistanceBlock)
class SpeakerDistanceBlockTerminator(BlockTerminator):
    category = Category.SPEAKERS
    value = " END"


@Denon.add_feature
class MenuVisibility(BoolFeature): #undocumented
    category = Category.VIDEO
    function = "MNMEN "


@Denon.add_feature
class VersionInformationBlock(FeatureBlock):
    function = "VIALL"

@Denon.add_feature(parent=VersionInformationBlock)
class AvrModel(SelectFeature):
    function = "AVR"
    dummy_value = f"{DUMMY_MODEL} E2"

@Denon.add_feature(parent=VersionInformationBlock)
class SerialNumber(SelectFeature):
    function = "S/N."
    dummy_value = "ABC01234567890"

@Denon.add_feature(parent=VersionInformationBlock)
class VersionInformation(ListFeature):
    function = ""
    TERMINATOR = "END:END"
    dummy_value = [
        #f"AVR{DUMMY_MODEL} E2",
        #"S/N.ABC01234567890",
        "MAIN:7897897897897",
        "MAINFBL:00.30",
        "DSP:07.17",
        "APLD:60.03",
        "GUIDAT:98798798",
        "HIMG:58464D16",
        "HEOSVER:2.71.270",
        "HEOSBLD:205357",
        "HEOSMOD:5",
        "HEOSCNF:Production",
        "HEOSLCL:en_EU",
        "MAC:012345-6789AB",
        "WIFIMAC:CDEF01-234567",
        "BTMAC:89ABCD-EF0123",
        "AUDYIF:00.08",
        "PRODUCTID:000123456789",
        "PACKAGEID:0014",
        "CMP:OK",
    ]


@Denon.add_feature
class VolumeScale(SelectFeature):
    category = Category.VOLUME
    function = "SSVCTZMADIS "
    call = "SSVCTZMA ?"
    translation = {"REL":"-79-18 dB", "ABS":"0-98"}


@Denon.add_feature
class PowerOnLevel(LooseIntFeature):
    category = Category.VOLUME
    id = "power_on_level_numeric"
    function = "SSVCTZMAPON "
    call = "SSVCTZMA ?"
    def resend(self):
        return #handled by power_on_level


@Denon.add_feature
class PowerOnLevel(SelectFeature):
    category = Category.VOLUME
    function = "SSVCTZMAPON "
    call = "SSVCTZMA ?"
    translation = {"MUT":"Muted", "LAS":"Unchanged"}
    def on_change(self, val):
        super().on_change(val)
        if not self.target.features.power_on_level_numeric.is_set():
            self.target.features.power_on_level_numeric.set(0)


@Denon.add_feature
class MuteMode(SelectFeature):
    category = Category.VOLUME
    function = "SSVCTZMAMLV "
    call = "SSVCTZMA ?"
    translation = {"MUT":"Full", "040":"-40 dB", "060":"-20 dB"}


def create_source_input_assign_block(input_code, input_value_code, input_id, input_name):
    @Denon.add_feature
    class SourceInputAssignBlock(FeatureBlock):
        id = f"input_{input_id}_block"
        category = Category.INPUT
        function = f"SS{input_code}"
    return input_id, SourceInputAssignBlock

sourceInputAssignBlocks = dict([create_source_input_assign_block(*args) for args in INPUTS])

for input_code, input_value_code, input_id, input_name in INPUTS:
    for source_code, source_id, source_name in SOURCES:
        @Denon.add_feature(parent=sourceInputAssignBlocks[input_id])
        class SourceInputAssign(SelectFeature):
            name = f"{source_name} {input_name} Input"
            id = f"input_{source_id}_{input_id}"
            category = Category.INPUT
            function = f"{source_code} "
            call = f"SS{input_code} ?"
            translation = {"OFF":"None", "FRO":"Front",
                **{f"{input_value_code}{i}":f"{input_name} {i}" for i in range(7)}}

for input_code, input_value_code, input_id, input_name in INPUTS:
    @Denon.add_feature(parent=sourceInputAssignBlocks[input_id])
    class SourceInputAssignBlockTerminator(BlockTerminator):
        id = f"input_{input_id}_block_terminator"
        category = Category.INPUT
        value = " END"

del sourceInputAssignBlocks


class Equalizer: category = Category.EQUALIZER

@Denon.add_feature
class EqualizerActive(Equalizer, BoolFeature): function = "PSGEQ "

@Denon.add_feature
class EqualizerChannels(Equalizer, SelectFeature):
    function = "SSGEQSPS "
    translation = {cat_code: cat_name for cat_code, cat_id, cat_name, l in EQ_OPTIONS}

for cat_code, cat_id, cat_name, l in EQ_OPTIONS:
    @Denon.add_feature
    class SpeakerEqBlock(Equalizer, FeatureBlock):
        id = cat_id
        function = f"SSAEQ{cat_code}"
        call = f"SSAEQ{cat_code} ?"

    for code, sp_id, name in l:

        @Denon.add_feature(parent=SpeakerEqBlock)
        class SpeakerEq(Equalizer, DenonFeature, features.Feature): #undocumented
            name = f"Eq {name}"
            type = dict
            id = f"eq_{cat_id}_{sp_id}"
            function = f"{code} "
            dummy_value = {i:0 for i in range(9)}
            
            def serialize_val(self, d): return ":".join(["%d"%(v*10+500) for v in d.values()])

            def unserialize_val(self, data):
                return {i: Decimal(v)/10-50 for i, v in enumerate(data.split(":"))}

            def set_value(self, key, val):
                self.set({**self.get(), key:DecimalFeature._roundVolume(val)})

            def remote_set_value(self, key, val, *args, **xargs):
                self.remote_set({**self.get(), key:DecimalFeature._roundVolume(val)}, *args, **xargs)


        for bound, bound_name in enumerate(EQ_BOUNDS):

            @Denon.add_feature
            class Bound(Equalizer, features.OfflineFeatureMixin, DecimalFeature): #undocumented
                name = f"Eq {name} {bound_name}"
                id = f"eq_{cat_id}_{sp_id}_bound{bound}"
                min = -20
                max = +6
                
                def __init__(self, *args, cat_id=cat_id, sp_id=sp_id, **xargs):
                    super().__init__(*args, **xargs)
                    self._channels = self.target.features.equalizer_channels
                    self._channels.bind(on_change = self.update)
                    self._speaker_eq = self.target.features[f"eq_{cat_id}_{sp_id}"]
                    self._speaker_eq.bind(on_change = self.update)
                
                def update(self, val, cat_name=cat_name, bound=bound):
                    if isinstance(self.target, ServerType): return
                    is_set = self._channels.is_set() and self._channels.get() == cat_name \
                        and self._speaker_eq.is_set()
                    super().set(self._speaker_eq.get()[bound]) if is_set else self.unset()
                
                def set(self, value, bound=bound): self._speaker_eq.set_value(bound, self.type(value))

                def remote_set(self, value, *args, bound=bound, **xargs):
                    self._speaker_eq.remote_set_value(bound, self.type(value))
                
                def async_poll(self, *args, **xargs):
                    if not self._channels.is_set(): self._channels.async_poll(*args, **xargs)
                    if not self._speaker_eq.is_set(): self._speaker_eq.async_poll(*args, **xargs)


    if len(l) > 1:
        @Denon.add_feature(parent=SpeakerEqBlock)
        class SpeakerEqBlockTerminator(Equalizer, BlockTerminator):
            id = f"{cat_id}_end"


@Denon.add_feature
class EnergyUse(IntFeature): #undocumented
    category = Category.ECO
    function = "SSECOSTS "


@Denon.add_feature
class Optpn(SelectFeature): #undocumented
    #OPTPN01         008750
    function = "OPTPN"
    call = f"{function} ?"


@Denon.add_feature
class TunerBlock(FeatureBlock): #undocumented
    function = "OPTPSTUNER"
    call = "OPTPSTUNER ?"

for i in range(1, 57):
    @Denon.add_feature(parent=TunerBlock)
    class Tuner(BoolFeature): #undocumented
        i_ = "%02d"%i
        function = f"{i_} "
        id = f"tuner_{i_}"
        name = f"Tuner #{i_}"


@Denon.add_feature
class LrsSts(SelectFeature): #undocumented
    function = "SSLRSSTS "

@Denon.add_feature
class SdpSts(SelectFeature): #undocumented
    function = "SSSDPSTS "

@Denon.add_feature
class Loc(BoolFeature): #undocumented
    function = "SSLOC "

@Denon.add_feature
class AlsBlock(FeatureBlock): #undocumented
    function = "SSALS"
    call = f"{function} ?"

@Denon.add_feature(parent=AlsBlock)
class AlsSet(BoolFeature): #undocumented
    function = "SET "

@Denon.add_feature(parent=AlsBlock)
class AlsDsp(BoolFeature): #undocumented
    function = "DSP "

@Denon.add_feature(parent=AlsBlock)
class AlsVal(IntFeature): #undocumented
    function = "VAL "
    min = 0
    max = 999

@Denon.add_feature
class Heq(BoolFeature): #undocumented
    function = "PSHEQ "

@Denon.add_feature
class FirmwareBlock(FeatureBlock):
    function = "SSINFFRM"
    call = f"{function} ?"

@Denon.add_feature(parent=FirmwareBlock)
class FirmwareVersion(SelectFeature): #undocumented
    function = "AVR "
    dummy_value = "4700-2061-1072-1070"

@Denon.add_feature(parent=FirmwareBlock)
class DtsVersion(SelectFeature): #undocumented
    function = "DTS "
    dummy_value = "3.90.50.00"

@Denon.add_feature(parent=FirmwareBlock)
class FirmwareBlockTerminator(BlockTerminator):
    value = " END"


for zone in ZONES:
    
    class Zone:
        category = getattr(Category, f"ZONE_{zone}")
    
    @Denon.add_feature
    class ZVolume(Zone, Volume):
        name = "Zone %s Volume"%zone
        id = "zone%s_volume"%zone
        function = "Z%s"%zone
        
    @Denon.add_feature
    class ZPower(Zone, ZonePowerFeature):
        name = "Zone %s Power"%zone
        id = "zone%s_power"%zone
        function = "Z%s"%zone
        def matches(self, data): return super().matches(data) and data[len(self.function):] in self.translation
    
    @Denon.add_feature
    class ZSource(Zone, Source):
        name = "Zone %s Source"%zone
        id = "zone%s_source"%zone
        function = "Z%s"%zone
        translation = {**Source.translation, "SOURCE": "Main Zone"}
        _from_mainzone = False
        
        def __init__(self, *args, **xargs):
            super().__init__(*args, **xargs)
            self.target.features.source.bind(lambda *_:self._resolve_main_zone_source())

        def matches(self, data): return super().matches(data) and data[len(self.function):] in self.translation

        def _resolve_main_zone_source(self):
            self.target.schedule(lambda source: self._from_mainzone and Source.set(self, source.get()),
                requires=("source",))

        def set(self, data):
            self._from_mainzone = data == "Main Zone"
            if self._from_mainzone: self._resolve_main_zone_source()
            else: return super().set(data)
        
        def unset(self):
            super().unset()
            self._from_mainzone = False
    
    @Denon.add_feature
    class ZMuted(Zone, Muted):
        name = "Zone %s Muted"%zone
        id = "zone%s_muted"%zone
        function = "Z%sMU"%zone
    
    @Denon.add_feature
    class ChannelSetting(Zone, SelectFeature):
        id = "zone%s_channel_setting"%zone
        function = "Z%sCS"%zone
        translation = {"MONO":"Mono","ST":"Stereo"}
    
    @Denon.add_feature
    class ZFrontLeftVolume(Zone, RelativeDecimal):
        id = "zone%s_front_left_volume"%zone
        name = "Front Left Volume"
        function = "Z%sFL "%zone
        call = "Z%sCV?"%zone
        
    @Denon.add_feature
    class ZFrontRightVolume(Zone, RelativeDecimal):
        id = "zone%s_front_right_volume"%zone
        name = "Front Right Volume"
        function = "Z%sFR "%zone
        call = "Z%sCV?"%zone
        
    @Denon.add_feature
    class Hpf(Zone, BoolFeature):
        id = "zone%s_hpf"%zone
        name = "HPF"
        function = "Z%sHPF"%zone
    
    @Denon.add_feature
    class ZBass(Zone, RelativeInt):
        name = "Zone %s Bass"%zone
        id = "zone%s_bass"%zone
        function = "Z%sPSBAS "%zone
        
    @Denon.add_feature
    class ZTreble(Zone, RelativeInt):
        name = "Zone %s Treble"%zone
        id = "zone%s_treble"%zone
        function = "Z%sPSTRE "%zone
        
    @Denon.add_feature
    class Mdmi(Zone, SelectFeature):
        name = "MDMI Out"
        id = "zone%s_mdmi"%zone
        function = "Z%sHDA "%zone
        call = "Z%sHDA?"%zone
        translation = {"THR":"THR", "PCM":"PCM"}
        
    @Denon.add_feature
    class ZSleep(Zone, Sleep):
        name = "Zone %s Sleep (min.)"%zone
        id = "zone%s_sleep"%zone
        function = "Z%sSLP"%zone
        
    @Denon.add_feature
    class AutoStandby(Zone, SelectFeature):
        name = "Zone %s Auto Standby"%zone
        id = "zone%s_auto_standby"%zone
        function = "Z%sSTBY"%zone
        translation = {"2H":"2 hours","4H":"4 hours","8H":"8 hours","OFF":"Off"}

