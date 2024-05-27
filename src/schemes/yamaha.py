from decimal import Decimal
from ..core import shared_vars, SocketScheme
from ..core.transmission.types import ClientType, ServerType

ZONES = [
    # command, id_prefix, name
    ("MAIN", "", "Main Zone"),
    ("ZONE2", "zone2_", "Zone 2"),
]


class Yamaha(SocketScheme):
    description = "Yamaha AVR compatible"
    _pulse = "@MAIN:PWR=?"

    @classmethod
    def new_client_by_ssdp(cls, response, *args, **xargs):
        if "yamaha" in response.st.lower():
            host = urlparse(response.location).hostname
            port = 5000
            return cls.new_client(host, port, *args, **xargs)


class _YamahaVar:
    """ Handles Yamaha format "@ZONE:CMD=value" """
    
    zone = "MAIN" #str
    function = None #str
    call = property(lambda self: self._to_code("?"))

    def _to_code(self, value): return f"@{self.zone}:{self.function}={value}"
    
    def matches(self, cmd):
        return cmd.startswith(self._to_code(""))

    def serialize(self, value):
        return [self._to_code(e) for e in super().serialize(value)]
    
    def unserialize(self, data):
        return super().unserialize(list(map(lambda code: code.split("=", 1)[-1], data)))


class _SelectVar(_YamahaVar, shared_vars.SelectVar): pass

class _Power(_YamahaVar, shared_vars.BoolVar):
    function="PWR"
    translation={"On":True, "Standby":False}

class _DecimalVar(_YamahaVar, shared_vars.DecimalVar):
    step = Decimal('.5')
    min = -6
    max = 6

    def serialize(self, val):
        return super().serialize("%0.1f"%val)

    def unserialize(self, data):
        return Decimal(super().unserialize(data))


class _BoolVar(_YamahaVar, shared_vars.BoolVar):
    translation = {"On":True, "Off":False}


@Yamaha.shared_var
class Power(_Power):
    zone="SYS"


for zone, zone_id, zone_name in ZONES:

    class Zone:
        zone=zone
        category=zone_name

    @Yamaha.shared_var
    class Power(Zone, _Power):
        id=f"{zone.lower()}_power"
    
    @Yamaha.shared_var
    class Volume(Zone, _DecimalVar):
        id=f"{zone_id}volume"
        function="VOL"
        min = Decimal("-80.5")
        max = Decimal("16.5")

    class _Mute(Zone):
        function="MUTE"

    @Yamaha.shared_var
    class MuteOption(_Mute, _SelectVar):
        id=f"{zone_id}mute_option"
        translation={"Off":"Off", "Att -40 dB": "-40 dB", "Att -20 dB": "-20 dB", "On": "On"}

    @Yamaha.shared_var
    class Mute(_Mute, _BoolVar):
        id=f"{zone_id}muted"
        
        def unserialize(self, data):
            return super().unserialize(data) == True

        def resend(self): return

    @Yamaha.shared_var
    class Input(Zone, _SelectVar):
        id=f"{zone_id}source"
        function="INP"
        translation={   'TUNER': 'Tuner',
                        'PHONO': 'Phono',
                        "HDMI1": "HDMI 1",
                        "HDMI2": "HDMI 2",
                        "HDMI3": "HDMI 3",
                        "HDMI4": "HDMI 4",
                        "HDMI5": "HDMI 5",
                        'AV1': 'AV 1',
                        'AV2': 'AV 2',
                        'AV3': 'AV 3',
                        'AV4': 'AV 4',
                        'AV5': 'AV 5',
                        'AV6': 'AV 6',
                        'V-AUX': 'V-AUX',
                        'AUDIO1': 'Audio 1',
                        'AUDIO2': 'Audio 2',
                        'DOCK': 'Dock',
                        'iPod': 'iPod',
                        'Bluetooth': 'Bluetooth',
                        'UAW': 'UAW',
                        'NET': 'Net',
                        'Napster': 'Napster',
                        'PC': 'PC',
                        'NET RADIO': 'Net Radio',
                        'iPod (USB)': 'iPod (USB)'}


@Yamaha.shared_var
class Scene(_SelectVar):
    function="SCENE"
    translation = {"Scene 1": "Scene 1", "Scene 2": "Scene 2", "Scene 3": "Scene 3", "Scene 4": "Scene 4"}

@Yamaha.shared_var
class Bass(_DecimalVar):
    function="SPBASS"

@Yamaha.shared_var
class Treble(_DecimalVar):
    function="SPTREBLE"

@Yamaha.shared_var
class PureDirectMode(_BoolVar):
    function="PUREDIRMODE"

@Yamaha.shared_var
class HdmiOut(_BoolVar):
    function="HDMIOUT"

@Yamaha.shared_var
class HdmiAudioOutAmp(_BoolVar):
    function="HDMIAUDOUTAMP"

@Yamaha.shared_var
class HdmiAudioOut1(_BoolVar):
    function="HDMIAUDOUT1"

@Yamaha.shared_var
class HdmiAspect(_SelectVar):
    function="HDMIASPECT"
    translation={"Through": "Through", "16:9 Normal": "16:9 Normal"}

@Yamaha.shared_var
class HeadphoneBass(_DecimalVar):
    function="HPBASS"

@Yamaha.shared_var
class HeadphoneTreble(_DecimalVar):
    function="HPTREBLE"

@Yamaha.shared_var
class Cursor(shared_vars.ClientToServerVarMixin,_SelectVar):
    function="LISTCURSOR"
    translation={"Down":"Down", "Up":"Up", "Left":"Left", "Right":"Right", "Sel":"Select", "Back":"Back", "Back to Home":"Home"}

@Yamaha.shared_var
class Menu(shared_vars.ClientToServerVarMixin, _SelectVar):
    function="LISTMENU"
    translation={"On Screen":"On Screen", "Top Menu":"Top Menu", "Menu":"Menu", "Option":"Option"}

@Yamaha.shared_var(overwrite=True)
class Name(shared_vars.ServerToClientVarMixin, _SelectVar):
    default_value = "Yamaha"
    dummy_value = "Yamaha RX-V771 Dummy"
    zone = "SYS"
    function = "MODELNAME"

