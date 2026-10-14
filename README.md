# Maths Shorts Studio

Type a topic, get a narrated 9:16 maths short in the Maths in the Wild style.

```
topic ─► Gemini + Google Search ─► research notes + sources
      ─► Gemini ─► 4-beat script (hook · setup · maths · payoff)  ◄── you check and edit it
      ─► edge-tts ─► narration, one clip per beat (gives exact beat timings)
      ─► Gemini ─► Manim scene ─► render ─► error? send it back to Gemini (up to N times)
                                          └─► still failing? template scene (always renders)
      ─► ffmpeg ─► final.mp4 + captions.srt + scene.py
```

## Setup (once)

1. Install **Python 3.12** from python.org (tick "Add python.exe to PATH" on Windows).
2. Get a free Gemini API key at <https://aistudio.google.com/apikey>.
   Copy `.env.example` to `.env` and paste the key after `GEMINI_API_KEY=`, or paste it in the app's sidebar.
3. **Optional but recommended — LaTeX**, so formulas render as real maths:
   - Windows: install [MiKTeX](https://miktex.org/download); in MiKTeX Console, set "install missing packages on the fly" to *Yes*.
   - macOS: `brew install --cask mactex-no-gui`
   - Ubuntu: `sudo apt install texlive texlive-latex-extra dvisvgm`
   Without LaTeX, formulas show as plain text. The sidebar tells you which you have.
4. Linux only: Manim needs Pango and Cairo: `sudo apt install libpango1.0-dev libcairo2-dev pkg-config`.

## Run the website

- Windows: double-click `run_website_windows.bat`
- macOS / Linux: `./run_website_mac_linux.sh`

The first run installs everything into `.venv` (a few minutes). The website then opens in your browser at
<http://localhost:8000>. Keep the black server window open while you use it; close it to stop.

Add your Gemini key with the ⚙ Settings button (it is saved to `.env` on your computer).

**Try it first without a key:** switch on *Demo mode*, click *Research & write script*, then *Make video*.
That renders the UPI pay-later short and checks that voice, Manim and ffmpeg all work.

The website has three steps (Topic → (optional) Check the script → Video) and a Library of everything you've
made. Your last script is kept in the browser, so a page refresh doesn't lose your edits.

The older Streamlit version still works: `run_windows.bat` / `./run_mac_linux.sh` (port 8501).

## Making a short

**One click (default):** type just the topic, e.g. `Eigenvalues`, and press **Make video**. The studio
researches it on the web, writes the script, runs an automatic fact-check (Gemini recomputes every number and
fixes errors), records the voice, animates it and mixes the MP4. When it's done, open **What was checked** to
see the corrections, every number used and the web sources. To change anything, press **Edit script & re-make**.

Language, length, voice and quality are under **Options** and are remembered for next time.

**With a review step:** tick *Let me check the script before the video is made*. Then:

1. Enter a topic (or tap an idea), pick the language (English, Hinglish, Hindi), length, audience and voice.
2. **Research & write script.** Read the yellow *Check these before rendering* box: it lists every number
   and claim in the script. Fix anything wrong directly in the beat boxes; formulas preview live.
3. **Make video.** Pick Draft (540×960, about a minute) or Final (1080×1920, 2–3 minutes) under *Video options*.
   The page shows each stage live. Only one video renders at a time; others wait in a queue.
4. Download the MP4, the SRT captions (upload them to YouTube) and the Manim scene, or copy the description.

Every short is saved in `outputs/<date>-<title>/` with `script.json`, `narration.wav`, `scene.py`,
all failed attempts and their errors, and `log.txt`.

### Editing the animation by hand
Edit `outputs/<job>/scene.py`, then:
```
python make_short.py --rerender outputs/<job> --quality final
```
The narration stays the same; only the picture is re-rendered.

### Command line
```
python make_short.py "SIP: why 5,000 a month becomes crores" --lang Hinglish --quality final
python make_short.py --demo
```

## Language notes
- **Hinglish / Hindi:** narration is written in Devanagari (English technical words stay in Latin script) and
  read by a Hindi neural voice. On-screen text stays in English and maths notation.
- Voices are free Microsoft Edge neural voices via `edge-tts`. They need an internet connection.

## Good to know
- **Check the maths.** Gemini's research is grounded in Google Search, and sources are listed, but AI can
  still get a number wrong. The review step is there for that.
- **Generated code safety.** Gemini's scene code runs on your computer. Before rendering, the studio rejects
  code that imports anything except manim/numpy/math, opens files, or touches the network or OS.
- **Free-tier limits.** One short uses roughly 3–6 Gemini calls (research, script, 1–4 animation attempts).
- If animations often fall back to the template, set *Model for animation code* to a Pro model
  (e.g. `gemini-3.1-pro-preview`), or make the *Animation idea* boxes simpler and more concrete.

## Files
| File | What it does |
|---|---|
| `server/main.py`, `web/` | The website: FastAPI backend and the 3-step page |
| `run_website.py` | Starts the website and opens the browser |
| `app.py` | The older Streamlit studio |
| `make_short.py` | Command-line version and `--rerender` |
| `studio/research.py` | Research and script prompts |
| `studio/scene_gen.py` | Animation prompt, safety check, render, repair loop |
| `studio/preamble.py` | 9:16 frame, palette, beat timings and helpers shared by every scene |
| `studio/fallback_scene.py` | Template scene used when Gemini's scene can't render |
| `studio/tts.py`, `studio/assemble.py` | Voice, captions, final mixing |
| `studio/demo.py` | Demo script and scene |

## Author & Portfolio
Created by [mdsamhussain1996](https://mdsamhussain1996.github.io/) — visit my [Portfolio](https://mdsamhussain1996.github.io/) for more interactive maths, research, and AI platforms.
