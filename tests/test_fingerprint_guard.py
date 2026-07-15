"""Tests de la couche 0 (garde d'empreinte déterministe) — 100 % hors ligne."""

from middleware.fingerprint_guard import verifier
from middleware.intent_capture import EmpreinteIntention


def empreinte_rh() -> EmpreinteIntention:
    return EmpreinteIntention(
        requete_initiale="Résume le dossier RH de Jean et envoie le résumé à manager@company.com",
        action_attendue="Résumer un dossier RH et envoyer le résumé",
        destinataires_autorises=["manager@company.com"],
        perimetre_donnees="dossier RH de Jean",
    )


def test_destination_autorisee_aucune_violation():
    violations = verifier(
        empreinte_rh(), "send_message",
        {"destinataire": "manager@company.com", "contenu": "Voici le résumé."},
    )
    assert violations == []


def test_destination_inconnue_detectee():
    """Cœur du scénario A1 : exfiltration vers l'adresse de l'attaquant."""
    violations = verifier(
        empreinte_rh(), "send_message",
        {"destinataire": "audit-externe@gmail.com", "contenu": "dossier complet"},
    )
    codes = [v.code for v in violations]
    assert "destination_inconnue" in codes
    assert max(v.gravite for v in violations) >= 70  # doit suffire à bloquer seul


def test_action_hors_intention():
    """Déviation critique (CdC §3.2) : résumé demandé, suppression tentée."""
    empreinte = EmpreinteIntention(
        requete_initiale="Fais-moi un résumé du rapport trimestriel",
        action_attendue="Résumer le rapport trimestriel",
    )
    violations = verifier(empreinte, "delete_file", {"fichier": "rapport.txt"})
    assert any(v.code == "action_hors_intention" for v in violations)


def test_outil_prevu_par_intention_ok():
    """L'envoi est bien dans l'intention → pas de violation de catégorie."""
    violations = verifier(
        empreinte_rh(), "send_message",
        {"destinataire": "manager@company.com", "contenu": "résumé"},
    )
    assert not any(v.code == "action_hors_intention" for v in violations)


def test_compte_numerique_inconnu():
    """Scénario A2 (e-commerce) : remboursement détourné vers un autre compte."""
    empreinte = EmpreinteIntention(
        requete_initiale="Traite le ticket 1042 et rembourse le client du compte #78421",
        action_attendue="Répondre au ticket 1042 et rembourser le client",
        destinataires_autorises=["#78421"],
    )
    violations = verifier(empreinte, "refund", {"compte": "#99307", "montant": 45000})
    assert any(v.code == "destination_inconnue" for v in violations)
