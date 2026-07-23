import datetime
import io as _io

import matplotlib

matplotlib.use("Agg")  # headless backend — no display server, safe in a container
import matplotlib.pyplot as plt
from fpdf import FPDF


def _render_curve_png(curve: list[dict]) -> bytes:
    dates = [datetime.date.fromisoformat(p["date"][:10]) for p in curve]
    values = [p["value"] for p in curve]

    fig, ax = plt.subplots(figsize=(9, 3.5), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.plot(dates, values, color="#F59E0B", linewidth=1.8)
    ax.axhline(y=1.0, color="black", alpha=0.3, linestyle=":", linewidth=1)
    ax.grid(color="black", alpha=0.08)
    for spine in ax.spines.values():
        spine.set_color((0, 0, 0, 0.2))
    ax.tick_params(colors="#111111", labelsize=8)
    fig.tight_layout()

    buf = _io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _render_allocation_png(holdings_by_category: dict) -> bytes:
    colors = ["#F59E0B", "#FCD34D", "#B45309", "#78350F"]

    fig, ax = plt.subplots(figsize=(6, 4), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.pie(
        list(holdings_by_category.values()),
        labels=list(holdings_by_category.keys()),
        colors=colors,
        textprops={"color": "#111111"},
    )
    fig.tight_layout()

    buf = _io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def generate_pdf_report(username: str, user: dict, overview: dict) -> bytes:
    """Mirrors pages/1_Overview.py's generate_pdf_report exactly, just fed from
    the /portfolio/overview computation instead of Streamlit session state."""

    profile = overview["profile"]
    curve = overview["curve"]
    holdings_by_category = overview["holdings_by_category"]
    holdings = overview["holdings"]

    curve_img_bytes = _render_curve_png(curve) if curve else None
    alloc_img_bytes = _render_allocation_png(holdings_by_category) if holdings_by_category else None

    # Build PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 12, "AIPRS Portfolio Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 96)
    pdf.cell(0, 5,
        f"Generated for {username}  |  "
        f"{datetime.datetime.now(datetime.timezone.utc).strftime('%d %B %Y, %H:%M UTC')}",
        new_x="LMARGIN", new_y="NEXT", align="C",
    )
    pdf.ln(4)
    pdf.set_draw_color(217, 119, 6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Investor Profile
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, "Investor Profile", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    profile_rows = [
        ("Risk Profile", overview["risk_profile"]),
        ("Age", str(profile["age"])),
        ("Annual Income Range", str(profile["income_range"])),
        ("Investment Horizon", str(profile["investment_horizon"])),
        ("Experience Level", str(profile["experience"])),
        ("Primary Goal", str(profile["goals"])),
        ("Risk Tolerance Score", f"{profile['risk_tolerance']} / 10"),
    ]
    for label, value in profile_rows:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(90, 90, 96)
        pdf.cell(90, 7, label)
        pdf.set_text_color(17, 17, 17)
        pdf.cell(90, 7, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(217, 119, 6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Portfolio Metrics
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, f"Portfolio Metrics  ({overview['metrics_source']})", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    metric_cols = [
        ("Total Return (1Y)", f"{overview['total_return']:.2%}"),
        ("Annualised Volatility", f"{overview['ann_vol']:.2%}"),
        ("Sharpe Ratio", f"{overview['sharpe']:.2f}"),
    ]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(90, 90, 96)
    for label, _ in metric_cols:
        pdf.cell(63, 6, label)
    pdf.ln()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(17, 17, 17)
    for _, value in metric_cols:
        pdf.cell(63, 9, value)
    pdf.ln(12)
    pdf.set_draw_color(217, 119, 6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Equity curve
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, "Portfolio Performance (1Y)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    if curve_img_bytes:
        pdf.image(_io.BytesIO(curve_img_bytes), x=10, w=190)
        pdf.ln(1)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(90, 90, 96)
        pdf.cell(0, 5, f"Figure: Growth of your portfolio over the past year ({overview['metrics_source']}).",
                  new_x="LMARGIN", new_y="NEXT", align="C")
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(90, 90, 96)
        pdf.cell(0, 8, "Chart unavailable - market data could not be fetched.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(217, 119, 6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Asset Allocation
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, "Your Asset Allocation", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    if alloc_img_bytes:
        pdf.image(_io.BytesIO(alloc_img_bytes), x=30, w=150)
        pdf.ln(1)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(90, 90, 96)
        pdf.cell(0, 5, "Figure: Breakdown of your entered holdings by asset class.",
                  new_x="LMARGIN", new_y="NEXT", align="C")
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(90, 90, 96)
        pdf.multi_cell(0, 6,
            "No holdings entered yet, so an allocation breakdown isn't available. "
            "Add your holdings on the Overview page, or visit AI Recommendations "
            "for a personalized suggested allocation.")
    pdf.ln(4)

    # Holdings
    if holdings:
        pdf.set_draw_color(217, 119, 6)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(245, 158, 11)
        pdf.cell(0, 8, "Your Holdings", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(90, 90, 96)
        pdf.cell(80, 7, "Ticker")
        pdf.cell(60, 7, "Market")
        pdf.cell(50, 7, "Weight", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for h in holdings:
            pdf.set_text_color(17, 17, 17)
            pdf.cell(80, 7, h["ticker"])
            pdf.cell(60, 7, h.get("market", "US"))
            pdf.cell(50, 7, f"{h['weight']:.1f}%", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Disclaimer page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, "Legal Disclaimer", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 64)
    pdf.multi_cell(0, 6,
        "AIPRS is an academic Final Year Project built for research and educational demonstration. "
        "It is not a licensed financial advisory service, investment platform, or brokerage, and is "
        "not regulated by any financial authority. All outputs in this report - including portfolio "
        "metrics, performance charts, asset allocations, and any recommendations - are produced for "
        "educational and demonstration purposes only. They do not constitute financial advice or "
        "regulated financial guidance. AIPRS and its developers accept no responsibility or liability "
        "whatsoever for any financial loss arising from actions taken based on anything contained in "
        "this report. Always consult a qualified and licensed financial advisor before making any "
        "investment decisions.\n\n"
        "AI-Powered Portfolio Recommendation System (AIPRS)  |  Academic Final Year Project  |  "
        "aiprs.support@gmail.com"
    )

    return bytes(pdf.output())
