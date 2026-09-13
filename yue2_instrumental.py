# -*- coding: utf-8 -*-
"""
YuE2 Instrumental Node
Prépare une requête YuE2 strictement instrumentale, sans charger aucun modèle.

Rappel du fonctionnement réel de YuE2 (doc upstream + packs ComfyUI) :
  - le champ `lyrics` doit être VIDE : un tag "[Instrumental]" seul ne suffit
    pas, le champ ne doit contenir aucun mot ;
  - le `style` doit décrire genre / instruments / tempo SANS descripteur de voix
    ("female vocal", "male vocal", "singer"...) ;
  - si un score ABC est fourni, la voix `Vocal` doit être remise en silences :
    sinon le modèle chante la mélodie fournie, même avec des paroles vides.
    Les accords ("Am7") et la voix `Ins` (thème instrumental) sont conservés.

Ce node ne fait donc que produire des chaînes à brancher sur les nodes YuE2 que
tu utilises déjà (Compose / Generate Plan / Song Generator / API `yue2`) :
il ne charge pas de modèle et ne génère pas l'audio lui-même.
"""

from __future__ import annotations

import re
import string
from typing import List, Tuple

# --------------------------------------------------------------------------
# ABC : mêmes règles de tokenisation que YuE2CoverStrength, plus le symbole
# d'accord natif ("Am7") qui porte l'harmonie de la voix Vocal.
# --------------------------------------------------------------------------

# Longueur d'une note : "2", "3/2", "/2", "/", "//"
_LENGTH = r"(?:\d+(?:/\d*)?|/\d*|//)"

_TOKEN_RE = re.compile(
    r"(?P<field>\[[A-Za-z]:[^\]]*\])"                     # champ en ligne [K:G]
    r"|(?P<chord_symbol>\"[^\"]*\")"                      # accord natif "Am7"
    r"|(?P<bar>\|+\]?|:\|+|\|:|\[\||\[\d)"               # barres, reprises, endings
    r"|(?P<chord>\[[^\]]*\]" + _LENGTH + r"?)"            # accord [CEG]2
    r"|(?P<note>[_^=]*[A-Ga-g][,']*" + _LENGTH + r"?)"    # note C, c', ^F2
    r"|(?P<rest>[xzZ]" + _LENGTH + r"?)"                  # silence
    r"|(?P<space>\s+)"
    r"|(?P<other>\S)"
)

# Longueur en fin de token ("C2" -> "2", "[CEG]/2" -> "/2")
_LENGTH_RE = re.compile(r"(" + _LENGTH + r")$")

# Champ ABC en début de ligne (w:, s:, H: ...) : ce n'est pas une ligne de notes
_FIELD_RE = re.compile(r"^[A-Za-z]:")

# Déclaration / changement de voix : "V: Vocal", "V: Ins clef=treble"
_VOICE_RE = re.compile(r"^V:\s*(\S+)", re.IGNORECASE)


