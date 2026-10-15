"""glpi_connector -- passerelle GLPI <-> rag_core.

Un ticket est créé dans GLPI (côté client) -> le poller le récupère via l'API REST GLPI
-> rag_core.pipeline.answer produit une SUGGESTION -> elle est postée en suivi (ITILFollowup
privé) préfixée "[Suggestion IA - à valider]". Un agent humain valide/édite/envoie.
L'IA ne répond JAMAIS en autonomie au client final.

DRY_RUN=true par défaut (strict) : le poller LOGUE ce qu'il posterait, aucun appel
d'écriture GLPI.

Consomme rag_core par dépendance (pip install ../../rag_core), jamais par copie.
"""
__version__ = "0.1.0"
