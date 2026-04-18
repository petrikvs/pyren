#!/usr/bin/env python3

'''
UI backend abstraction.

The rest of pyren interacts with the user through a single backend object
stored in mod_globals.ui. TerminalUIBackend preserves the original
print()/input() behavior. Alternate backends (e.g. Toga for iOS) can be
plugged in without touching diagnostic logic.
'''

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


def init_default():
    if getattr(mod_globals, 'ui', None) is None:
        mod_globals.ui = TerminalUIBackend()


init_default()
