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
from typing import List, Tuple

# --------------------------------------------------------------------------
# Analyse des lignes ABC
# --------------------------------------------------------------------------

# Longueur d'une note : "2", "3/2", "/2", "/", "//"
_LENGTH = r"(?:\d+(?:/\d*)?|/\d*|//)"

# Découpe une ligne de notes. Deux points importants :
#   - les accords sont traités comme une seule unité, sinon "[CEG]" peut
#     devenir "[zzz]" (ABC invalide) ;
#   - les champs en ligne "[K:G]" sont protégés, sinon leur note serait diluée.
_TOKEN_RE = re.compile(
    r"(?P<field>\[[A-Za-z]:[^\]]*\])"                   # champ en ligne [K:G]
    r"|(?P<bar>\|+\]?|:\|+|\|:|\[\||\[\d)"             # barres, reprises, endings
    r"|(?P<chord>\[[^\]]*\]" + _LENGTH + r"?)"          # accord [CEG]2
    r"|(?P<note>[_^=]*[A-Ga-g][,']*" + _LENGTH + r"?)"  # note C, c' , ^F2
    r"|(?P<rest>[xzZ]" + _LENGTH + r"?)"                # silence
    r"|(?P<space>\s+)"
    r"|(?P<other>\S)"
)

# Une note isolée : altération, lettre, octave, longueur
_PITCH_RE = re.compile(r"([_^=]?)([A-Ga-g])([,']*)(" + _LENGTH + r")?")

# Longueur en fin de token ("C2" -> "2", "[CEG]/2" -> "/2")
_LENGTH_RE = re.compile(r"(" + _LENGTH + r")$")

# Champ ABC en début de ligne (w:, s:, H: ...) : ce n'est pas une ligne de notes
_FIELD_RE = re.compile(r"^[A-Za-z]:")


