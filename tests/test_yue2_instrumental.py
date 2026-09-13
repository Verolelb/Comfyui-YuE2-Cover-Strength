# -*- coding: utf-8 -*-
"""
Tests du node YuE2 Instrumental.

Depuis la racine du dépôt :

    python -m unittest discover -s tests -v
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yue2_instrumental import YuE2Instrumental


# Score natif YuE2 : la voix Vocal porte la mélodie chantée et les accords,
# la voix Ins porte le thème instrumental.
ABC = """X:1
T:Test
M:4/4
L:1/32
Q:1/4=88
V: Vocal clef=treble name="Vocal Melody" snm="Vocal"
V: Ins clef=treble name="Ins Melody" snm="Inst."
K:G
% verse
V: Vocal
"Gmaj7"B8d8"Am7"c8A8|"D7"F16"G"G16|
V: Ins
Z2|
"""

ABC_TWO_MELODIES = """X:1
T:Test
M:4/4
L:1/32
V: Vocal
V: Ins
K:C
V: Vocal
C8D8E8F8|
V: Ins
G8A8B8c8|
"""

ABC_TIE = """X:1
T:Test
M:4/4
L:1/32
V: Vocal
V: Ins
K:C
V: Vocal
C8-C8|D8E8|
V: Ins
Z1|
"""

ABC_NO_VOICE = """X:1
T:Test
M:4/4
L:1/4
K:C
C D E F|
"""


def notes_of(text):
    """Notes réelles d'un extrait ABC, en ignorant les lignes de champ."""
    lignes = [l for l in text.splitlines() if not re.match(r"^[A-Za-z]:", l.strip())]
    return re.findall(r"[_^=]?[A-Ga-g][,']*", "\n".join(lignes))


class TestStyleInstrumental(unittest.TestCase):
    def setUp(self):
        self.node = YuE2Instrumental()

    def style(self, value, remove=True, tag=True):
        return self.node.prepare(value, "", "", remove, tag)[0]

    def test_les_descripteurs_de_voix_sont_retires(self):
        out = self.style("English, warm female vocal, melodic piano pop, gentle drums, 90 BPM")
        self.assertNotIn("vocal", out.lower())
        self.assertNotIn("female", out.lower())
        # le reste de la phrase est conservé
        self.assertIn("warm", out)
        self.assertIn("melodic piano pop", out)
        self.assertIn("English", out)
        self.assertIn("90 BPM", out)

    def test_tag_instrumental_ajoute(self):
        self.assertTrue(self.style("cinematic, piano").startswith("instrumental,"))

    def test_tag_instrumental_pas_duplique(self):
        out = self.style("cinematic, piano, instrumental")
        self.assertEqual(out.lower().count("instrumental"), 1)
        self.assertEqual(out, "cinematic, piano, instrumental")

    def test_tag_instrumental_desactivable(self):
        out = self.style("cinematic, piano", remove=True, tag=False)
        self.assertNotIn("instrumental", out.lower())

    def test_retrait_des_voix_desactivable(self):
        out = self.style("warm female vocal, piano", remove=False, tag=False)
        self.assertIn("female", out.lower())
        self.assertIn("vocal", out.lower())

    def test_phrase_entierement_vocale_supprimee(self):
        out = self.style("piano, male vocal, choir, drums")
        self.assertNotIn("male", out.lower())
        self.assertNotIn("choir", out.lower())
        self.assertIn("piano", out)
        self.assertIn("drums", out)

    def test_style_vide_tombe_sur_instrumental(self):
        self.assertEqual(self.style("   "), "instrumental")


class TestParoles(unittest.TestCase):
    def setUp(self):
        self.node = YuE2Instrumental()

    def test_les_paroles_sortent_toujours_vides(self):
        for lyrics in ("[Verse]\nHello world\n[Chorus]\nBye", "[Instrumental]", "la la la"):
            self.assertEqual(self.node.prepare("cinematic, piano", lyrics, "", True, True)[1], "")

    def test_info_compte_les_mots_vides(self):
        info = self.node.prepare("cinematic, piano", "[Verse]\nHello world\n[Chorus]\nBye", "", True, True)[3]
        self.assertIn("5 mot(s) vidé(s)", info)
        self.assertIn("Instrumental", info)


