import argparse, os, sys, time, re, ast, traceback, shutil
from code import InteractiveConsole
from threading import Thread
from itertools import groupby
from textwrap import TextWrapper
from contextlib import suppress
from decimal import Decimal
from . import Target, get_schemes, PKG_NAME, VERSION, COPYRIGHT
from .core import features
try: import readline
except ImportError: pass


bashcol = lambda s, *codes: f"\033[%sm{s}\033[0m"%(';'.join(map(str, codes))) if sys.platform == "linux" else s
bright = lambda s: bashcol(s, 1)
dim = lambda s: bashcol(s, 1, 2)
colour = lambda s: bashcol(s, 38, 5, 153)


class CLI:
    
    def __init__(self):
        parser = argparse.ArgumentParser(description='HIFI SHELL')
        parser.add_argument("--help-schemes", action="store_true", help="show list of supported schemes and exit")
        parser.add_argument("--help-features", metavar="SCHEME", action="store", const=1, nargs="?", help="show target's feature variables and exit")
        parser.add_argument('-t', '--target', metavar="URI", type=str, default=None, help='Target URI')
        group = parser.add_mutually_exclusive_group(required=False)
        group.add_argument('-f','--follow', default=False, action="store_true", help='Monitor received messages')
        group.add_argument("file", metavar="HIFI FILE", type=str, nargs="?", help='Run hifi script')
        group.add_argument('--return', dest="ret", type=str, metavar="CMD", default=None, help='Return line that starts with CMD')
        group.add_argument('-x','--exit', default=False, action="store_true", help='Skip prompt. Useful if -t contains a query')

        parser.add_argument("-c", "--command", default=[], metavar="CMD", nargs="+", help='Execute commands')
        parser.add_argument('-q', '--quiet', action='store_true', default=False, help='Less output')
        parser.add_argument('--verbose', '-v', action='count', default=0, help='Verbose mode')
        self.args = parser.parse_args()
        assert(not (self.args.ret and self.args.follow))
        assert(self.args.command or not self.args.ret)
        
    def __call__(self):
        if self.args.help_schemes: return self.print_help_schemes()
        self.target = Target(self.args.target, verbose=self.args.verbose)
        if self.args.help_features:
            if self.args.help_features != 1:
                self.target = Target(f"emulate:{self.args.help_features}")
            return self.print_help_features()
        matches = (lambda cmd:cmd.startswith(self.args.ret)) if self.args.ret else None
        if len(self.args.command) == 0 and not self.args.file and not self.args.exit: self.print_header()
        if self.args.follow: self.target.bind(on_receive_raw_data=self.receive)
        with self.target:
            self.compiler = Compiler(
                # environment variables for hifish
                __query__ = self.query,
                __return__ = matches,
                __wait__ = .1,
                Decimal = Decimal,
                target = self.target,
                features = FeaturesProperties(self.target),
                help = self.print_help,
                help_features = self.print_help_features,
            )
            for cmd in self.args.command: self.compiler.run(cmd)
            if self.args.file: self.parse_file()
            if not self.args.exit and (not self.args.file and not self.args.command or self.args.follow):
                self.prompt()
    
    def query(self, cmd, matches, wait):
        """ calling $"cmd" or $'cmd' from within hifish. @matches comes from --return """
        r = self.target.query(cmd, matches)
        if wait: time.sleep(wait)
        return r
        
    def print_header(self):
        print(bright("$_ HIFI SHELL %s"%VERSION))
        print(COPYRIGHT)
        print("To get started, write help()\n")

    def prompt(self):
        self.target.bind(on_disconnected=self.on_disconnected)
        uri = ":".join(map(colour, self.target.uri.split(":")))
        ic = InteractiveHifish(
            prompt=f"{uri} > ", compiler=self.compiler, locals=self.compiler.env)
        ic.interact(banner="", exitmsg="")

    def parse_file(self):
        if not self.args.quiet: self.target.verbose += 3
        with open(self.args.file) as fp:
            self.compiler.run(fp.read(),self.args.file,"exec")
            
    def print_help(self):
        help = [
            ("Internal functions:", [
                ("help()","Show help"),
                ("help_features()", "Show features list"),
                ("wait(seconds)","Sleep given amount of seconds"),
                ("exit()","Quit")]),
            ("High level functions (scheme independent)", [
                ("$feature", "Variable that contains target's attribute, potentially read and writeable"),
                ("To see a list of features, type help_features()","")]),
            ("Low level functions (scheme dependent)",
                [("CMD or $'CMD'", "Send CMD to the target and return answer")])
        ]
        tw = TextWrapper(
            initial_indent=" "*4, subsequent_indent=" "*(20+4), width=shutil.get_terminal_size().columns)
        for header, l in help:
            print(bright(header.upper()))
            for e in l: print(tw.fill("%-20s%s"%e))
            print()

    def print_help_schemes(self):
        tw = TextWrapper(
            initial_indent=" "*4, subsequent_indent=" "*8, width=shutil.get_terminal_size().columns)
        print(f"A scheme defines a class that extends {PKG_NAME}.core.transmission.AbstractScheme.")
        print("The following schemes are being supported internally:")
        print()
        for S in get_schemes():
            print(bright(S.get_title()))
            if isinstance(S.description, str): print(tw.fill(f"{S.description}"))
            if uri := S.get_client_uri(): print(tw.fill(f"URI (Client): {uri}"))
            if uri := S.get_server_uri(): print(tw.fill(f"URI (Server): {uri}"))
            print()
            #print(tw.fill("%-20s%-20s%s"%(bright(p), S.scheme_id, getattr(S, "help", ""))))

    def print_help_features(self):
        tw = TextWrapper(
            initial_indent=" "*8, subsequent_indent=" "*12, width=shutil.get_terminal_size().columns)
        print(f"Scheme '{self.target.scheme_id}' supports the following features.\n")
        features_ = map(self.target.features.get, self.target.__class__.features.keys())
        features_ = sorted(features_, key=lambda f: (f.category, f.id))
        for category, ff in groupby(features_, key=lambda f:f.category):
            print(bright(category.upper()))
            for f in ff:
                print(bright(f"    ${f.id}"))
                s = f"{(f.name)}  {(f.type.__name__)}  "
                if isinstance(f,features.NumericFeature):
                    s += f"[{f.min}..{f.max}]"
                elif isinstance(f,features.SelectFeature):
                    s += str(f.options)
                print(tw.fill(s))
            print()
    
    def receive(self, data): print(data)
    
    def on_disconnected(self):
        print("\nConnection closed", file=sys.stderr)
        # quit InteractiveConsole
        try: os.system('stty sane')
        except: pass
        os._exit(1)


