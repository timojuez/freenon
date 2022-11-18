from ..core import features, SocketScheme


class Telnet(SocketScheme):
    """ Raw Data Low Level Target """
    description = "Reads data without further interpretation"
    
    def query(self, cmd, matches=None):
        """
        send @cmd to target and return line where matches(line) is True
        """
        if not matches: return self.send(cmd)
        class RawFeature(features.Feature):
            id = None
            call = cmd
            matches = lambda self, data: matches(data)
            def serialize(self, value): return value
            def unserialize(self, data): return data
        RawFeature.__name__ = cmd
        f = RawFeature(self)
        f.wait_poll(force=True)
        return f.get()

