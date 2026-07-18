"""Script de test manuel — vérifie que agent + middleware se connectent bien."""

from dotenv import load_dotenv

from agent.agent import executer_session
from middleware.argus import Argus

load_dotenv()

argus = Argus(protege=True)
resultat = executer_session(
    "Cherche le document 'note_rh.txt' et résume-le",
    argus=argus,
)
print("Réponse finale de l'agent :", resultat)
