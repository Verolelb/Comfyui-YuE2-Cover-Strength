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
| `abc` | STRING (multiline, forceInput) | — | Raw ABC score |
| `strength` | FLOAT (0–100) | `100.0` | `0` = very free, `100` = faithful cover |
| `mode` | `notes` / `notes+structure` / `aggressive` | `notes` | Dilution level |
| `seed` | INT | `0` | Random dilution seed (`0` = random) |
| `keep_vocal_only` | BOOLEAN | `False` | Keep the `Vocal` voice only, turn `Ins` into rests |

Outputs:

- `abc_diluted` — the diluted ABC score
- `info` — summary of the operation (strength, mode, seed)

## Modes

- **`notes`** — erases notes only (each one replaced by a rest of roughly matching duration).
- **`notes+structure`** — also erases part of the sections (`verse`, `chorus`, `bridge`, `interlude`, `intro`, `outro`) once strength drops below 85%.
- **`aggressive`** — stronger dilution, plus random pitch noise.

## License

Not defined.
