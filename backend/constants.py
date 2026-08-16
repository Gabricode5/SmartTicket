import uuid

# Chaque déploiement SmartTicket est aujourd'hui mono-tenant (une instance = un client,
# cf. décision d'architecture "flotte d'instances" plutôt que multi-tenant partagé).
# tenant_id est posé dès maintenant sur les tables principales avec cette valeur fixe
# unique, pour qu'une future bascule vers un vrai multi-tenant soit une fusion de données
# (les lignes ont déjà un tenant_id) plutôt qu'une réécriture de schéma.
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

VALID_REASONS = {"technique", "complexe", "sensible", "autre"}

REASON_LABELS = {
    "technique": "Technique",
    "complexe": "Complexe",
    "sensible": "Sensible",
    "autre": "Autre",
}

REASON_COLORS = {
    "technique": "#0ea5e9",
    "complexe": "#f59e0b",
    "sensible": "#ef4444",
    "autre": "#8b5cf6",
}

# Miroir des CheckConstraint de models.Ticket (ck_tickets_status / ck_tickets_waiting_on) --
# source de vérité applicative unique, validée ici avant même d'atteindre la DB.
VALID_TICKET_STATUSES = {"new", "in_progress", "resolved", "closed"}
VALID_TICKET_WAITING_ON = {"us", "customer"}
