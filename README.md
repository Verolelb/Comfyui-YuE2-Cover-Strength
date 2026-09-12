# Comfyui-YuE2-Cover-Strength

Custom node ComfyUI : **YuE2 Cover Strength**.

Dilue progressivement un score **ABC** (provenant de SheetSage2 ou d'un plan) selon une force de 0 à 100 %.

- `0 %` → presque plus de mélodie (très libre)
- `100 %` → score intact (cover natif)

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Verolelb/Comfyui-YuE2-Cover-Strength.git
```

Redémarre ComfyUI. Le node apparaît dans la catégorie `YuE2/Utils`.

## Node

### `YuE2 Cover Strength` (`YuE2CoverStrength`)

Entrées :

| Entrée | Type | Défaut | Description |
| --- | --- | --- | --- |
| `abc` | STRING (multiline, forceInput) | — | Score ABC brut |
| `strength` | FLOAT (0–100) | `100.0` | `0` = très libre, `100` = cover fidèle |
| `mode` | `notes` / `notes+structure` / `aggressive` | `notes` | Niveau de dilution |
| `seed` | INT | `0` | Seed de la dilution aléatoire (`0` = aléatoire) |
| `keep_vocal_only` | BOOLEAN | `False` | Garde uniquement la voix `Vocal`, passe `Ins` en rests |

Sorties :

- `abc_diluted` : le score ABC dilué
- `info` : résumé de l'opération (force, mode, seed)

## Modes

- **`notes`** — efface seulement les notes (remplacées par des rests de durée approximative).
- **`notes+structure`** — efface aussi une partie des sections (`verse`, `chorus`, `bridge`, `interlude`, `intro`, `outro`) quand la force passe sous 85 %.
- **`aggressive`** — dilution plus forte, avec un bruit de hauteur aléatoire.

## Licence

Non définie.
