"""Normalisation anti-obfuscation — prétraitement AVANT la couche 1.

Motivation (recherche, cf. docs/ETAT_DE_LART.md §6) : les détecteurs par regex se
contournent trivialement. Des travaux 2025-2026 montrent des taux d'évasion
jusqu'à ~93 % via caractères invisibles, homoglyphes, caractères « tag » Unicode
et encodages. On neutralise ces vecteurs en amont pour que la couche 1 voie le
texte réel, ET on traite l'obfuscation elle-même comme un signal : un document
légitime n'a aucune raison de cacher du texte à un humain.

Pipeline : décodage des tags Unicode -> suppression des invisibles ->
NFKC (pleine largeur/compat -> ASCII) -> mapping des homoglyphes ->
réduction de l'espacement lettre-à-lettre. Les blobs base64 suspects sont
signalés (pas décodés aveuglément, pour éviter les faux positifs).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# --- Caractères invisibles / de contrôle utilisés pour cacher du texte ---------
# Zero-width, joiners, marques directionnelles, BOM, séparateurs exotiques.
INVISIBLES = (
    "​‌‍‎‏"  # ZWSP, ZWNJ, ZWJ, LRM, RLM
    "‪‫‬‭‮"  # overrides bidirectionnels
    "⁠⁡⁢⁣⁤"  # word joiner, invisibles mathématiques
    "﻿­᠎"              # BOM, soft hyphen, mongolian vowel separator
)
_TABLE_INVISIBLES = {ord(c): None for c in INVISIBLES}

# --- Bloc « Tag » Unicode (U+E0000–U+E007F) : miroir invisible de l'ASCII ------
# Détourné pour smuggler un payload ASCII. On le RE-décode vers l'ASCII visible
# afin que la couche 1 puisse lire l'instruction cachée.
TAG_BASE = 0xE0000
TAG_FIN = 0xE007F

# --- Homoglyphes courants (autres scripts -> latin) ---------------------------
# Sous-ensemble pragmatique : les lettres cyrilliques/grecques qui ressemblent à
# des latines et servent à écrire « ignоre » (о cyrillique) sans matcher la regex.
HOMOGLYPHES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "ѕ": "s", "і": "i", "ј": "j", "ԁ": "d", "һ": "h", "ո": "n", "м": "m",
    "к": "k", "т": "t", "в": "b", "н": "h",
    "ο": "o", "α": "a", "ν": "v", "ρ": "p", "τ": "t", "ϲ": "c", "ι": "i",
}
_TABLE_HOMOGLYPHES = {ord(k): v for k, v in HOMOGLYPHES.items()}

# Espacement inséré entre chaque lettre pour casser un mot ("i g n o r e").
# On exige un RUN d'au moins 4 lettres isolées d'affilée : sinon on matcherait
# les nombreux mots d'une lettre du français ("à l'adresse", "y a", "d'un").
_ESPACEMENT_LETTRES = re.compile(r"(?:\w[ .\-_*]){3,}\w")
# Blob potentiellement encodé (base64/hex) d'une longueur suspecte
_BLOB_ENCODE = re.compile(r"[A-Za-z0-9+/=]{40,}|(?:[0-9a-fA-F]{2}[\s:]?){20,}")


@dataclass
class ResultatNormalisation:
    """Texte nettoyé + signaux d'obfuscation détectés pendant le nettoyage."""

    texte: str
    signaux: list[str] = field(default_factory=list)

    @property
    def obfusque(self) -> bool:
        return bool(self.signaux)


def _decoder_tags(texte: str) -> tuple[str, bool]:
    """Reconvertit les caractères du bloc Tag en ASCII visible."""
    trouve = False
    sortie = []
    for c in texte:
        point = ord(c)
        if TAG_BASE <= point <= TAG_FIN:
            trouve = True
            ascii_point = point - TAG_BASE
            if 0x20 <= ascii_point <= 0x7E:  # tag mappant un caractère imprimable
                sortie.append(chr(ascii_point))
        else:
            sortie.append(c)
    return "".join(sortie), trouve


def normaliser(texte: str) -> ResultatNormalisation:
    """Applique le pipeline de dé-obfuscation et collecte les signaux."""
    signaux: list[str] = []

    # 1. Caractères « tag » : re-décodés en ASCII (le payload caché redevient lisible)
    texte, tags_vus = _decoder_tags(texte)
    if tags_vus:
        signaux.append("caracteres_tag_unicode")

    # 2. Caractères invisibles / overrides bidirectionnels
    if any(ord(c) in _TABLE_INVISIBLES for c in texte):
        signaux.append("caracteres_invisibles")
        texte = texte.translate(_TABLE_INVISIBLES)

    # 3. NFKC : pleine largeur, ligatures, exposants -> forme canonique ASCII
    normalise = unicodedata.normalize("NFKC", texte)
    if normalise != texte:
        signaux.append("normalisation_compatibilite")
    texte = normalise

    # 4. Homoglyphes (cyrillique/grec -> latin)
    if any(ord(c) in _TABLE_HOMOGLYPHES for c in texte):
        signaux.append("homoglyphes")
        texte = texte.translate(_TABLE_HOMOGLYPHES)

    # 5. Espacement lettre-à-lettre ("i-g-n-o-r-e" -> "ignore") : on retire les
    #    séparateurs uniquement à l'intérieur des runs de lettres isolées détectés.
    compacte = _ESPACEMENT_LETTRES.sub(
        lambda m: re.sub(r"[ .\-_*]", "", m.group(0)), texte
    )
    if compacte != texte:
        signaux.append("espacement_lettres")
        texte = compacte

    # 6. Blob encodé suspect (signalé, non décodé — évite les faux positifs)
    if _BLOB_ENCODE.search(texte):
        signaux.append("blob_encode_suspect")

    return ResultatNormalisation(texte=texte, signaux=signaux)
