#!/usr/bin/env python3

'''
UI backend abstraction.

The rest of pyren interacts with the user through a single backend object
stored in mod_globals.ui. TerminalUIBackend preserves the original
print()/input() behavior. Alternate backends (e.g. Toga for iOS) can be
plugged in without touching diagnostic logic.

For legacy code that writes via bare print() / sys.stdout / input(), a
backend may call install_stdio_capture() to redirect those calls into
its own writeln() / ask() methods without touching business logic.
'''

import builtins
import sys
import mod_globals


class UIBackend(object):
    def clear(self):
        raise NotImplementedError

    def write(self, text):
        raise NotImplementedError

    def writeln(self, text=""):
        raise NotImplementedError

    def ask(self, prompt=""):
        raise NotImplementedError

    def choose(self, items, question):
        raise NotImplementedError

    def choose_long(self, items, question, header=""):
        raise NotImplementedError

    def choose_from_dict(self, mapping, question, show_id=True):
        raise NotImplementedError


class _StdoutRedirect(object):
    '''File-like object that buffers by line and forwards to backend.

    Emits a writeln() to the backend for each complete line; keeps a
    partial trailing fragment in self._buf until a newline arrives.
    '''
    def __init__(self, backend):
        self._backend = backend
        self._buf = ""
        self.encoding = "utf-8"

    def write(self, data):
        if not data:
            return 0
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._backend.writeln(line)
        return len(data)

    def flush(self):
        if self._buf:
            self._backend.write(self._buf)
            self._buf = ""

    def isatty(self):
        return False


class TerminalUIBackend(UIBackend):
    def clear(self):
        sys.stdout.write(chr(27) + "[2J" + chr(27) + "[;H")

    def write(self, text):
        sys.stdout.write(text)

    def writeln(self, text=""):
        print(text)

    def ask(self, prompt=""):
        try:
            return input(prompt)
        except (KeyboardInterrupt, SystemExit):
            print()
            print()
            sys.exit()

    def choose(self, items, question):
        d = {}
        c = 1
        for s in items:
            if s.lower() == '<up>' or s.lower() == '<exit>':
                print("%-2s - %s" % ('Q', s))
                d['Q'] = s
            else:
                print("%-2s - %s" % (c, s))
                d[str(c)] = s
            c += 1

        while True:
            ch = self.ask(question)
            if ch == 'q':
                ch = 'Q'
            if ch == 'cmd':
                mod_globals.opt_cmd = True
            if ch in d:
                return [d[ch], ch]

    def choose_long(self, items, question, header=""):
        d = {}
        c = 1
        page = 0
        page_size = 20

        for s in items:
            if s.lower() == '<up>' or s.lower() == '<exit>':
                d['Q'] = s
            else:
                d[str(c)] = s
            c += 1

        while True:
            self.clear()
            if header:
                print(header)

            c = page * page_size
            for s in items[page * page_size:(page + 1) * page_size]:
                c += 1
                if s.lower() == '<up>' or s.lower() == '<exit>':
                    print("%-2s - %s" % ('Q', s))
                else:
                    print("%-2s - %s" % (c, s))

            if len(items) > page_size:
                if page > 0:
                    print("%-2s - %s" % ('P', '<prev page>'))
                if (page + 1) * page_size < len(items):
                    print("%-2s - %s" % ('N', '<next page>'))

            while True:
                ch = self.ask(question)
                if ch == 'q':
                    ch = 'Q'
                if ch == 'p':
                    ch = 'P'
                if ch == 'n':
                    ch = 'N'
                if ch == 'N' and (page + 1) * page_size < len(items):
                    page += 1
                    break
                if ch == 'P' and page > 0:
                    page -= 1
                    break
                if ch == 'cmd':
                    mod_globals.opt_cmd = True
                if ch in d:
                    return [d[ch], ch]

    def choose_from_dict(self, mapping, question, show_id=True):
        d = {}
        c = 1
        for k in sorted(mapping.keys()):
            s = mapping[k]
            if k.lower() == '<up>' or k.lower() == '<exit>':
                print("%s - %s" % ('Q', s))
                d['Q'] = k
            else:
                if show_id:
                    print("%s - (%s) %s" % (c, k, s))
                else:
                    print("%s - %s" % (c, s))
                d[str(c)] = k
            c += 1

        while True:
            ch = self.ask(question)
            if ch == 'q':
                ch = 'Q'
            if ch in d:
                return [d[ch], ch]


_saved_stdout = None
_saved_input = None


def install_stdio_capture(backend):
    '''Redirect print() and input() to the given backend.

    Intended for non-terminal backends (Toga/iOS) so existing code that
    uses bare print() / input() still works without modification.
    '''
    global _saved_stdout, _saved_input
    if _saved_stdout is None:
        _saved_stdout = sys.stdout
        sys.stdout = _StdoutRedirect(backend)
    if _saved_input is None:
        _saved_input = builtins.input
        builtins.input = lambda prompt="": backend.ask(prompt)


def uninstall_stdio_capture():
    global _saved_stdout, _saved_input
    if _saved_stdout is not None:
        sys.stdout = _saved_stdout
        _saved_stdout = None
    if _saved_input is not None:
        builtins.input = _saved_input
        _saved_input = None


def init_default():
    if getattr(mod_globals, 'ui', None) is None:
        mod_globals.ui = TerminalUIBackend()


init_default()

