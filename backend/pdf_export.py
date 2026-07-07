from datetime import datetime

from fpdf import FPDF

AUTHOR_LABELS = {"user": "Vous", "ai": "Assistant IA", "sav": "Agent SAV"}
ALERT_LEVEL_LABELS = {"critical": "CRITIQUE", "warning": "ATTENTION"}


def _safe(value) -> str:
    """fpdf2's core fonts only support Latin-1. Unsupported characters (emoji,
    em-dash, etc.) in user-generated content are replaced with '?' rather than
    crashing the export."""
    if value is None:
        return ""
    return str(value).encode("latin-1", errors="replace").decode("latin-1")


class _Report:
    """Small helper shared by the analytics/monitoring PDF exports: a title +
    period header, KPI lines, alert callouts, and bordered data tables."""

    def __init__(self, title: str, days: int):
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)
        self.pdf.add_page()
        self.line(title, size=16, style="B")
        self.line(f"SmartTicket - généré le {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC - période : {days} derniers jours")
        self.pdf.ln(4)

    def line(self, text: str, size: int = 10, style: str = "") -> None:
        self.pdf.set_font("Helvetica", style, size)
        self.pdf.multi_cell(0, 6 if size <= 11 else 10, _safe(text), new_x="LMARGIN", new_y="NEXT")

    def section(self, title: str) -> None:
        self.pdf.ln(2)
        self.line(title, size=12, style="B")

    def alerts(self, alerts: list[dict]) -> None:
        if not alerts:
            self.line("Aucune alerte : toutes les métriques sont dans les seuils normaux.", size=9)
            return
        for alert in alerts:
            level = ALERT_LEVEL_LABELS.get(alert.get("level"), alert.get("level", ""))
            self.line(f"[{level}] {alert.get('message', '')}", size=9, style="B" if alert.get("level") == "critical" else "")

    def table(self, headers: list[str], rows: list[list], widths: list[int]) -> None:
        if not rows:
            self.line("Aucune donnée sur cette période.", size=9)
            return
        self.pdf.set_font("Helvetica", "B", 9)
        for header, width in zip(headers, widths):
            self.pdf.cell(width, 7, _safe(header), border=1)
        self.pdf.ln(7)
        self.pdf.set_font("Helvetica", "", 9)
        for row in rows:
            for value, width in zip(row, widths):
                self.pdf.cell(width, 6, _safe(value), border=1)
            self.pdf.ln(6)

    def output(self) -> bytes:
        return bytes(self.pdf.output())


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


def build_stats_report_pdf(data: dict, days: int) -> bytes:
    """Builds the business/SAV analytics report (mirrors GET /v1/analytics/stats)."""
    report = _Report("Rapport Analytics - SmartTicket", days)

    report.section("Alertes")
    report.alerts(data.get("alerts", []))

    report.section("Indicateurs clés")
    satisfaction = data.get("satisfaction_score")
    report.line(f"Conversations totales : {data.get('total_sessions', 0)}")
    report.line(f"Taux de résolution IA : {data.get('ai_resolution_rate', 0)}%")
    report.line(f"Transferts vers un agent humain : {data.get('transferred_count', 0)}")
    report.line(f"Score de satisfaction : {f'{satisfaction:.2f}/5' if satisfaction is not None else 'aucune donnée'}")

    report.section("Évolution quotidienne des conversations")
    daily = data.get("daily_messages") or []
    report.table(
        ["Jour", "Messages IA", "Messages humains"],
        [[d.get("name", "-"), d.get("IA", 0), d.get("Humain", 0)] for d in daily],
        [60, 60, 60],
    )

    report.section("Raisons de transfert")
    reasons = data.get("transfer_reasons") or []
    report.table(
        ["Raison", "Nombre"],
        [[r.get("name", "-"), r.get("value", 0)] for r in reasons],
        [100, 80],
    )

    report.section("Agents SAV")
    agents = data.get("sav_agents") or []
    report.table(
        ["Agent", "Conversations traitées"],
        [[a.get("name", "-"), a.get("conversations", 0)] for a in agents],
        [100, 80],
    )

    return report.output()


def build_ai_metrics_report_pdf(data: dict, days: int) -> bytes:
    """Builds the AI monitoring report (mirrors GET /v1/analytics/ai-metrics)."""
    report = _Report("Rapport Monitoring IA - SmartTicket", days)
    if data.get("model_name"):
        report.line(f"Modèle : {data['model_name']}")

    report.section("Alertes")
    report.alerts(data.get("alerts", []))

    report.section("Indicateurs clés")
    latency = data.get("avg_latency_ms")
    kb_score = data.get("kb_score")
    report.line(f"Appels totaux : {data.get('total_calls', 0)}")
    report.line(f"Latence moyenne : {f'{latency}ms' if latency is not None else 'aucune donnée'}")
    report.line(f"Taux d'erreur : {data.get('error_rate', 0)}%")
    report.line(f"Requêtes sans contexte RAG : {data.get('no_context_rate', 0)}%")
    report.line(f"Score de santé de la base de connaissances : {f'{kb_score}/100' if kb_score is not None else 'indisponible (< 5 appels)'}")

    prev_latency, prev_error, prev_no_context = data.get("prev_latency_ms"), data.get("prev_error_rate"), data.get("prev_no_context_rate")
    if prev_latency is not None or prev_error is not None or prev_no_context is not None:
        report.section("Comparaison avec la période précédente")
        if prev_latency is not None:
            report.line(f"Latence : {prev_latency}ms -> {latency}ms")
        if prev_error is not None:
            report.line(f"Taux d'erreur : {prev_error}% -> {data.get('error_rate', 0)}%")
        if prev_no_context is not None:
            report.line(f"Sans contexte RAG : {prev_no_context}% -> {data.get('no_context_rate', 0)}%")

    report.section("Évolution de la latence")
    trend = data.get("latency_trend") or []
    report.table(
        ["Jour", "Latence moyenne (ms)", "Appels"],
        [[t.get("name", "-"), t.get("latence_ms", 0), t.get("appels", 0)] for t in trend],
        [60, 60, 60],
    )

    report.section("Enrichissements de la base de connaissances")
    kb_events = data.get("kb_events") or []
    report.table(
        ["Date", "Chunks ajoutés"],
        [[e.get("date", "-"), e.get("chunks", 0)] for e in kb_events],
        [100, 80],
    )

    return report.output()
