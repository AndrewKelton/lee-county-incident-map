import io
import datetime
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    Table, TableStyle, HRFlowable,
)

_NAVY  = colors.HexColor("#1e3a5f")
_BLUE  = "#2563eb"
_LIGHT = colors.HexColor("#f0f4f8")
_RULE  = colors.HexColor("#ddd")


def _parse_date(inc):
    d = inc.get("occuredDate")
    if not d:
        return None
    try:
        return datetime.datetime.fromisoformat(d.replace(" ", "T")[:19])
    except Exception:
        return None


def _bar_chart(nature_counts):
    """Horizontal bar chart — incident counts by type (top 12)."""
    items = sorted(nature_counts.items(), key=lambda x: x[1], reverse=True)[:12]
    labels = [k.title() for k, _ in items]
    vals = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(7, max(2.5, len(labels) * 0.38)))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    bars = ax.barh(labels[::-1], vals[::-1], color=_BLUE, edgecolor="none", height=0.6)
    ax.set_xlabel("Incident Count", fontsize=9)
    ax.set_title("Incidents by Type", fontsize=11, fontweight="bold", pad=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=8)

    for bar, val in zip(bars, vals[::-1]):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(val), va="center", ha="left", fontsize=8, color="#333",
        )

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _line_chart(incidents, days):
    """Line chart — daily incident counts over the selected period."""
    end = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    start = end - datetime.timedelta(days=days)

    bucket = Counter()
    for inc in incidents:
        d = _parse_date(inc)
        if d:
            bucket[d.date()] += 1

    all_dates = [start.date() + datetime.timedelta(days=i) for i in range(days + 1)]
    all_vals  = [bucket.get(d, 0) for d in all_dates]

    fig, ax = plt.subplots(figsize=(7, 2.6))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    ax.plot(all_dates, all_vals, color=_BLUE, linewidth=1.8,
            marker="o", markersize=4, markerfacecolor="#1d4ed8")
    ax.fill_between(all_dates, all_vals, alpha=0.12, color=_BLUE)
    ax.set_title("Daily Incident Count", fontsize=11, fontweight="bold", pad=10)
    ax.set_ylabel("Count", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=7)

    locator = mdates.DayLocator() if days <= 14 else mdates.WeekdayLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    fig.autofmt_xdate(rotation=30)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_pdf(incidents, bounds, days):
    """Assemble and return a BytesIO PDF for the given filtered incidents."""
    buf = io.BytesIO()
    styles = getSampleStyleSheet()

    title_s = ParagraphStyle(
        "RTitle", parent=styles["Title"],
        fontSize=18, textColor=_NAVY, spaceAfter=4,
    )
    sub_s = ParagraphStyle(
        "RSub", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#555"), spaceAfter=2,
    )
    h2_s = ParagraphStyle(
        "RH2", parent=styles["Heading2"],
        fontSize=12, textColor=_NAVY, spaceBefore=14, spaceAfter=6,
    )
    footer_s = ParagraphStyle(
        "RFooter", parent=styles["Normal"],
        fontSize=7.5, textColor=colors.HexColor("#888"),
    )

    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.85 * inch,  bottomMargin=0.85 * inch,
    )

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    nature_counts = Counter(
        (inc.get("nature") or "Unknown").strip() for inc in incidents
    )
    most_common  = nature_counts.most_common(1)[0][0].title() if nature_counts else "N/A"
    days_label   = f"Last {days} day{'s' if days != 1 else ''}"

    story = []

    # Title block
    story.append(Paragraph("Lee County Incident Report", title_s))
    story.append(Paragraph(
        f"Generated: {now.strftime('%B %d, %Y at %H:%M UTC')} &nbsp;·&nbsp; Period: {days_label}",
        sub_s,
    ))
    story.append(Paragraph(
        f"Viewport: N {bounds['north']:.4f}° &nbsp; S {bounds['south']:.4f}° &nbsp;"
        f" E {bounds['east']:.4f}° &nbsp; W {bounds['west']:.4f}°",
        sub_s,
    ))
    story.append(Spacer(1, 0.1 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=_RULE, spaceAfter=10))

    # Summary stats
    story.append(Paragraph("Summary", h2_s))
    stat_data = [
        ["Total Incidents", "Most Common Type", "Period", "Data Source"],
        [str(len(incidents)), most_common, days_label, "LCSO Public Log"],
    ]
    stat_tbl = Table(stat_data, colWidths=[1.5*inch, 2*inch, 1.3*inch, 1.9*inch])
    stat_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("FONTSIZE",      (0, 1), (-1, 1), 12),
        ("FONTNAME",      (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0, 1), (-1, 1), _NAVY),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND",    (0, 1), (-1, 1), _LIGHT),
        ("GRID",          (0, 0), (-1, -1), 0.5, _RULE),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(stat_tbl)
    story.append(Spacer(1, 0.1 * inch))

    # Bar chart
    story.append(Paragraph("Incidents by Type", h2_s))
    story.append(Image(_bar_chart(nature_counts), width=6.5*inch, height=3.4*inch))
    story.append(Spacer(1, 0.05 * inch))

    # Line chart
    story.append(Paragraph("Daily Incident Trend", h2_s))
    story.append(Image(_line_chart(incidents, days), width=6.5*inch, height=2.5*inch))
    story.append(Spacer(1, 0.1 * inch))

    # Breakdown table
    story.append(Paragraph("Incident Type Breakdown", h2_s))
    total    = len(incidents)
    tbl_data = [["Incident Type", "Count", "% of Total"]]
    for nature, count in nature_counts.most_common():
        pct = f"{100 * count / total:.1f}%" if total > 0 else "—"
        tbl_data.append([nature.title(), str(count), pct])

    breakdown = Table(tbl_data, colWidths=[3.6*inch, 1.4*inch, 1.7*inch])
    breakdown.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, _LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, _RULE),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(breakdown)

    # Footer
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_RULE))
    story.append(Spacer(1, 0.07 * inch))
    story.append(Paragraph(
        "Data sourced from the Lee County Sheriff's Office public incident log. "
        "Incidents are published with a 48-hour delay. "
        "Only geocoded incidents (~55–60% of total) are included in viewport-filtered reports.",
        footer_s,
    ))

    doc.build(story)
    buf.seek(0)
    return buf