class YuE2CoverStrength:
    """
    Contrôle la force du cover en diluant le score ABC.
    """

    # ----------------------------------------------------------------------
    # Réglages
    # ----------------------------------------------------------------------
    # Valeurs par défaut sûres : ComfyUI peut envoyer None / NaN (JSON invalide)
    # ou des valeurs décalées quand la liste des widgets est désynchronisée au
    # chargement d'un workflow. On retombe alors sur force 100 et mode "notes".
    DEFAULT_STRENGTH = 100.0
    DEFAULT_MODE = "notes"
    MODES = ("notes", "notes+structure", "aggressive")

    # Mode aggressive : dilution renforcée d'un tiers + bruit de hauteur aléatoire
    AGGRESSIVE_DILUTION_BOOST = 1.33
    AGGRESSIVE_NOISE = 0.30

    # Mode notes+structure : en dessous de cette force, des sections entières sautent
    SECTION_DROP_THRESHOLD = 0.85

    # ----------------------------------------------------------------------
    # Tables de correspondance ABC
    # ----------------------------------------------------------------------
    # Hauteur : majuscule = octave centrale, minuscule = une octave au-dessus,
    # chaque "," descend d'une octave, chaque "'" monte d'une octave.
    _PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    _PITCH_CLASS_REV = {v: k for k, v in _PITCH_CLASS.items()}
    _ACCIDENTAL_SHIFT = {"^": 1, "_": -1, "=": 0}

    # Armure : nombre de dièses (> 0) ou de bémols (< 0), via le cycle des quintes
    _FIFTHS_BASE = {"F": -1, "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5}
    _MODE_FIFTHS = {
        "": 0, "maj": 0, "ion": 0,
        "dor": -2, "phr": -4, "lyd": 1, "mix": -1, "aeo": -3, "loc": -5,
        "m": -3, "min": -3,
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "abc": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Score ABC brut (provenant de SheetSage2, ou colle-le directement ici)"
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

        # Les valeurs affichées peuvent arriver vides / décalées selon le frontend :
        # on retombe toujours sur des valeurs saines (force 100, mode "notes").
        strength = self._coerce_strength(strength)
        mode = self._coerce_mode(mode)
        seed = self._coerce_int(seed)
        keep_vocal_only = self._coerce_bool(keep_vocal_only)
        keep_ratio = strength / 100.0          # 1.0 = intact, 0.0 = totalement dilué

        # Mode aggressive : on dilue plus fort que la force demandée. La formule
        # porte sur la dilution, donc 100 % reste exactement 100 % (score intact)
        # et la progression reste continue entre 99 % et 100 %.
        if mode == "aggressive":
            keep_ratio = max(0.0, 1.0 - (1.0 - keep_ratio) * self.AGGRESSIVE_DILUTION_BOOST)

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

        # L'armure sert à écrire les notes transposées avec le bon altération.
        key_flat = self._key_is_flat(header)

        # --- Option : garder uniquement Vocal ---
        if keep_vocal_only:
            body = self._keep_vocal_only(body)

        # --- Dilution des notes ---
        diluted_body = []
        for line in body:
            # On ne touche qu'aux lignes de notes : paroles (w:), champs et
            # commentaires sont recopiés tels quels.
            if not self._is_note_line(line):
                diluted_body.append(line)
                continue

            if keep_ratio >= 0.999:
                diluted_body.append(line)
                continue

            diluted_body.append(self._dilute_notes(line, keep_ratio, mode, rng, key_flat))

        # --- Mode notes+structure : on peut aussi supprimer des sections entières ---
        if mode == "notes+structure" and keep_ratio < self.SECTION_DROP_THRESHOLD:
            diluted_body = self._maybe_drop_sections(diluted_body, keep_ratio, rng)

        result = "\n".join(header + diluted_body).strip() + "\n"

        info = (f"Cover Strength {strength:.0f}% | mode={mode} | "
                f"kept={keep_ratio * 100:.0f}% | "
                f"seed={seed} | keep_vocal_only={keep_vocal_only}")
        return (result, info)

    # ----------------------------------------------------------------------
    # Garde-fous sur les entrées
    # ----------------------------------------------------------------------
    @classmethod
    def _coerce_strength(cls, value) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return cls.DEFAULT_STRENGTH
        if value != value:  # NaN
            return cls.DEFAULT_STRENGTH
        return max(0.0, min(100.0, value))

    @classmethod
    def _coerce_mode(cls, value) -> str:
        # Un combo peut arriver en texte, ou en simple index numérique s'il a été
        # sérialisé par le frontend dans un format différent.
        if isinstance(value, str):
            value = value.strip()
            if value in cls.MODES:
                return value
            if value.isdigit() and int(value) < len(cls.MODES):
                return cls.MODES[int(value)]
        elif isinstance(value, int) and not isinstance(value, bool):
            if 0 <= value < len(cls.MODES):
                return cls.MODES[value]
        return cls.DEFAULT_MODE

    @staticmethod
    def _coerce_int(value, default: int = 0) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            return default
        return max(0, value)

    @staticmethod
    def _coerce_bool(value) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    # ----------------------------------------------------------------------
    # Lecture du score
    # ----------------------------------------------------------------------
    @staticmethod
    def _is_note_line(line: str) -> bool:
        """Vrai si la ligne contient des notes (et non un champ, des paroles ou un commentaire)."""
        stripped = line.strip()
        return bool(stripped) and not stripped.startswith("%") and not _FIELD_RE.match(stripped)

    @classmethod
    def _note_length(cls, token: str) -> str:
        """Longueur explicite d'une note ou d'un accord : "C2" -> "2", "[CEG]/2" -> "/2"."""
        match = _LENGTH_RE.search(token)
        return match.group(1) if match else ""

    @classmethod
    def _key_is_flat(cls, header: List[str]) -> bool:
        """Vrai si l'armure est bémolisée (K:F, K:Bb, K:Dm...), False sinon."""
        for line in header:
            stripped = line.strip()
            if not stripped.startswith("K:"):
                continue
            key = stripped[2:].strip().replace(" ", "")
            if not key or key.lower().startswith("none"):
                return False
            match = re.match(r"([A-Ga-g])([#b]*)(.*)", key)
            if not match:
                return False
            letter, accidentals, mode = match.groups()
            fifths = cls._FIFTHS_BASE[letter.upper()]
            fifths += 7 * accidentals.count("#") - 7 * accidentals.count("b")
            fifths += cls._MODE_FIFTHS.get(mode.lower().rstrip("0123456789"), 0)
            return fifths < 0
        return False

    # ----------------------------------------------------------------------
    # Voix
    # ----------------------------------------------------------------------
    def _keep_vocal_only(self, body: List[str]) -> List[str]:
        """
        Vocal seul : la voix "Ins" devient des silences, barre par barre.
        La structure des mesures est conservée, contrairement à un simple
        remplacement de la ligne par des silences de mesure.
        """
        new_body = []
        in_ins = False
        for line in body:
            stripped = line.strip()
            if stripped.startswith("V:"):
                in_ins = stripped[2:].strip().lower().startswith("ins")
                new_body.append(line)
            elif in_ins and self._is_note_line(line):
                new_body.append(self._notes_to_rests(line))
            else:
                new_body.append(line)
        return new_body

    def _notes_to_rests(self, line: str) -> str:
        """Remplace notes et accords par des silences de même longueur."""
        out = []
        for match in _TOKEN_RE.finditer(line):
            token = match.group("note") or match.group("chord")
            out.append("z" + self._note_length(token) if token else match.group(0))
        return "".join(out)

    # ----------------------------------------------------------------------
    # Dilution
    # ----------------------------------------------------------------------
    def _dilute_notes(self, line: str, keep_ratio: float, mode: str, rng: random.Random,
                      key_flat: bool = False) -> str:
        """
        Dilue une ligne de notes.
        keep_ratio = 1.0 → intact
        keep_ratio = 0.0 → quasi tout en rests
        """
        new_tokens = []
        for match in _TOKEN_RE.finditer(line):
            # Une note et un accord se diluent de la même façon ; tout le reste
            # (barres, silences, champs, ornements, espaces) est recopié tel quel.
            token = match.group("note") or match.group("chord")

            if not token:
                new_tokens.append(match.group(0))
                continue

            if rng.random() > keep_ratio:
                # Silence de même longueur : les mesures restent justes.
                new_tokens.append("z" + self._note_length(token))
                continue

            # Mode aggressive : on décale la hauteur de certaines notes gardées
            # (±1 demi-ton le plus souvent, ±2 parfois). Un accord est transposé
            # d'un seul bloc, donc ses intervalles sont conservés.
            if mode == "aggressive" and rng.random() < self.AGGRESSIVE_NOISE * (1.0 - keep_ratio):
                token = self._transpose(token, rng, key_flat)
            new_tokens.append(token)

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

    # ----------------------------------------------------------------------
    # Hauteur (mode aggressive)
    # ----------------------------------------------------------------------
    @classmethod
    def _groups_to_pitch(cls, match) -> Tuple[int, str]:
        accidental, letter, octaves, duration = match.groups()
        octave = 0 if letter.isupper() else 1
        octave += octaves.count("'") - octaves.count(",")
        semitone = (octave * 12
                    + cls._PITCH_CLASS[letter.upper()]
                    + cls._ACCIDENTAL_SHIFT.get(accidental, 0))
        return semitone, duration or ""

    @classmethod
    def _parse_pitch(cls, token: str):
        """Décompose une note ABC en (demi-tons absolus, longueur), ou None si ce n'en est pas une."""
        match = _PITCH_RE.fullmatch(token)
        return cls._groups_to_pitch(match) if match else None

    @classmethod
    def _format_pitch(cls, semitone: int, duration: str = "", prefer_flat: bool = False) -> str:
        """Ré-encode un demi-ton absolu en note ABC, en privilégiant les notes diatoniques."""
        octave, within = divmod(semitone, 12)
        prefix = ""
        if within in cls._PITCH_CLASS_REV:
            letter = cls._PITCH_CLASS_REV[within]
        else:
            # On garde l'orthographe d'origine quand c'est possible : un _E reste
            # un bémol au lieu de devenir ^D (même hauteur, écriture différente).
            sharp = cls._PITCH_CLASS_REV.get(within - 1)
            flat = cls._PITCH_CLASS_REV.get(within + 1)
            if prefer_flat and flat:
                letter, prefix = flat, "_"
            elif sharp:
                letter, prefix = sharp, "^"
            elif flat:
                letter, prefix = flat, "_"
            else:
                return ""
        if octave <= 0:
            letter, marks = letter.upper(), "," * -octave
        else:
            letter, marks = letter.lower(), "'" * (octave - 1)
        return prefix + letter + marks + duration

    @classmethod
    def _transpose(cls, token: str, rng: random.Random, key_flat: bool = False) -> str:
        """Décale une note — ou un accord entier — de un ou deux demi-tons."""
        offset = rng.choice((-1, 1, -1, 1, -2, 2))

        def shift(match) -> str:
            semitone, duration = cls._groups_to_pitch(match)
            accidental = match.group(1)
            # L'altération écrite dans le score est prioritaire ; sinon on suit l'armure.
            prefer_flat = key_flat if accidental not in ("^", "_") else accidental == "_"
            shifted = cls._format_pitch(semitone + offset, duration, prefer_flat=prefer_flat)
            return shifted or match.group(0)

        # On sépare la longueur pour pouvoir la ré-attacher à la fin.
        length = cls._note_length(token)
        core = token[: len(token) - len(length)] if length else token

        if core.startswith("[") and core.endswith("]"):
            # Accord : le même décalage est appliqué à toutes les notes, les
            # intervalles sont donc conservés.
            core = "[" + _PITCH_RE.sub(shift, core[1:-1]) + "]"
        else:
            core = _PITCH_RE.sub(shift, core)

        return core + length


NODE_CLASS_MAPPINGS = {
    "YuE2CoverStrength": YuE2CoverStrength,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "YuE2CoverStrength": "YuE2 Cover Strength",
}
