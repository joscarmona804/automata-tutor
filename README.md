# Automata Tutor

> Learn DFAs, NFAs, and regular expressions by playing — not just reading.

Automata Tutor is a desktop game that turns the core of automata theory into a
hands-on, level-by-level challenge. You draw machines on a canvas, write regular
expressions, run words through your constructions, and get step-by-step
explanations of *why* an answer works. It's built for students meeting finite
automata and regular languages for the first time, and it follows the structure
of Michael Sipser's *Introduction to the Theory of Computation*, Chapter 1.

## Features

- **Gamified, progressive levels** — problems are organized so concepts build on
  one another, from simple DFAs up to trickier NFAs and regular expressions.
- **XP, stars, and streaks** — earn points for correct solutions, collect stars,
  and keep a solving streak going to stay motivated.
- **Step-by-step explanations** — every problem comes with the underlying
  concept, a solving strategy, and contextual feedback on your attempt.
- **Interactive drawing canvas** — place states, add transitions, and mark
  start/accept states directly with the mouse, JFLAP-style.
- **Formal regular-expression engine** — RE answers are compiled with a real
  Thompson-construction NFA and graded, not pattern-matched by guesswork.
- **Simulation with narration** — feed a word to your automaton and watch it
  move state by state, with a note explaining each transition.
- **Themes** — switch between tasteful, high-contrast color palettes
  (Midnight, Solarized, Nord, and a readable Light theme).

## Screenshots

> _Coming soon._ Drop images in a `docs/` or `screenshots/` folder and link them
> here, for example:
>
> ```markdown
> ![Main window](screenshots/main.png)
> ![Simulation view](screenshots/simulate.png)
> ```

## Download (Windows, no Python needed)

Grab the latest `AutomataTutor.exe` from the
[**Releases page**](https://github.com/joscarmona804/automata-tutor/releases/latest)
and double-click it. Nothing to install — hand it straight to a friend.

## Run from source

Requirements:

- Python **3.10+**
- Standard library only — **Tkinter** ships with CPython, so there's nothing
  else to install.

Then:

```bash
python app.py
```

That's it. No virtual environment or package install is needed just to play.

## Build a standalone Windows `.exe`

Want to hand the game to someone who doesn't have Python? Package it with
[PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name AutomataTutor app.py
```

The result lands at `dist/AutomataTutor.exe` — a single self-contained file that
runs on any Windows machine with no Python installed. See
[`build_exe.md`](build_exe.md) for more detail.

## Project structure

| Module            | What it does                                                                 |
| ----------------- | ---------------------------------------------------------------------------- |
| `app.py`          | The Tkinter GUI: canvas, sidebar, explain panel, and all user interaction.   |
| `automaton.py`    | The automaton model and simulation engine (states, transitions, run a word). |
| `regex_engine.py` | A formal regular-expression matcher built on a Thompson-construction NFA.    |
| `quiz.py`         | The problem bank: prompts, target languages, hints, and grading.             |
| `game.py`         | Progression logic — levels, XP, stars, and streak tracking.                  |
| `theme.py`        | Pure-data color palettes (themes) with no rendering dependencies.            |

## Educational background

The content is grounded in Michael Sipser's *Introduction to the Theory of
Computation*, Chapter 1, which develops the theory of regular languages:

- **§1.1** — deterministic finite automata (DFAs) and the regular languages.
- **§1.2** — nondeterministic finite automata (NFAs), the subset construction,
  and the equivalence of DFAs and NFAs.
- **§1.3** — regular expressions, GNFAs, and converting between automata and
  expressions.

All explanations in the app and this repository are written in our own words.
We cite Sipser for attribution and to point learners to the standard treatment;
no text from the book is reproduced here.

## Contributing

Contributions are welcome! If you'd like to add problems, themes, or features:

1. Fork the repository and create a feature branch.
2. Keep the runtime standard-library only (Tkinter), so the game stays easy to
   run and package.
3. Make sure new reference answers are verified against their target language
   before opening a pull request.
4. Open a PR with a clear description of what you changed and why.

Bug reports and feature ideas are equally welcome — open an issue to start the
conversation.

## License

Released under the [MIT License](LICENSE). © 2026 joscarmona804.