class YuE2Instrumental:
    """
    Transforme style + paroles + score ABC en requête instrumentale YuE2.
    """

    # ----------------------------------------------------------------------
    # Réglages
    # ----------------------------------------------------------------------
    DEFAULT_STYLE = "cinematic, piano, strings, instrumental"

    # Mots qui font chanter le modèle : on les retire du style, sinon YuE2
    # rajoute une voix même quand les paroles sont vides.
    VOCAL_TERMS = frozenset({
        "vocal", "vocals", "vocalist", "vocalists", "voice", "voices",
        "sing", "sings", "singer", "singers", "singing", "sung", "vocaloid",
        "rap", "rapper", "rapping", "spoken", "recitation",
        "choir", "choirs", "choral", "chant", "chanting",
        "male", "female", "man", "woman", "boy", "girl", "duet",
        "a-cappella", "acapella", "cappella", "lyric", "lyrics",
        "humming", "hummed", "scat",
    })

    # Une voix dont le nom commence par un de ces préfixes est chantée.
    VOCAL_VOICE_PREFIXES = ("vocal", "voice")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "style": ("STRING", {
                    "default": cls.DEFAULT_STYLE,
                    "multiline": True,
                    "tooltip": "Prompt de style/genre à instrumentaliser : les descripteurs de voix en sont retirés"
                }),
                "lyrics": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Paroles à neutraliser. Elles ne sont jamais recopiées en sortie : YuE2 fait de l'instrumental quand le champ lyrics est vide"
                }),
                "abc": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Score ABC optionnel (SheetSage2, piano roll...). La voix Vocal devient des silences, les accords et la voix Ins sont gardés"
                }),
                "remove_vocal_terms": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Retire du style les mots qui appellent une voix (female vocal, singer, choir...)"
                }),
                "add_instrumental_tag": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Garantit que le mot \"instrumental\" est présent dans le style"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("style", "lyrics", "abc", "info")
    FUNCTION = "run"
    CATEGORY = "YuE2/Utils"
    OUTPUT_NODE = False

    def run(self, style: str, lyrics: str, abc: str,
            remove_vocal_terms: bool, add_instrumental_tag: bool):
        """
        Point d'entrée ComfyUI : renvoie les mêmes sorties que `prepare`, plus le
        résumé affiché directement sur le node (sinon la sortie `info` reste
        invisible tant qu'elle n'est pas branchée).
        """
        style, lyrics, abc_out, info = self.prepare(
            style, lyrics, abc, remove_vocal_terms, add_instrumental_tag
        )
        return {"ui": {"text": [info]}, "result": (style, lyrics, abc_out, info)}

    def prepare(self, style: str, lyrics: str, abc: str,
                remove_vocal_terms: bool, add_instrumental_tag: bool):
        # Les valeurs affichées peuvent arriver vides / décalées selon le
        # frontend : on retombe toujours sur des valeurs saines.
        style = self._coerce_text(style).strip()
        lyrics = self._coerce_text(lyrics)
        abc = self._coerce_text(abc)
        remove_vocal_terms = self._coerce_bool(remove_vocal_terms, True)
        add_instrumental_tag = self._coerce_bool(add_instrumental_tag, True)

        # --- Style : on enlève ce qui déclenche une voix ---
        removed = 0
        if remove_vocal_terms:
            style, removed = self._strip_vocal_terms(style)
        if add_instrumental_tag:
            style = self._ensure_instrumental(style)
        if not style:
            style = "instrumental"

        # --- Paroles : toujours vides (c'est LA condition de l'instrumental) ---
        dropped_words = len(lyrics.split())

        # --- Score : la voix chantée devient des silences ---
        abc_out, abc_info = self._instrumental_abc(abc)

        info = (
            f"Instrumental | style: {removed} mot(s) de voix retiré(s) | "
            f"lyrics: {dropped_words} mot(s) vidé(s) | {abc_info}"
        )
        return (style, "", abc_out, info)

    # ----------------------------------------------------------------------
    # Garde-fous sur les entrées
    # ----------------------------------------------------------------------
    @staticmethod
    def _coerce_text(value) -> str:
        # Un widget texte ne reçoit que des str : None, NaN, int ou bool
        # signalent un frontend désynchronisé, on repart donc sur du vide.
        return value if isinstance(value, str) else ""

    @staticmethod
    def _coerce_bool(value, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip().lower()
            if value in ("", "none", "nan", "null"):
                return default
            return value in ("1", "true", "yes", "on")
        return bool(value)

    # ----------------------------------------------------------------------
    # Style
    # ----------------------------------------------------------------------
    @staticmethod
    def _normalize_word(word: str) -> str:
        """Minuscule sans ponctuation de bord : "Female" -> female."""
        return word.strip(string.punctuation).lower()

    @classmethod
    def _strip_vocal_terms(cls, style: str) -> Tuple[str, int]:
        """
        Retire les mots de voix, phrase par phrase. Le reste de la phrase est
        conservé ("warm female vocal" -> "warm"), et une phrase qui ne contient
        plus rien est supprimée.
        """
        kept_phrases: List[str] = []
        removed = 0
        for phrase in re.split(r"[,\n;|]+", style):
            kept_words = []
            for word in phrase.split():
                if cls._normalize_word(word) in cls.VOCAL_TERMS:
                    removed += 1
                else:
                    kept_words.append(word)
            if kept_words:
                kept_phrases.append(" ".join(kept_words))
        return ", ".join(kept_phrases), removed

    @classmethod
    def _ensure_instrumental(cls, style: str) -> str:
        """Ajoute le tag instrumental s'il n'est pas déjà là."""
        tags = {cls._normalize_word(word) for word in re.split(r"[,\s]+", style) if word.strip()}
        if "instrumental" in tags:
            return style
        return f"instrumental, {style}" if style else "instrumental"

    # ----------------------------------------------------------------------
    # Score ABC
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
    def _is_vocal_voice(cls, name: str) -> bool:
        return name.strip().lower().startswith(cls.VOCAL_VOICE_PREFIXES)

    @staticmethod
    def _split_header(lines: List[str]) -> Tuple[List[str], List[str]]:
        """
        Sépare l'en-tête (X:, T:, M:, L:, Q:, V:, K:, %) du corps du score.
        Les déclarations V: placées avant K: sont donc dans l'en-tête, les
        changements de voix du corps restent dans le corps.
        """
        header: List[str] = []
        body: List[str] = []
        in_header = True
        for line in lines:
            stripped = line.strip()
            if in_header and (
                stripped.startswith(("X:", "T:", "M:", "L:", "Q:", "V:", "K:", "%"))
                or stripped == ""
            ):
                header.append(line)
                if stripped.startswith("K:"):
                    in_header = False
            else:
                in_header = False
                body.append(line)
        return header, body

    def _instrumental_abc(self, abc: str) -> Tuple[str, str]:
        """Vide la voix chantée du score tout en gardant mesures, accords et Ins."""
        if not abc.strip():
            # Pas de score : c'est le cas normal. YuE2 planifie alors lui-même sa
            # mélodie/accords, et le champ lyrics vide suffit à éviter la voix.
            # Fournir un score ici court-circuiterait ce planificateur.
            return "", "abc: aucun score fourni -> laisse la sortie abc débranchée (YuE2 planifie son propre score)"

        lines = abc.strip().splitlines()
        header, body = self._split_header(lines)

        new_body, cleared, dropped_lyric_lines, has_voices = self._clear_vocal_voice(body)
        if not has_voices:
            # Score sans étiquette de voix : impossible de savoir quoi vider,
            # on préfère ne rien casser.
            return abc, "abc: aucune voix Vocal détectée -> score recopié tel quel"

        result = "\n".join(header + new_body).strip() + "\n"
        details = f"abc: voix Vocal vidée ({cleared} note(s)"
        if dropped_lyric_lines:
            details += f", {dropped_lyric_lines} ligne(s) w: retirée(s)"
        details += "), accords et voix Ins conservés"
        return result, details

    def _clear_vocal_voice(self, body: List[str]):
        """Remplace les notes de la voix chantée par des silences de même longueur."""
        new_body: List[str] = []
        in_vocal = False
        has_voices = False
        cleared = 0
        dropped_lyric_lines = 0

        for line in body:
            stripped = line.strip()
            voice = _VOICE_RE.match(stripped)
            if voice:
                has_voices = True
                in_vocal = self._is_vocal_voice(voice.group(1))
                new_body.append(line)
                continue

            if in_vocal and stripped.startswith("w:"):
                # Paroles attachées à la voix chantée : on les retire aussi.
                dropped_lyric_lines += 1
                continue

            if in_vocal and self._is_note_line(line):
                new_line, count = self._notes_to_rests(line)
                cleared += count
                new_body.append(new_line)
                continue

            new_body.append(line)

        return new_body, cleared, dropped_lyric_lines, has_voices

    def _notes_to_rests(self, line: str) -> Tuple[str, int]:
        """
        Remplace notes et accords par des silences de même longueur.
        Les symboles d'accord ("Am7") sont conservés : chez YuE2 c'est l'harmonie
        de la voix, elle doit rester même quand la voix se tait.
        """
        out: List[str] = []
        count = 0
        for match in _TOKEN_RE.finditer(line):
            token = match.group("note") or match.group("chord")
            if token:
                out.append("z" + self._note_length(token))
                count += 1
            elif match.group(0) == "-":
                # Un silence ne peut pas porter de liaison (ABC invalide) :
                # on retire le "-", les deux silences se suivent et la durée
                # totale est identique.
                continue
            else:
                out.append(match.group(0))
        return "".join(out), count


NODE_CLASS_MAPPINGS = {
    "YuE2Instrumental": YuE2Instrumental,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "YuE2Instrumental": "YuE2 Instrumental",
}
