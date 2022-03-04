import sys


def _skip_on_windows():
    if sys.platform.startswith("win"):
        return True

    return False


skip_on_windows = _skip_on_windows()
SKIP_ON_WINDOWS_REASON = "These tests are skipped on Windows"
