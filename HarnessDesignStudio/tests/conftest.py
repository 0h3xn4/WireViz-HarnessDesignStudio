import atexit
import os
import shutil
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Safety net: a test that builds the editor with the default settings must not read or write the
# developer's own ~/.config (first-run tour, window geometry). Qt resolves the per-user ini
# folder from XDG_CONFIG_HOME on Linux.
_CONFIG_HOME = tempfile.mkdtemp(prefix="harness-tests-config-")
os.environ["XDG_CONFIG_HOME"] = _CONFIG_HOME
atexit.register(shutil.rmtree, _CONFIG_HOME, ignore_errors=True)

# Every process (the one that runs pytest and each pytest-xdist worker) imports this file and so has
# its own folder, which keeps parallel workers from sharing one settings file. A worker ends without
# running the atexit hook, so the folder is removed when pytest unconfigures as well.


def pytest_unconfigure(config: object) -> None:
    shutil.rmtree(_CONFIG_HOME, ignore_errors=True)
