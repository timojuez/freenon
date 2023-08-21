"""
    Registering an own scheme and running HiFiSh. Call this script e.g. with
    "--help-schemes" or "--target emulate:myscheme" and change $value to any number
    to see that it works!
"""

from decimal import Decimal
from hificon.core import SocketScheme, shared_vars
from hificon import register_scheme, hifish


class MySocketScheme(SocketScheme):
    """ try by running `examples$ python3 -m hificon.hifish -t emulate:my_scheme.MySocketScheme`
    or start the server by `examples$ python3 -m hificon.server -t my_scheme.MySocketScheme://127.0.0.1:1234`
    and start the client by `examples$ python3 -m hificon.hifish -t my_scheme.MySocketScheme://127.0.0.1:1234`
    """
    description = "My custom scheme"


@MySocketScheme.shared_var(overwrite=True)
class Power(shared_vars.BoolVar):
    call = "?pwr"

    def serialize(self, value): return "!pwr=1" if value else "!pwr=0"
    def unserialize(self, data): return data == "!pwr=1"
    def matches(self, data): return data.startswith("!pwr")
    def poll_on_server(self): self.set(True)
    def set_on_server(self, value): self.set(value)


@MySocketScheme.shared_var
class Value(shared_vars.DecimalVar):
    min = 0
    max = 10
    call = "get value"
    
    def serialize(self, value): return "set value %0.2f"%value
    def unserialize(self, data): return Decimal(data.rsplit(" ",1)[1])
    def matches(self, data): return data.startswith("set value")
    def set_on_server(self, value): self.set(value)
    def poll_on_server(self): self.set(5)


if __name__ == "__main__":
    register_scheme("myscheme", MySocketScheme)
    hifish.main()

