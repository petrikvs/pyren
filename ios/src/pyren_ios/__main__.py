# iOS simulator / device return a locale string that Python's locale
# module cannot resolve; Toga unconditionally calls
# locale.setlocale(LC_ALL, "") in App.__init__, which raises
# locale.Error and kills the app before startup(). Guard it here before
# Toga is imported.
import locale as _locale
import os as _os

_os.environ.setdefault("LANG", "en_US.UTF-8")
_os.environ.setdefault("LC_ALL", "en_US.UTF-8")

_orig_setlocale = _locale.setlocale


def _safe_setlocale(category, loc=None):
    try:
        return _orig_setlocale(category, loc)
    except _locale.Error:
        try:
            return _orig_setlocale(category, "C")
        except _locale.Error:
            return None


_locale.setlocale = _safe_setlocale

from pyren_ios import main

if __name__ == "__main__":
    main().main_loop()
