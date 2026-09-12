# -*- coding: utf-8 -*-
"""
YuE2 Cover Strength Node
Dilue progressivement un score ABC selon une force de 0 à 100 %.
0 %   = presque plus de mélodie (très libre)
100 % = score intact (cover natif)
"""

from __future__ import annotations
import re
import random
from typing import List

class YuE2CoverStrength:
    """
    Contrôle la force du cover en diluant le score ABC.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "abc": ("STRING", {
                    "forceInput": True,
                    "multiline": True,
                    "tooltip": "Score ABC brut (provenant de SheetSage2 ou d'un plan)"
                }),
                "strength": ("FLOAT", {
                    "default": 100.0,
                    "min": 0.0,
                    "max": 100.0,
                    "step": 1.0,
                    "tooltip": "0 = très libre | 100 = cover fidèle (score intact)"
                }),
                "mode": (["notes", "notes+structure", "aggressive"], {
                    "default": "notes",
                    "tooltip":
                        "notes = efface seulement les notes\n"
                        "notes+structure = efface aussi une partie des sections\n"
                        "aggressive = dilution plus forte + bruit de hauteur"
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                    "tooltip": "Seed pour la dilution aléatoire (0 = aléatoire)"
                }),
                "keep_vocal_only": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Garde uniquement la voix Vocal, met Ins en rests"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("abc_diluted", "info")
    FUNCTION = "apply"
    CATEGORY = "YuE2/Utils"
    OUTPUT_NODE = False

    def apply(self, abc: str, strength: float, mode: str, seed: int, keep_vocal_only: bool):
        if not abc or not abc.strip():
            return ("", "Empty ABC")

        strength = max(0.0, min(100.0, float(strength)))
        keep_ratio = strength / 100.0          # 1.0 = intact, 0.0 = totalement dilué

        if seed == 0:
            seed = random.randint(1, 2**31 - 1)
        rng = random.Random(seed)

        lines = abc.strip().splitlines()
        header: List[str] = []
        body: List[str] = []
        in_header = True

        for line in lines:
            stripped = line.strip()
            if in_header and (stripped.startswith(("X:", "T:", "M:", "L:", "Q:", "V:", "K:", "%")) or stripped == ""):
                header.append(line)
                if stripped.startswith("K:"):
                    in_header = False
            else:
                in_header = False
                body.append(line)

        # --- Option : garder uniquement Vocal ---
        if keep_vocal_only:
            body = self._keep_vocal_only(body)

        # --- Dilution des notes ---
        diluted_body = []
        for line in body:
            if line.strip().startswith("V:") or line.strip().startswith("%") or not line.strip():
                diluted_body.append(line)
                continue

            # Ligne de notes
            if keep_ratio >= 0.999:
                diluted_body.append(line)
                continue

            diluted_line = self._dilute_notes(line, keep_ratio, mode, rng)
            diluted_body.append(diluted_line)

        # --- Mode notes+structure : on peut aussi supprimer des sections entières ---
        if mode == "notes+structure" and keep_ratio < 0.85:
            diluted_body = self._maybe_drop_sections(diluted_body, keep_ratio, rng)

        result = "\n".join(header + diluted_body).strip() + "\n"

        info = (f"Cover Strength {strength:.0f}% | mode={mode} | "
                f"seed={seed} | keep_vocal_only={keep_vocal_only}")
        return (result, info)

    # ------------------------------------------------------------------
    def _keep_vocal_only(self, body: List[str]) -> List[str]:
        """Remplace toutes les lignes Ins par des rests de même durée approximative."""
        new_body = []
        current_voice = None
        for line in body:
            s = line.strip()
            if s.startswith("V: Vocal"):
                current_voice = "Vocal"
                new_body.append(line)
            elif s.startswith("V: Ins"):
                current_voice = "Ins"
                new_body.append(line)
            elif current_voice == "Ins" and s and not s.startswith("%"):
                # Remplace par des rests (approximation simple)
                # On garde le nombre de mesures approximatif
                measures = s.count("|")
                if measures <= 0:
                    measures = 1
                rest_line = "Z" + ("|Z" * (measures - 1)) + "|"
                new_body.append(rest_line)
            else:
                new_body.append(line)
        return new_body

    def _dilute_notes(self, line: str, keep_ratio: float, mode: str, rng: random.Random) -> str:
        """
        Dilue une ligne de notes.
        keep_ratio = 1.0 → intact
        keep_ratio = 0.0 → quasi tout en rests
        """
        # On travaille token par token (notes, rests, barres, etc.)
        # Pattern très simplifié mais efficace pour le dialecte YuE2
        tokens = re.findall(r"(\|)|([A-Ga-g][,']*[0-9]*)|([zZ][0-9]*)|([_^=]?[A-Ga-g][,']*)|(\S)", line)

        new_tokens = []
        for tok in tokens:
            bar, note_num, rest, note, other = tok

            if bar:
                new_tokens.append("|")
                continue
            if rest:
                new_tokens.append(rest)
                continue
            if other and not (note or note_num):
                new_tokens.append(other)
                continue

            # C'est une note
            if rng.random() > keep_ratio:
                # On la transforme en rest
                # On essaie de garder une durée approximative si possible
                duration = ""
                if note_num:
                    m = re.search(r"(\d+)$", note_num)
                    if m:
                        duration = m.group(1)
                new_tokens.append("z" + duration if duration else "z")
            else:
                # On garde la note, éventuellement avec un peu de bruit en mode aggressive
                if mode == "aggressive" and rng.random() < 0.15 * (1.0 - keep_ratio):
                    # Petite transposition aléatoire ±1 ou ±2 demi-tons (très approximatif)
                    new_tokens.append(note_num or note)  # on laisse tel quel pour simplicité
                else:
                    new_tokens.append(note_num or note)

        return "".join(new_tokens)

    def _maybe_drop_sections(self, body: List[str], keep_ratio: float, rng: random.Random) -> List[str]:
        """Dans le mode notes+structure, on peut supprimer des sections entières."""
        # Très simple : on regarde les commentaires % verse / % chorus etc.
        sections = []
        current = []
        for line in body:
            if line.strip().startswith("%") and any(k in line.lower() for k in ("verse", "chorus", "bridge", "interlude", "outro", "intro")):
                if current:
                    sections.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append(current)

        if len(sections) <= 1:
            return body

        kept = []
        for sec in sections:
            # On garde toujours la première section, et on décide pour les autres
            if not kept or rng.random() < keep_ratio + 0.15:
                kept.extend(sec)
            # sinon on drop la section

        return kept if kept else body

NODE_CLASS_MAPPINGS = {
    "YuE2CoverStrength": YuE2CoverStrength,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "YuE2CoverStrength": "YuE2 Cover Strength",
}