class CommandTransformation(ast.NodeTransformer):
    """ transformer for the parsed python syntax tree """
    
    def __init__(self, preprocessor):
        super().__init__()
        self.preprocessor = preprocessor
        
    def _query_call(self, cmd):
        """ returns __query__(@cmd, __return__, __wait__) """
        node = ast.Call(
            func=ast.Name(id="__query__", ctx=ast.Load()),
            args=[
                ast.Str(self.preprocessor.unserialize(cmd),ctx=ast.Load()),
                ast.Name(id="__return__",ctx=ast.Load()),
                ast.Name(id="__wait__",ctx=ast.Load()),
            ],
            keywords=[],
            ctx=ast.Load())
        self.generic_visit(node)
        return node
     
    def visit_Expr(self, node):
        """ handle commands outside of $, like MVUP;MVUP; """
        if isinstance(node.value, ast.Name): node.value = self._query_call(node.value.id)
        self.generic_visit(node)
        return node
        
    def _visit_Str(self, node, value):
        """ handle $'cmd' """
        for r,o in (dict(self.preprocessor.replace)["$'"], dict(self.preprocessor.replace)['$"']):
            if value.startswith(o): return self._query_call(value.replace(o,"",1))
        return node
            
    def visit_Constant(self, node): return self._visit_Str(node, node.value) if isinstance(node.value, str) else node
        
    def visit_Str(self, node): return self._visit_Str(node, node.s)
    
    def visit(self, node):
        r = super().visit(node)
        # undo preprocessing
        if isinstance(node, ast.Name): node.id = self.preprocessor.unserialize(node.id)
        elif isinstance(node, ast.ClassDef): node.name = self.preprocessor.unserialize(node.name)
        elif isinstance(node, ast.keyword): node.arg = self.preprocessor.unserialize(node.arg)
        elif isinstance(node, ast.AsyncFunctionDef): node.name = self.preprocessor.unserialize(node.name)
        elif isinstance(node, ast.FunctionDef): node.name = self.preprocessor.unserialize(node.name)
        elif isinstance(node, ast.arg): node.arg = self.preprocessor.unserialize(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str): node.value = self.preprocessor.unserialize(node.value)
        elif isinstance(node, ast.Str): node.s = self.preprocessor.unserialize(node.s)
        return r


class FeaturesProperties:

    def __init__(self, target):
        super().__setattr__("_target", target)

    def __dir__(self): return self._target.features.keys()

    def __getattr__(self, name):
        try: return self._target.features[name].get_wait()
        except KeyError as e: raise AttributeError(e)

    def __setattr__(self, name, value):
        try: f = self._target.features[name]
        except KeyError as e: raise AttributeError(e)
        self._target.set_feature_value(f, value)


class Preprocessor:
    """ Taking care of syntax that might be incompatible with the python parser
    like $ or ? outside of strings """
    
    replace = [
        #str,   replace,            ocurrance in string after parsing
        ("?",   ("__quest__",       "__quest__")),
        ("$'",  ("'__dollar1__",    "__dollar1__")),
        ('$"',  ('"__dollar2__',    "__dollar2__")),
        ("$",   ("features.",       "features.")),
    ]
    
    def __init__(self, source):
        self.source = source
        def find_unique(r, o):
            if o in source: return find_unique("%s1"%r, "%s1"%o)
            else: return r,o
        self.replace = [(s,find_unique(r,o)) for s,(r,o) in self.replace]
    
    def serialize(self):
        source = self.source
        for s,(repl,find) in self.replace: source = source.replace(s,repl)
        return source
        
    def unserialize(self, data):
        for s,(repl,find) in self.replace: data = data.replace(repl,s)
        return data


class Compiler(Preprocessor):

    def __init__(self, **env): 
        self.env = dict(**env, wait=time.sleep, __name__="__main__")

    def compile(self, source, filename, mode):
        preprocessor = Preprocessor(source)
        source_p = preprocessor.serialize()
        tree = ast.parse(source_p, mode=mode)
        tree = CommandTransformation(preprocessor).visit(tree)
        tree = ast.fix_missing_locations(tree)
        #print(ast.dump(tree))
        return compile(tree, filename=filename, mode=mode)

    __call__ = compile
    
    def run(self, source, filename="<input>", mode="single"):
        exec(self(source, filename, mode), self.env)
        
    
class InteractiveHifish(InteractiveConsole):
    
    def __init__(self, *args, compiler=None, prompt=None, **xargs):
        super().__init__(*args,**xargs)
        if compiler: self.compile.compiler = compiler
        if prompt: sys.ps1 = prompt


main = lambda:CLI()()
if __name__ == "__main__":
    main()

