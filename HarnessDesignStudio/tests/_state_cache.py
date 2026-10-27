"""Build an expensive starting state once per module and hand every test its own copy.

A generated and exported project, a released baseline: producing them takes seconds, and many tests
only need the finished state before they change something. The state is built once into a template
folder (`tmp_path_factory`, so no fixed path and one template per xdist worker) and each test gets
`copy_state(template, tmp_path / ...)`: a faithful copy (links kept as links, file modes and
modification times kept), so the test may change its copy freely. A test never touches the
template.
"""

import shutil
from pathlib import Path


def copy_state(template: Path, dest: Path) -> Path:
    """A faithful private copy of `template` at `dest` (which must not exist yet): symbolic links
    stay links (not followed), `copy2` keeps modes and modification times."""
    shutil.copytree(template, dest, symlinks=True, copy_function=shutil.copy2)
    return dest
