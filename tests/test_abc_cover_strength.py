# -*- coding: utf-8 -*-
"""
Tests du node YuE2 Cover Strength.

Depuis la racine du dépôt :

    python -m unittest discover -s tests -v
"""

import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abc_cover_strength import YuE2CoverStrength


ABC = """X:1
T:Test
M:4/4
L:1/4
Q:1/4=120
K:C
V: Vocal
C D E F|G A B c|d e f g|a b c' d'|
V: Ins
C,2 E,2|G,2 C,2|"""

CHORDS = """X:1
T:Test
M:4/4
L:1/4
K:C
[CEG]2 [DFA]2|[EGB]2 z2|"""


def notes_of(text):
    """
    Notes réelles d'un extrait ABC.
    On ignore les lignes de champ (X:, K:C, V: Vocal...) : leurs mots contiennent
    des lettres A-G qu'on prendrait sinon pour des notes.
    """
    lignes = [l for l in text.splitlines() if not re.match(r"^[A-Za-z]:", l.strip())]
    return re.findall(r"[_^=]?[A-Ga-g][,']*", "\n".join(lignes))


class TestGardeFous(unittest.TestCase):
    """force 100 / mode notes quand une valeur arrive invalide."""

    def setUp(self):
        self.node = YuE2CoverStrength()

    def info(self, strength, mode, seed=1, keep=False):
        return self.node.apply(ABC, strength, mode, seed, keep)[1]

    def test_nan_retombe_sur_100(self):
        self.assertIn("Cover Strength 100%", self.info(float("nan"), "notes"))

    def test_none_retombe_sur_100(self):
        self.assertIn("Cover Strength 100%", self.info(None, "notes"))

    def test_texte_retombe_sur_100(self):
        self.assertIn("Cover Strength 100%", self.info("notes", "notes"))

    def test_hors_bornes_est_borne(self):
        self.assertIn("Cover Strength 100%", self.info(250.0, "notes"))
        self.assertIn("Cover Strength 0%", self.info(-50.0, "notes"))

    def test_mode_invalide_retombe_sur_notes(self):
        for bad in (0, "0", "??", None, True):
            self.assertIn("mode=notes", self.info(50.0, bad))

    def test_mode_en_index_est_accepte(self):
        self.assertIn("mode=aggressive", self.info(50.0, 2))

    def test_seed_invalide_ne_plante_pas(self):
        for bad in (None, float("nan"), "abc"):
            self.node.apply(ABC, 50.0, "notes", bad, False)

    def test_keep_vocal_arrive_en_texte(self):
        self.assertIn("keep_vocal_only=False", self.info(50.0, "notes", 1, "false"))
        self.assertIn("keep_vocal_only=True", self.info(50.0, "notes", 1, "true"))

    def test_abc_vide(self):
        self.assertEqual(self.node.apply("", 50.0, "notes", 1, False)[1], "Empty ABC")
        self.assertEqual(self.node.apply("   ", 50.0, "notes", 1, False)[1], "Empty ABC")


class TestDilution(unittest.TestCase):
    def setUp(self):
        self.node = YuE2CoverStrength()

    def apply(self, strength, mode="notes", seed=1, keep=False, abc=ABC):
        return self.node.apply(abc, strength, mode, seed, keep)[0]

    def test_force_100_est_un_identity(self):
        for mode in YuE2CoverStrength.MODES:
            self.assertEqual(self.apply(100.0, mode).strip(), ABC.strip(),
                             f"le score devrait être intact en mode {mode}")

    def test_force_0_retire_presque_toutes_les_notes(self):
        self.assertLessEqual(len(notes_of(self.apply(0.0))), 1)

    def test_meme_seed_meme_resultat(self):
        self.assertEqual(self.apply(40.0, seed=7), self.apply(40.0, seed=7))

    def test_seeds_differents_donnent_des_resultats_differents(self):
        self.assertNotEqual(self.apply(40.0, seed=1), self.apply(40.0, seed=2))

    def test_structure_des_mesures_conservee(self):
        """Une note supprimée devient un silence de même longueur : les barres ne bougent pas."""
        for mode in YuE2CoverStrength.MODES:
            self.assertEqual(self.apply(30.0, mode).count("|"), ABC.count("|"), mode)

    def test_les_paroles_ne_sont_pas_diluees(self):
        abc = ABC + "\nw: la la la la"
        self.assertIn("w: la la la la", self.apply(30.0, seed=3, abc=abc))

    def test_les_silences_existants_sont_conserves(self):
        abc = """X:1
T:t
M:4/4
L:1/4
K:C
C z D z|E z F z|"""
        self.assertGreaterEqual(self.apply(30.0, seed=5, abc=abc).count("z"), 4)

    def test_les_longueurs_sont_conservees(self):
        """C2 doit devenir z2 (ou rester une note avec sa longueur), jamais z."""
        out = self.apply(20.0, seed=11).split("V: Ins", 1)[1]
        for token in re.findall(r"[_^]?[A-Ga-g][,']*\d*|[zZ]\d*", out):
            self.assertTrue(token[-1].isdigit(), f"longueur perdue sur {token!r}")

    def test_accords_supprimes_entierement(self):
        """Un accord doit partir d'un bloc, jamais devenir [zzz] (ABC invalide)."""
        for seed in range(1, 80):
            out = self.apply(50.0, seed=seed, abc=CHORDS)
            for group in re.findall(r"\[[^\]]*\]", out):
                self.assertNotIn("z", group, f"accord corrompu {group!r} (seed={seed})")

    def test_champ_en_ligne_protege(self):
        abc = """X:1
T:t
M:4/4
L:1/4
K:C
C D E F|[K:G]G A B c|"""
        for seed in range(1, 80):
            self.assertIn("[K:G]", self.apply(50.0, seed=seed, abc=abc))

    def test_keep_vocal_only_vide_seulement_la_voix_ins(self):
        out = self.apply(100.0, keep=True)
        self.assertIn("C D E F|G A B c|d e f g|a b c' d'|", out)
        ins = out.split("V: Ins", 1)[1]
        self.assertEqual(notes_of(ins), [])
        self.assertEqual(ins.count("|"), 2)


