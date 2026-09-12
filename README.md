# Comfyui-YuE2-Cover-Strength

A ComfyUI custom node: **YuE2 Cover Strength**.

It progressively dilutes an **ABC** score (coming from SheetSage2 or a plan) based on a strength value from 0 to 100%.

- `0%` → almost no melody left (very free)
- `100%` → score intact (native cover)

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Verolelb/Comfyui-YuE2-Cover-Strength.git
```

Restart ComfyUI. The node shows up under the `YuE2/Utils` category.

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
logic. It never touches ComfyUI.

## License

Not defined.
