from datetime import datetime

from fpdf import FPDF

AUTHOR_LABELS = {"user": "Vous", "ai": "Assistant IA", "sav": "Agent SAV"}


def _safe(value) -> str:
    """fpdf2's core fonts only support Latin-1. Unsupported characters (emoji,
    em-dash, etc.) in user-generated content are replaced with '?' rather than
    crashing the export."""
    if value is None:
        return ""
    return str(value).encode("latin-1", errors="replace").decode("latin-1")


def build_user_data_export_pdf(user, sessions_with_messages: list[dict]) -> bytes:
    """Builds the RGPD Art. 15/20 personal data export as a PDF.

    `sessions_with_messages` is a list of dicts:
    {"id", "title", "status", "date_creation", "messages": [{"auteur", "contenu", "date"}]}
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def line(text: str, size: int = 10, style: str = "") -> None:
        pdf.set_font("Helvetica", style, size)
        pdf.multi_cell(0, 6 if size <= 11 else 10, _safe(text), new_x="LMARGIN", new_y="NEXT")

    line("Export de mes données personnelles", size=16, style="B")
    line(f"SmartTicket - généré le {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
    pdf.ln(4)

    line("Profil", size=12, style="B")
    role_name = user.role.nom_role if user.role else "user"
    for text in [
        f"Nom d'utilisateur : {user.username}",
        f"Email : {user.email}",
        f"Prénom : {user.prenom or '-'}",
        f"Nom : {user.nom or '-'}",
        f"Rôle : {role_name}",
        f"Date de création du compte : {user.date_creation.strftime('%d/%m/%Y') if user.date_creation else '-'}",
    ]:
        line(text)
    pdf.ln(4)

    line(f"Conversations ({len(sessions_with_messages)})", size=12, style="B")
    if not sessions_with_messages:
        line("Aucune conversation.")

    for s in sessions_with_messages:
        pdf.ln(2)
        title = s["title"] or "Nouvelle conversation"
        line(f"#{s['id']} - {title} ({s['status']})", size=11, style="B")
        if not s["messages"]:
            line("Aucun message.", size=9)
        for m in s["messages"]:
            author = AUTHOR_LABELS.get(m["auteur"], m["auteur"])
            line(f"[{m['date'] or '-'}] {author} : {m['contenu']}", size=9)

    return bytes(pdf.output())
