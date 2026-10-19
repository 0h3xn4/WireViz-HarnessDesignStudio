"""D-149: Qt on Windows cannot read WOFF2, so the Windows package carries TrueType copies of the
bundled fonts (packaging/fonts/) and gui/fonts.py falls back to them."""

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WOFF2 = ROOT / "src" / "harness_design_studio" / "resources" / "fonts"
TTF = ROOT / "packaging" / "fonts"


def _folder(tmp_path: Path, woff: int, ttf: int) -> Path:
    folder = tmp_path / "fonts"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir()
    for f in sorted(WOFF2.glob("*.woff2"))[:woff]:
        shutil.copy(f, folder)
    for f in sorted(TTF.glob("*.ttf"))[:ttf]:
        shutil.copy(f, folder)
    return folder


def test_the_truetype_fonts_load_when_qt_cannot_read_woff2(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtGui import QFontDatabase

    from harness_design_studio.gui import fonts

    real = QFontDatabase.addApplicationFont
    asked: list[str] = []

    def without_woff2(path: str) -> int:
        asked.append(Path(path).suffix)
        return -1 if path.endswith(".woff2") else real(path)

    folder = _folder(tmp_path, woff=1, ttf=6)
    monkeypatch.setattr(fonts, "fonts_path", lambda: folder)
    monkeypatch.setattr(fonts, "_loaded", None)
    monkeypatch.setattr(QFontDatabase, "addApplicationFont", staticmethod(without_woff2))
    assert {fonts.UI_FAMILY, fonts.MONO_FAMILY} <= set(fonts.load_fonts())
    assert ".woff2" in asked and ".ttf" in asked


def test_where_woff2_loads_the_truetype_files_stay_unused(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtGui import QFontDatabase

    from harness_design_studio.gui import fonts

    real = QFontDatabase.addApplicationFont
    asked: list[str] = []

    def counting(path: str) -> int:
        asked.append(Path(path).suffix)
        return real(path)

    folder = _folder(tmp_path, woff=6, ttf=1)
    monkeypatch.setattr(fonts, "fonts_path", lambda: folder)
    monkeypatch.setattr(fonts, "_loaded", None)
    monkeypatch.setattr(QFontDatabase, "addApplicationFont", staticmethod(counting))
    assert {fonts.UI_FAMILY, fonts.MONO_FAMILY} <= set(fonts.load_fonts())
    assert ".ttf" not in asked and asked.count(".woff2") == 6


def test_the_truetype_fonts_are_for_the_windows_package_only() -> None:
    import tomllib

    from tools import build_installer

    assert len(list(TTF.glob("*.ttf"))) == len(list(WOFF2.glob("*.woff2"))) == 6
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = pyproject["tool"]["setuptools"]["package-data"]["harness_design_studio.resources"]
    assert "fonts/*" in patterns and not list(WOFF2.glob("*.ttf"))  # not in the wheel
    assert "packaging" in " ".join(build_installer.ttf_fonts_args())
    # only the Windows build adds them: not the Linux build, the .deb or the macOS build
    main = (ROOT / "tools/build_installer.py").read_text(encoding="utf-8").split("def main()")[1]
    assert "ttf_fonts_args" not in main
    assert "ttf_fonts_args" not in (ROOT / "tools/build_deb.py").read_text(encoding="utf-8")
    assert "ttf_fonts_args()" in (ROOT / "tools/build_windows.py").read_text(encoding="utf-8")
    assert "ttf_fonts_args" not in (ROOT / "tools/build_macos.py").read_text(encoding="utf-8")
