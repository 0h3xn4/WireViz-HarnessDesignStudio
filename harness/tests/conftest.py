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