class TestScoreAbc(unittest.TestCase):
    def setUp(self):
        self.node = YuE2Instrumental()

    def abc(self, value):
        return self.node.prepare("cinematic, piano", "", value, True, True)[2]

    def info(self, value):
        return self.node.prepare("cinematic, piano", "", value, True, True)[3]

    def test_voix_vocal_videe_en_silences(self):
        out = self.abc(ABC)
        self.assertIn('"Gmaj7"z8z8"Am7"z8z8|"D7"z16"G"z16|', out)
        self.assertNotIn("B8", out)
        self.assertNotIn("A8", out)

    def test_les_accords_sont_conserves(self):
        out = self.abc(ABC)
        for accord in ('"Gmaj7"', '"Am7"', '"D7"', '"G"'):
            self.assertIn(accord, out)

    def test_la_voix_ins_est_intacte(self):
        out = self.abc(ABC_TWO_MELODIES)
        self.assertIn("G8A8B8c8|", out)
        self.assertNotIn("C8D8E8F8", out)

    def test_structure_des_mesures_conservee(self):
        for score in (ABC, ABC_TWO_MELODIES, ABC_TIE):
            self.assertEqual(self.abc(score).count("|"), score.count("|"))

    def test_liaison_retiree_sur_les_silences(self):
        """Un silence ne peut pas porter de liaison : z8-z8 est invalide."""
        out = self.abc(ABC_TIE)
        self.assertNotIn("-", out)
        self.assertIn("z8z8|z8z8|", out)

    def test_champ_en_ligne_protege(self):
        score = ABC_TWO_MELODIES.replace("C8D8E8F8|", "C8|[K:G]D8E8F8|")
        self.assertIn("[K:G]", self.abc(score))

    def test_paroles_w_supprimees(self):
        score = ABC_TWO_MELODIES.replace("C8D8E8F8|", "C8D8E8F8|\nw: la la la la")
        out = self.abc(score)
        self.assertNotIn("w: la la", out)
        self.assertIn("ligne(s) w:", self.info(score))

    def test_score_sans_voix_recopie_tel_quel(self):
        self.assertEqual(self.abc(ABC_NO_VOICE), ABC_NO_VOICE)
        self.assertIn("recopié tel quel", self.info(ABC_NO_VOICE))

    def test_score_vide(self):
        self.assertEqual(self.abc(""), "")
        self.assertIn("aucun score fourni", self.info(""))


class TestGardeFous(unittest.TestCase):
    def setUp(self):
        self.node = YuE2Instrumental()

    def test_entrees_invalides_ne_plantent_pas(self):
        for value in (None, float("nan"), 0, False):
            style, lyrics, abc, info = self.node.prepare(value, value, value, value, value)
            self.assertEqual(style, "instrumental")
            self.assertEqual(lyrics, "")
            self.assertEqual(abc, "")
            self.assertIsInstance(info, str)

    def test_booleens_arrivent_en_texte(self):
        self.assertNotIn("instrumental", self.node.prepare("cinematic, piano", "", "", "true", "false")[0])
        self.assertIn("instrumental", self.node.prepare("cinematic, piano", "", "", "false", "true")[0])

    def test_sorties_declarees(self):
        self.assertEqual(self.node.RETURN_TYPES, ("STRING", "STRING", "STRING", "STRING"))
        self.assertEqual(self.node.RETURN_NAMES, ("style", "lyrics", "abc", "info"))

    def test_run_affiche_le_resume_sur_le_node(self):
        """`run` est le point d'entrée ComfyUI : il ajoute le résumé visible à l'écran."""
        out = self.node.run("cinematic, piano", "", "", True, True)
        self.assertEqual(out["result"], ("instrumental, cinematic, piano", "", "", out["result"][3]))
        self.assertEqual(out["ui"]["text"], [out["result"][3]])
        self.assertIn("Instrumental", out["ui"]["text"][0])


if __name__ == "__main__":
    unittest.main()