class TestModeAggressive(unittest.TestCase):
    def setUp(self):
        self.node = YuE2CoverStrength()

    def apply(self, strength, mode, seed):
        return self.node.apply(ABC, strength, mode, seed, False)[0]

    def test_force_100_reste_intacte(self):
        self.assertEqual(self.apply(100.0, "aggressive", 3).strip(), ABC.strip())

    def test_dilue_plus_que_le_mode_notes(self):
        def remaining(mode):
            return sum(len(notes_of(self.apply(50.0, mode, s))) for s in range(1, 101))
        self.assertLess(remaining("aggressive"), remaining("notes"))

    def test_ajoute_un_bruit_de_hauteur(self):
        altered = [s for s in range(1, 101) if re.search(r"[\^_]", self.apply(50.0, "aggressive", s))]
        untouched = [s for s in range(1, 101) if re.search(r"[\^_]", self.apply(50.0, "notes", s))]
        self.assertGreater(len(altered), 0)
        self.assertEqual(untouched, [])

    def test_toutes_les_notes_produites_sont_valides(self):
        for seed in range(1, 80):
            out = self.apply(40.0, "aggressive", seed)
            for token in notes_of(out):
                self.assertIsNotNone(self.node._parse_pitch(token), token)


class TestHauteur(unittest.TestCase):
    def setUp(self):
        self.node = YuE2CoverStrength()

    def test_parse_et_format_sont_inverses(self):
        for token in ["C", "D", "E", "F", "G", "A", "B", "c", "d", "f", "g", "a", "b",
                      "C,", "C,,", "c'", "c''", "B,", "^C", "_E", "^F", "_B",
                      "c2", "C,4", "A16", "g4", "_B,", "^d'", "C/2", "F3/2"]:
            semitone, duration = self.node._parse_pitch(token)
            prefer_flat = token.startswith("_")
            self.assertEqual(self.node._format_pitch(semitone, duration, prefer_flat), token)

    def test_silences_et_barres_ne_sont_pas_des_notes(self):
        for token in ["z", "z2", "Z", "x", "|", ">", "[CEG]"]:
            self.assertIsNone(self.node._parse_pitch(token))

    def test_transposition_dans_la_limite_de_deux_demi_tons(self):
        for base in ["C", "c", "C,", "c'", "G", "e'", "B,", "F", "A"]:
            reference = self.node._parse_pitch(base)[0]
            for i in range(150):
                out = self.node._transpose(base, random.Random(i))
                semitone = self.node._parse_pitch(out)[0]
                self.assertLessEqual(abs(semitone - reference), 2, f"{base} -> {out}")

    def test_armure_bemolisee_donne_des_bemols(self):
        for base in ["C", "c", "G", "B,", "F"]:
            for i in range(150):
                out = self.node._transpose(base, random.Random(i), key_flat=True)
                self.assertNotIn("^", out, out)

    def test_armure_diese_donne_des_dieses(self):
        produits = {self.node._transpose("C", random.Random(i), key_flat=False) for i in range(150)}
        self.assertTrue(any(t.startswith("^") for t in produits), produits)

    def test_accord_transpose_dun_seul_bloc(self):
        """Les intervalles d'un accord doivent survivre à la transposition."""
        for i in range(100):
            out = self.node._transpose("[CEG]", random.Random(i), key_flat=False)
            hauteurs = [self.node._parse_pitch(t)[0] for t in notes_of(out)]
            self.assertEqual([b - a for a, b in zip(hauteurs, hauteurs[1:])], [4, 3], out)

    def test_longueur_conservee_a_la_transposition(self):
        for token in ["C2", "c'4", "F,8", "A16"]:
            for i in range(50):
                out = self.node._transpose(token, random.Random(i))
                self.assertTrue(out.endswith(self.node._note_length(token)), out)

    def test_lecture_de_larmure(self):
        pour = ["K:F", "K:Bb", "K:Eb", "K:Ab", "K:Dm", "K:Gm", "K:Fnood"]
        contre = ["K:C", "K:G", "K:D", "K:A", "K:E", "K:B", "K:Am", "K:Em", "K:Ddor",
                  "K:Gmix", "K:none"]
        for ligne in pour:
            self.assertTrue(self.node._key_is_flat([ligne]), ligne)
        for ligne in contre:
            self.assertFalse(self.node._key_is_flat([ligne]), ligne)


if __name__ == "__main__":
    unittest.main()
