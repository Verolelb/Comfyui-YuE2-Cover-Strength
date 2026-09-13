# Comfyui-YuE2-Cover-Strength

Two ComfyUI custom nodes for YuE2:

- **YuE2 Cover Strength** — progressively dilutes an **ABC** score (coming from SheetSage2 or a plan) based on a strength value from 0 to 100%.
  - `0%` → almost no melody left (very free)
  - `100%` → score intact (native cover)
- **YuE2 Instrumental** — prepares a strictly instrumental YuE2 request (empty `lyrics`, de-voiced `style`, silenced sung voice in an optional ABC score). See [below](#yue2-instrumental-yue2instrumental).

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Verolelb/Comfyui-YuE2-Cover-Strength.git
```

Restart ComfyUI. Both nodes show up under the `YuE2/Utils` category.

## Node

### `YuE2 Cover Strength` (`YuE2CoverStrength`)

Inputs:

| Input | Type | Default | Description |
| --- | --- | --- | --- |
| `abc` | STRING (multiline) | `` (empty) | Raw ABC score — wired from SheetSage2, or pasted directly |
| `strength` | FLOAT (0–100) | `100.0` | `0` = very free, `100` = faithful cover |
| `mode` | `notes` / `notes+structure` / `aggressive` | `notes` | Dilution level |
| `seed` | INT | `0` | Random dilution seed (`0` = random) |
| `keep_vocal_only` | BOOLEAN | `False` | Keep the `Vocal` voice only, turn `Ins` into rests |

Outputs:

- `abc_diluted` — the diluted ABC score
- `info` — summary of the operation (strength, mode, effective `kept`, seed)

### `YuE2 Instrumental` (`YuE2Instrumental`)

Prepares a **strictly instrumental** YuE2 request. It loads no model and calls no
model API: it only builds the strings you wire into the YuE2 node you already use
(`Compose`, `Generate Plan`, `Song Generator`, or the `yue2` package).

YuE2 has no "instrumental" switch. Three things are needed, and the node does all three:

1. `lyrics` must be **empty** — not `[Instrumental]`, not a section tag without
   words. The node always outputs an empty `lyrics` string.
2. `style` must describe genre / instruments / tempo **without vocal
   descriptors**, otherwise the model still adds a voice.
3. If an ABC score is supplied, its sung voice must be silenced, otherwise YuE2
   sings the melody it was given even with empty lyrics.

Inputs:

| Input | Type | Default | Description |
| --- | --- | --- | --- |
| `style` | STRING (multiline) | `cinematic, piano, strings, instrumental` | Style/genre prompt, instrumentalized on the way out |
| `lyrics` | STRING (multiline) | `` (empty) | Lyrics to neutralize — they are counted, then dropped |
| `abc` | STRING (multiline) | `` (empty) | Optional ABC score (SheetSage2, piano roll...) |
| `remove_vocal_terms` | BOOLEAN | `True` | Strips vocal words from `style` (`female vocal`, `singer`, `choir`...) |
| `add_instrumental_tag` | BOOLEAN | `True` | Guarantees `instrumental` appears in `style` |

Outputs:

- `style` — style prompt with the vocal descriptors removed and `instrumental` added
- `lyrics` — always empty, this is what makes YuE2 instrumental
- `abc` — score where the `Vocal` voice became rests (chords and the `Ins` voice kept)
- `info` — what was removed, dropped and cleared (also shown directly on the node)

Wiring notes:

- **Leave `abc` unconnected when you have no score.** The output then stays empty,
  which is what you want: a supplied score bypasses YuE2's symbolic planner. With
  an empty `abc` and empty `lyrics`, YuE2 plans its own melody and chords, without
  a voice. No ABC is required to get instrumental music.
- `lyrics` plugged into a Display Any will look empty — that is the point.
- `abc` only carries a score when a score is wired into its input (SheetSage2, a
  piano roll, or the Cover Strength node), which is the only case where the sung
  voice has to be silenced.

How the score is handled:

- Notes and chords of the `Vocal` voice become rests of the same length, so the bar
  grid is unchanged.
- Native chord symbols (`"Am7"`) are kept: in YuE2's ABC they carry the harmony of
  the vocal part and must survive even when the voice rests.
- The `Ins` voice (instrumental theme), comments (`% verse`), the header and inline
  fields (`[K:G]`) are copied untouched.
- `w:` lyric lines of the vocal voice are dropped, and ties are removed from rests
  (`z8-z8` is invalid ABC; `z8z8` keeps the same duration).
- A score with no `V:` labels is returned as-is — the node never guesses which part
  is sung.

## Modes

- **`notes`** — erases notes only. Each erased note becomes a rest of the same
  length, so the bar structure and the rhythm stay valid.
- **`notes+structure`** — also erases part of the sections (`verse`, `chorus`,
  `bridge`, `interlude`, `intro`, `outro`) once strength drops below 85%.
- **`aggressive`** — dilution pushed one third further, plus real pitch noise:
  some of the surviving notes are transposed by ±1 semitone (twice as often)
  or ±2. Chords are transposed as a whole so their intervals are preserved, and
  the accidentals follow the key signature (`K:`).

Notes and chords are always handled as whole units: a chord is either kept or
replaced by a rest, never half-diluted. Voice lines, lyrics (`w:`), inline
fields (`[K:G]`) and comments are left untouched.

The two `aggressive` cursors can be tuned at the top of the class:
`AGGRESSIVE_DILUTION_BOOST` and `AGGRESSIVE_NOISE`.

## Widget values

- A freshly added node defaults to `strength = 100` and `mode = notes`.
- Values you edit are stored in the workflow, so they come back when you reopen
  it or switch to another workflow and back.
- If `strength` or `mode` ever arrives missing, `NaN` or out of range, the node
  falls back to those same safe defaults instead of erroring out.

## Tests

No dependency to install, the suite uses the standard library `unittest`:

```bash
python -m unittest discover -s tests -v
```

It covers the input guards, the dilution rules, chord handling and the pitch
logic, plus the instrumental node (style cleanup, blank lyrics, vocal voice
silencing). It never touches ComfyUI.

## License

Not defined.
