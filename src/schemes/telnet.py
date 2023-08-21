from ..core import shared_vars, SocketScheme


class Telnet(SocketScheme):
    """ Raw Data Low Level Target """
    description = "Reads data without further interpretation"
    
    def query(self, cmd, matches=None):
        """
        send @cmd to target and return line where matches(line) is True
        """
        if not matches: return self.send(cmd)
        class RawVar(shared_vars.SharedVar):
            id = None
            call = cmd
            matches = lambda self, data: matches(data)
            def serialize(self, value): return [value]
            def unserialize(self, data): return data[0]
        RawVar.__name__ = cmd
        var = RawVar(self)
        var.wait_poll(force=True)
        return var.get()

