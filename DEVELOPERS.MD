# Technical Information

## Run from source

```bash
uv sync
uv run python -m pompom

# or
python pompom.py
```

Settings persist as a plain-text INI file at
`%APPDATA%\pompom\pompom.ini`.
When enabled from a source run, **Start with Windows** depends on that Python
environment remaining at the same path.

## Build the app folder

```bash
uv run pyinstaller --noconfirm --clean pompom.spec
```

Output is in `dist/pompom/`.

## Build the Windows installer

Install [Inno Setup 7](https://jrsoftware.org/isinfo.php), then run:

```powershell
.\scripts\build_installer.ps1
```

The script finds `ISCC.exe` on `PATH` or in standard install locations. For a
custom location, set `ISCC_PATH` to the full compiler path first.

The script builds the PyInstaller app first, then writes the installer to
`dist/installer/pompom-1.0.0-setup.exe`.