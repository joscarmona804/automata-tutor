# Building a standalone Windows executable

You can package Automata Tutor into a single `.exe` that runs with **no Python
installed** on the target machine. This is handy for sharing with classmates
or friends who just want to play.

## Prerequisites

- Windows
- Python 3.10+
- PyInstaller (`pip install pyinstaller`, or `pip install -r requirements.txt`)

## The command

Run this from the project root:

```
pyinstaller --onefile --windowed --name AutomataTutor app.py
```

What the flags do:

- `--onefile` bundles everything into a single executable file.
- `--windowed` hides the console window (this is a GUI app, so no terminal
  should pop up behind it).
- `--name AutomataTutor` sets the output name.

## Where the output lands

After the build finishes you'll find:

```
dist/AutomataTutor.exe
```

That `dist/AutomataTutor.exe` is fully self-contained. Copy it to any Windows
machine and double-click to run — the target does not need Python, Tkinter, or
anything else installed.

PyInstaller also creates a `build/` folder and an `AutomataTutor.spec` file as
part of the process; those are intermediate artifacts and are safe to delete
or leave ignored by git.
