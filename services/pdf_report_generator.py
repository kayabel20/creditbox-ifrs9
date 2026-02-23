"""
Professional IFRS 9 PDF Report Generator

Generates a formatted PDF report with:
- Executive Summary with intelligent interpretation
- Portfolio Health Assessment & Recommendations
- Stage Distribution
- Risk Grade Analysis
- Dual Provision Comparison
- Sensitivity Analysis
- Vintage Analysis
- Loss Forecast & Liquidity
- Methodology Notes
- Regulatory Rules Used

Uses fpdf2 library.
"""
import io
from datetime import date
from typing import Dict, Any, List
from fpdf import FPDF


class IFRS9Report(FPDF):
    """Custom PDF class with headers/footers for IFRS 9 reports."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, f"IFRS 9 Provision Report | {self.config.get('institution_name', '')} | {self.config.get('reporting_date', '')}", 0, 1, 'L')
        self.set_draw_color(41, 128, 185)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | IFRS 9 Dual Provisioning Platform v3.0 | CreditBox', 0, 0, 'C')

    def section_title(self, title: str):
        self.ln(4)
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(41, 128, 185)
        self.cell(0, 10, title, 0, 1, 'L')
        self.set_draw_color(41, 128, 185)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def sub_title(self, title: str):
        self.ln(2)
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(50, 50, 50)
        self.cell(0, 8, title, 0, 1, 'L')
        self.set_text_color(0, 0, 0)

    def body_text(self, text: str):
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def key_value(self, key: str, value: str):
        self.set_font('Helvetica', 'B', 10)
        self.cell(80, 6, key, 0, 0, 'L')
        self.set_font('Helvetica', '', 10)
        self.cell(0, 6, value, 0, 1, 'L')

    def table_header(self, cols: List[str], widths: List[int]):
        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(41, 128, 185)
        self.set_text_color(255, 255, 255)
        for col, w in zip(cols, widths):
            self.cell(w, 7, col, 1, 0, 'C', True)
        self.ln()
        self.set_text_color(0, 0, 0)

    def table_row(self, values: List[str], widths: List[int], fill: bool = False):
        self.set_font('Helvetica', '', 9)
        if fill:
            self.set_fill_color(240, 245, 250)
        for val, w in zip(values, widths):
            self.cell(w, 6, val, 1, 0, 'C', fill)
        self.ln()

    def highlight_box(self, text: str, color: str = "blue"):
        colors = {
            "blue": (41, 128, 185),
            "green": (39, 174, 96),
            "red": (231, 76, 60),
            "orange": (243, 156, 18),
        }
        r, g, b = colors.get(color, (41, 128, 185))
        self.set_fill_color(r, g, b)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 11)
        self.cell(0, 10, f"  {text}", 0, 1, 'L', True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def bullet(self, text: str, indent: int = 5):
        """Print a bullet point."""
        self.set_font('Helvetica', 'B', 10)
        self.cell(indent, 5, '-', 0, 0)
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def recommendation_box(self, title: str, text: str, priority: str = "P1"):
        """Print a colored recommendation box."""
        colors = {"P0": (231, 76, 60), "P1": (243, 156, 18), "P2": (41, 128, 185)}
        r, g, b = colors.get(priority, (41, 128, 185))
        self.set_fill_color(r, g, b)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 9)
        self.cell(0, 7, f"  [{priority}] {title}", 0, 1, 'L', True)
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', '', 9)
        self.set_fill_color(250, 250, 250)
        self.multi_cell(0, 5, text, fill=True)
        self.ln(2)


def _generate_interpretation(config, results, summary, sensitivity, vintage, forecast, cohort=None):
    """
    Generate intelligent executive interpretation and recommendations
    based on the actual portfolio numbers.
    """
    cs = config.get('currency_symbol', '')
    total_balance = results.get('total_balance', 0)
    total_ead = results.get('total_ead', 0)
    total_collateral = results.get('total_security', 0)
    ifrs9_total = results.get('ifrs9_total', 0)
    reg_total = results.get('regulatory_total', 0)
    gap = results.get('gap', 0)
    total_loans = results.get('total_loans', 0)
    coverage = summary.get('overall_coverage_ratio', 0)

    by_stage = summary.get('by_stage', {})
    stage1 = by_stage.get(1, {})
    stage2 = by_stage.get(2, {})
    stage3 = by_stage.get(3, {})

    s1_pct = stage1.get('balance_pct', 0)
    s2_pct = stage2.get('balance_pct', 0)
    s3_pct = stage3.get('balance_pct', 0)
    s3_count = stage3.get('count', 0)
    s3_balance = stage3.get('balance', 0)
    s3_coverage = stage3.get('coverage_ratio', 0)

    findings = []
    recommendations = []

    # ── 1. Provision Status ──
    gap_pct = abs(gap / ifrs9_total * 100) if ifrs9_total > 0 else 0
    if gap > 0:
        findings.append(
            f"The institution is UNDER-PROVISIONED by {cs} {abs(gap):,.0f} ({gap_pct:.1f}%). "
            f"IFRS 9 ECL ({cs} {ifrs9_total:,.0f}) falls short of regulatory requirements "
            f"({cs} {reg_total:,.0f}). The regulatory provision must be used as the minimum."
        )
        if gap_pct > 20:
            recommendations.append(("P0", "Immediate Provision Top-Up Required",
                f"Book an additional {cs} {abs(gap):,.0f} in provisions immediately to reach "
                f"regulatory compliance. A gap of {gap_pct:.1f}% represents material under-provisioning "
                f"that would be flagged in a regulatory examination."))
        else:
            recommendations.append(("P1", "Provision Top-Up Needed",
                f"Book an additional {cs} {abs(gap):,.0f} to close the {gap_pct:.1f}% gap. "
                f"While the shortfall is manageable, it should be addressed before the next reporting period."))
    else:
        findings.append(
            f"The institution is COMPLIANT. IFRS 9 ECL ({cs} {ifrs9_total:,.0f}) exceeds "
            f"regulatory requirements ({cs} {reg_total:,.0f}) by {gap_pct:.1f}%. "
            f"No provision top-up is needed."
        )

    # ── 2. Stage Concentration ──
    if s3_pct > 0.50:
        findings.append(
            f"CRITICAL: {s3_pct:.0%} of the outstanding balance ({cs} {s3_balance:,.0f}) is in Stage 3 "
            f"(credit-impaired/defaulted). This represents {s3_count} loans. A healthy portfolio should "
            f"have Stage 3 below 10-15% of the book. This level of NPL concentration indicates systemic "
            f"portfolio distress."
        )
        recommendations.append(("P0", "Aggressive Write-Off & Recovery Program",
            f"Loans in Stage 3 with DPD > 360 days should be written off per CBK guidelines. "
            f"Establish a dedicated recovery unit for the {s3_count} defaulted loans. "
            f"Consider bulk sale of irrecoverable accounts to clean the book."))
        recommendations.append(("P0", "Tighten Underwriting Standards",
            f"With {s3_pct:.0%} of the book defaulted, new loan origination standards need immediate review. "
            f"Implement stricter credit scoring cutoffs, reduce maximum loan sizes, and add mandatory "
            f"collateral requirements for high-risk segments."))
    elif s3_pct > 0.20:
        findings.append(
            f"Stage 3 concentration is elevated at {s3_pct:.0%} of the book ({cs} {s3_balance:,.0f}). "
            f"While not critical, this exceeds the 10-15% benchmark for healthy MFB/Bank portfolios."
        )
        recommendations.append(("P1", "Enhance Collections & Reduce NPLs",
            f"Target the {s3_count} Stage 3 loans with intensified collection efforts. "
            f"Set a 90-day action plan to reduce Stage 3 below 15% of the book."))
    elif s3_pct > 0.10:
        findings.append(
            f"Stage 3 is at {s3_pct:.0%} of the book - within acceptable range but should be monitored."
        )
    else:
        findings.append(
            f"Stage distribution is healthy: Stage 1 at {s1_pct:.0%}, Stage 2 at {s2_pct:.0%}, "
            f"Stage 3 at {s3_pct:.0%}. This indicates sound credit risk management."
        )

    # ── 3. Stage 2 Migration Risk ──
    if s2_pct > 0.15:
        findings.append(
            f"Stage 2 (SICR) loans represent {s2_pct:.0%} of the book. These are at risk of migrating "
            f"to Stage 3 if not actively managed. High Stage 2 is an early warning signal."
        )
        recommendations.append(("P1", "Stage 2 Migration Prevention",
            f"Implement proactive engagement with Stage 2 borrowers: early collection calls, "
            f"restructuring offers where appropriate, and SMS payment reminders. "
            f"Monitor weekly for migration to Stage 3."))

    # ── 4. Collateral Assessment ──
    if total_collateral > 0:
        collateral_ratio = total_collateral / total_balance if total_balance > 0 else 0
        if collateral_ratio > 10:
            findings.append(
                f"Collateral coverage is extremely high at {collateral_ratio:.0f}x the outstanding balance "
                f"({cs} {total_collateral:,.0f} collateral vs {cs} {total_balance:,.0f} balance). This is "
                f"suppressing LGD and reducing ECL. However, if collateral valuations are stale or "
                f"assets are illiquid, the actual ECL exposure could be significantly higher."
            )
            recommendations.append(("P1", "Independent Collateral Valuation Audit",
                f"Commission independent revaluation of all collateral assets, particularly for "
                f"Stage 3 loans. Verify that {cs} {total_collateral:,.0f} in pledged assets is "
                f"realizable. Stale or inflated valuations create hidden ECL exposure."))
        elif collateral_ratio > 2:
            findings.append(
                f"Collateral coverage is strong at {collateral_ratio:.1f}x outstanding balance."
            )
        elif collateral_ratio > 0:
            findings.append(
                f"Collateral coverage is {collateral_ratio:.1f}x - adequate but not excessive."
            )

    # ── 5. EAD vs Balance Check ──
    if total_balance > 0:
        ead_ratio = total_ead / total_balance
        if ead_ratio > 3:
            findings.append(
                f"EAD ({cs} {total_ead:,.0f}) is {ead_ratio:.1f}x the outstanding balance "
                f"({cs} {total_balance:,.0f}). This significant gap suggests large accrued interest "
                f"or future interest components are inflating exposure. Verify that accrued interest "
                f"data in the source file represents current period only, not cumulative."
            )
            recommendations.append(("P2", "Verify EAD Input Data",
                f"Review the accrued interest and outstanding balance columns in the source data. "
                f"If accrued interest is cumulative rather than current period, EAD is overstated "
                f"and ECL will be higher than necessary."))

    # ── 6. Coverage Ratio Assessment ──
    if coverage < 0.05:
        findings.append(
            f"Overall coverage ratio is low at {coverage:.2%}. For a portfolio with "
            f"{s3_pct:.0%} Stage 3 concentration, this suggests collateral is significantly reducing "
            f"loss expectations, or the portfolio has data quality issues."
        )
    elif coverage > 0.30:
        findings.append(
            f"Overall coverage ratio is {coverage:.2%}, which is conservative and prudent."
        )

    # ── 7. Sensitivity Insights ──
    if sensitivity:
        severe = [s for s in sensitivity.get('combined', []) if 'Severe' in s.get('scenario', '')]
        if severe:
            s = severe[0]
            stress_ecl = s['ecl']
            stress_change = s['change_pct']
            findings.append(
                f"Under severe stress (PD +50%, LGD +30%), ECL would increase to "
                f"{cs} {stress_ecl:,.0f} ({stress_change:+.1%} from base). "
                f"Management should consider holding a buffer above the base ECL."
            )
            buffer_amount = stress_ecl - ifrs9_total
            if buffer_amount > 0:
                recommendations.append(("P2", "Consider Management Overlay Buffer",
                    f"Under severe stress, ECL increases by {cs} {buffer_amount:,.0f}. "
                    f"Consider holding a management overlay of 10-20% above base ECL "
                    f"({cs} {ifrs9_total * 0.1:,.0f} - {cs} {ifrs9_total * 0.2:,.0f}) as a prudential buffer."))

    # ── 8. Vintage Data Quality ──
    if vintage and vintage.get('by_vintage'):
        vintages = vintage['by_vintage']
        if len(vintages) == 1 and vintages[0].get('vintage', '').startswith('1970'):
            findings.append(
                "Vintage analysis shows all loans grouped under 1970-01, indicating the disbursement "
                "date column contains Excel serial numbers that were not properly parsed. Vintage "
                "analysis is not usable until disbursement dates are correctly formatted in the source data."
            )
            recommendations.append(("P1", "Fix Disbursement Date Format in Source Data",
                "The disbursement date column appears to contain Excel date serial numbers instead "
                "of proper dates. Re-export the data with dates formatted as YYYY-MM-DD or DD/MM/YYYY "
                "for accurate vintage cohort analysis."))
        else:
            # Find worst performing vintage
            worst = max(vintages, key=lambda v: v.get('par_30_pct', 0))
            if worst.get('par_30_pct', 0) > 0.30:
                findings.append(
                    f"Worst performing vintage: {worst['vintage']} with {worst['par_30_pct']:.0%} PAR 30+ "
                    f"and avg DPD of {worst['avg_dpd']:.0f} days. Investigate underwriting standards "
                    f"and market conditions during this origination period."
                )

    # ── 9. Regulatory Rule Gap Detection ──
    rules = config.get('regulatory_rules', [])
    if rules:
        sorted_rules = sorted(rules, key=lambda r: r.get('dpd_min', 0))
        for i in range(len(sorted_rules) - 1):
            current_max = sorted_rules[i].get('dpd_max', 0)
            next_min = sorted_rules[i + 1].get('dpd_min', 0)
            if next_min - current_max > 1:
                gap_start = current_max + 1
                gap_end = next_min - 1
                findings.append(
                    f"WARNING: Regulatory rule gap detected. DPD range {gap_start}-{gap_end} "
                    f"is not covered by any classification rule. Loans in this range will default "
                    f"to 1% provision, which may significantly under-provision delinquent accounts."
                )
                recommendations.append(("P0", f"Fix Regulatory Rule Gap (DPD {gap_start}-{gap_end})",
                    f"Add or adjust classification rules to cover DPD {gap_start}-{gap_end}. "
                    f"Standard CBK guidelines: Normal 0-30, Watch 31-90, Substandard 91-180, "
                    f"Doubtful 181-360, Loss 361+. No gaps should exist between classifications."))

    # ── 10. Loss Forecast Insight ──
    if forecast and forecast.get('summary'):
        total_loss = forecast['summary'].get('total_expected_loss', 0)
        if total_loss > 0 and total_balance > 0:
            loss_to_book = total_loss / total_balance
            findings.append(
                f"6-month expected loss: {cs} {total_loss:,.0f} ({loss_to_book:.1%} of current book). "
                f"Declining monthly losses indicate the portfolio is naturally amortizing."
            )

    # ── 11. Product-Specific Insights ──
    if cohort:
        problem_products = cohort.get('problem_products', [])
        healthy_products = cohort.get('healthy_products', [])

        if problem_products:
            problem_names = [p['product'] for p in problem_products]
            problem_balance = sum(p['balance'] for p in problem_products)
            problem_pct = problem_balance / total_balance if total_balance > 0 else 0
            findings.append(
                f"PRODUCT DRILL-DOWN: {len(problem_products)} product(s) are distressed: "
                f"{', '.join(problem_names)}. These represent {cs} {problem_balance:,.0f} "
                f"({problem_pct:.0%} of book). The portfolio distress is concentrated in specific "
                f"products, not systemic across the entire book."
            )
            for p in problem_products:
                recommendations.append(("P0" if p['par_90_pct'] > 0.50 else "P1",
                    f"Product: {p['product']} ({p['count']} loans, {cs} {p['balance']:,.0f})",
                    p['recommendation']))

        if healthy_products:
            healthy_names = [p['cohort'] for p in healthy_products[:5]]
            healthy_balance = sum(p['balance'] for p in healthy_products)
            findings.append(
                f"HEALTHY CORE: {len(healthy_products)} product(s) are performing well with <5% PAR30: "
                f"{', '.join(healthy_names)}. These represent {cs} {healthy_balance:,.0f} "
                f"of the book. Focus growth efforts on these products."
            )

        # Secured vs Unsecured insight
        by_security = cohort.get('by_security', [])
        if len(by_security) == 2:
            secured = next((s for s in by_security if s['cohort'] == 'Secured'), None)
            unsecured = next((s for s in by_security if s['cohort'] == 'Unsecured'), None)
            if secured and unsecured:
                if unsecured['par_90_pct'] > secured['par_90_pct'] * 1.5:
                    findings.append(
                        f"Unsecured loans have significantly worse performance: "
                        f"PAR90 {unsecured['par_90_pct']:.0%} vs {secured['par_90_pct']:.0%} for secured. "
                        f"Consider tightening unsecured lending criteria or requiring collateral."
                    )
                elif secured['par_90_pct'] > unsecured['par_90_pct'] * 1.5:
                    findings.append(
                        f"Secured loans paradoxically have worse performance: "
                        f"PAR90 {secured['par_90_pct']:.0%} vs {unsecured['par_90_pct']:.0%} for unsecured. "
                        f"This may indicate that collateral gives false confidence in underwriting, "
                        f"or that secured products attract riskier borrowers."
                    )

    return findings, recommendations


def generate_pdf_report(
    config: Dict[str, Any],
    results: Dict[str, Any],
    summary: Dict[str, Any],
    sensitivity: Dict[str, Any] = None,
    vintage: Dict[str, Any] = None,
    forecast: Dict[str, Any] = None,
    cohort: Dict[str, Any] = None,
) -> bytes:
    """
    Generate a comprehensive IFRS 9 PDF report.

    Returns:
        PDF content as bytes, ready for download.
    """
    cs = config.get('currency_symbol', '')
    pdf = IFRS9Report(config)
    pdf.alias_nb_pages()
    pdf.add_page()

    # ============================================================
    # COVER / EXECUTIVE SUMMARY
    # ============================================================
    pdf.set_font('Helvetica', 'B', 22)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(0, 15, 'IFRS 9 Dual Provisioning Report', 0, 1, 'C')
    pdf.set_font('Helvetica', '', 14)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, config.get('institution_name', ''), 0, 1, 'C')
    pdf.cell(0, 8, f"{config.get('country_name', '')} | {config.get('regulator', '')}", 0, 1, 'C')
    pdf.cell(0, 8, f"Reporting Date: {config.get('reporting_date', '')}", 0, 1, 'C')
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)

    # Status box
    gap = results.get('gap', 0)
    if gap > 0:
        pdf.highlight_box("STATUS: UNDER-PROVISIONED - Use Regulatory Provision", "red")
    else:
        pdf.highlight_box("STATUS: COMPLIANT - IFRS 9 Provision Exceeds Regulatory", "green")

    # Key metrics
    pdf.section_title("1. Executive Summary")

    pdf.key_value("Institution:", config.get('institution_name', ''))
    pdf.key_value("License Type:", config.get('license_type', ''))
    pdf.key_value("Country:", f"{config.get('country_name', '')} ({config.get('regulator', '')})")
    pdf.key_value("Reporting Date:", str(config.get('reporting_date', '')))
    pdf.ln(3)

    pdf.key_value("Total Loans:", f"{results.get('total_loans', 0):,}")
    pdf.key_value("Total Outstanding Balance:", f"{cs} {results.get('total_balance', 0):,.2f}")
    pdf.key_value("Total EAD:", f"{cs} {results.get('total_ead', 0):,.2f}")
    pdf.key_value("Total Collateral:", f"{cs} {results.get('total_security', 0):,.2f}")
    pdf.ln(3)

    pdf.key_value("IFRS 9 ECL Provision:", f"{cs} {results.get('ifrs9_total', 0):,.2f}")
    pdf.key_value("Regulatory Provision:", f"{cs} {results.get('regulatory_total', 0):,.2f}")
    pdf.key_value("Gap (Reg - IFRS 9):", f"{cs} {gap:,.2f}")
    pdf.key_value("Final Provision (Higher-of):", f"{cs} {results.get('final_total', 0):,.2f}")
    pdf.key_value("Overall Coverage Ratio:", f"{summary.get('overall_coverage_ratio', 0):.2%}")

    # ============================================================
    # PORTFOLIO HEALTH ASSESSMENT & RECOMMENDATIONS (NEW)
    # ============================================================
    findings, recommendations = _generate_interpretation(
        config, results, summary, sensitivity, vintage, forecast, cohort
    )

    pdf.add_page()
    pdf.section_title("2. Portfolio Health Assessment")

    pdf.sub_title("Key Findings")
    for finding in findings:
        pdf.bullet(finding)

    pdf.ln(3)
    pdf.sub_title("Recommendations")
    if recommendations:
        for priority, title, text in recommendations:
            pdf.recommendation_box(title, text, priority)
    else:
        pdf.body_text("No critical issues identified. Continue monitoring portfolio health.")

    # Overall health score
    pdf.ln(3)
    pdf.sub_title("Portfolio Health Score")

    by_stage = summary.get('by_stage', {})
    s3_pct = by_stage.get(3, {}).get('balance_pct', 0)
    s2_pct = by_stage.get(2, {}).get('balance_pct', 0)
    coverage = summary.get('overall_coverage_ratio', 0)

    # Simple scoring: 100 = perfect, deductions for issues
    score = 100
    if s3_pct > 0.50:
        score -= 40
    elif s3_pct > 0.20:
        score -= 25
    elif s3_pct > 0.10:
        score -= 10
    if s2_pct > 0.20:
        score -= 10
    elif s2_pct > 0.10:
        score -= 5
    if gap > 0:
        gap_pct = abs(gap / max(results.get('ifrs9_total', 1), 1) * 100)
        if gap_pct > 20:
            score -= 20
        elif gap_pct > 5:
            score -= 10
        else:
            score -= 5
    # Rule gaps
    rules = config.get('regulatory_rules', [])
    sorted_rules = sorted(rules, key=lambda r: r.get('dpd_min', 0))
    for i in range(len(sorted_rules) - 1):
        if sorted_rules[i + 1].get('dpd_min', 0) - sorted_rules[i].get('dpd_max', 0) > 1:
            score -= 15
            break

    score = max(0, min(100, score))

    if score >= 80:
        rating = "STRONG"
        color = "green"
    elif score >= 60:
        rating = "ADEQUATE"
        color = "blue"
    elif score >= 40:
        rating = "WEAK"
        color = "orange"
    else:
        rating = "CRITICAL"
        color = "red"

    pdf.highlight_box(f"PORTFOLIO HEALTH: {score}/100 - {rating}", color)

    health_cols = ['Metric', 'Value', 'Benchmark', 'Status']
    health_widths = [50, 40, 40, 40]
    pdf.table_header(health_cols, health_widths)

    s3_status = "Pass" if s3_pct < 0.15 else ("Watch" if s3_pct < 0.30 else "FAIL")
    s2_status = "Pass" if s2_pct < 0.15 else ("Watch" if s2_pct < 0.25 else "FAIL")
    cov_status = "Pass" if coverage > 0.05 else "Low"
    gap_status = "Pass" if gap <= 0 else ("Watch" if abs(gap) / max(results.get('ifrs9_total', 1), 1) < 0.10 else "FAIL")

    pdf.table_row(["Stage 3 Concentration", f"{s3_pct:.1%}", "< 15%", s3_status], health_widths, fill=True)
    pdf.table_row(["Stage 2 Concentration", f"{s2_pct:.1%}", "< 15%", s2_status], health_widths)
    pdf.table_row(["Coverage Ratio", f"{coverage:.2%}", "> 5%", cov_status], health_widths, fill=True)
    pdf.table_row(["Provision Gap", f"{cs}{gap:,.0f}", "<= 0", gap_status], health_widths)

    # ============================================================
    # PRODUCT DRILL-DOWN
    # ============================================================
    if cohort and cohort.get('by_product'):
        pdf.add_page()
        pdf.section_title("3. Product-Level Analysis")
        pdf.body_text(
            "Breakdown by loan product to identify which products are driving portfolio risk "
            "and which form the healthy core of the book."
        )

        prod_cols = ['Product', 'Loans', 'Balance', 'ECL', 'Cov%', 'PAR30', 'PAR90', 'AvgDPD']
        prod_widths = [42, 14, 28, 28, 16, 16, 16, 18]
        pdf.table_header(prod_cols, prod_widths)

        for i, p in enumerate(cohort['by_product']):
            name = p['cohort'][:22]  # truncate long names
            pdf.table_row([
                name,
                f"{p['count']}",
                f"{cs}{p['balance']:,.0f}",
                f"{cs}{p['ecl']:,.0f}",
                f"{p['coverage_ratio']:.1%}",
                f"{p['par_30_pct']:.0%}",
                f"{p['par_90_pct']:.0%}",
                f"{p['avg_dpd']:.0f}",
            ], prod_widths, fill=(i % 2 == 0))

        # Problem products callout
        if cohort.get('problem_products'):
            pdf.ln(5)
            pdf.sub_title("Problem Products (Require Immediate Action)")
            for p in cohort['problem_products']:
                pdf.recommendation_box(
                    f"{p['product']} - {p['count']} loans, {cs} {p['balance']:,.0f}",
                    p['recommendation'],
                    "P0" if p['par_90_pct'] > 0.50 else "P1"
                )

        # Healthy products
        if cohort.get('healthy_products'):
            pdf.ln(3)
            pdf.sub_title("Healthy Products (Growth Candidates)")
            for p in cohort['healthy_products'][:5]:
                pdf.body_text(
                    f"  {p['cohort']}: {p['count']} loans, {cs} {p['balance']:,.0f}, "
                    f"PAR30 {p['par_30_pct']:.0%}, Avg DPD {p['avg_dpd']:.0f} - PERFORMING WELL"
                )

    # ============================================================
    # SECURED vs UNSECURED
    # ============================================================
    if cohort and cohort.get('by_security'):
        pdf.add_page()
        pdf.section_title("4. Secured vs Unsecured Analysis")
        pdf.body_text(
            "Comparison of collateralized vs uncollateralized loan performance. "
            "This helps assess whether collateral requirements are effective in reducing credit risk."
        )

        sec_cols = ['Segment', 'Loans', 'Balance', 'Collateral', 'ECL', 'Cov%', 'PAR30', 'PAR90', 'AvgDPD']
        sec_widths = [22, 14, 25, 25, 25, 15, 15, 15, 15]
        pdf.table_header(sec_cols, sec_widths)

        for i, s in enumerate(cohort['by_security']):
            pdf.table_row([
                s['cohort'],
                f"{s['count']}",
                f"{cs}{s['balance']:,.0f}",
                f"{cs}{s['collateral']:,.0f}",
                f"{cs}{s['ecl']:,.0f}",
                f"{s['coverage_ratio']:.1%}",
                f"{s['par_30_pct']:.0%}",
                f"{s['par_90_pct']:.0%}",
                f"{s['avg_dpd']:.0f}",
            ], sec_widths, fill=(i % 2 == 0))

        pdf.ln(5)

        # Stage distribution within each segment
        pdf.sub_title("Stage Distribution by Security Type")
        seg_stage_cols = ['Segment', 'Stage 1 %', 'Stage 2 %', 'Stage 3 %', 'Avg PD', 'Avg LGD']
        seg_stage_widths = [35, 28, 28, 28, 28, 28]
        pdf.table_header(seg_stage_cols, seg_stage_widths)
        for i, s in enumerate(cohort['by_security']):
            pdf.table_row([
                s['cohort'],
                f"{s['stage_1_pct']:.0%}",
                f"{s['stage_2_pct']:.0%}",
                f"{s['stage_3_pct']:.0%}",
                f"{s['avg_pd']:.2%}",
                f"{s['avg_lgd']:.2%}",
            ], seg_stage_widths, fill=(i % 2 == 0))

    # ============================================================
    # DPD BUCKET BREAKDOWN
    # ============================================================
    if cohort and cohort.get('by_dpd_bucket'):
        pdf.ln(5)
        pdf.section_title("5. DPD Bucket Distribution")
        pdf.body_text(
            "Distribution of loans by days past due bucket, showing how delinquency "
            "is spread across the portfolio."
        )

        dpd_cols = ['DPD Bucket', 'Loans', 'Balance', '% Book', 'ECL', 'Coverage', 'Avg PD']
        dpd_widths = [30, 16, 30, 18, 30, 20, 24]
        pdf.table_header(dpd_cols, dpd_widths)
        for i, b in enumerate(cohort['by_dpd_bucket']):
            pdf.table_row([
                b['cohort'],
                f"{b['count']}",
                f"{cs}{b['balance']:,.0f}",
                f"{b['balance_pct']:.1%}",
                f"{cs}{b['ecl']:,.0f}",
                f"{b['coverage_ratio']:.1%}",
                f"{b['avg_pd']:.2%}",
            ], dpd_widths, fill=(i % 2 == 0))

        # Section number offset for remaining sections
        _sec_offset = 6
    else:
        _sec_offset = 4 if (cohort and cohort.get('by_security')) else 3

    # ============================================================
    # STAGE DISTRIBUTION
    # ============================================================
    pdf.add_page()
    pdf.section_title(f"{_sec_offset}. IFRS 9 Stage Distribution")

    stage_cols = ['Stage', 'Loans', 'Balance', 'EAD', 'ECL', 'Coverage', '% Book']
    stage_widths = [22, 18, 35, 35, 35, 22, 22]
    pdf.table_header(stage_cols, stage_widths)

    for s, d in summary.get('by_stage', {}).items():
        if d['count'] > 0:
            pdf.table_row([
                f"Stage {s}",
                f"{d['count']:,}",
                f"{cs}{d['balance']:,.0f}",
                f"{cs}{d['ead']:,.0f}",
                f"{cs}{d['ecl']:,.0f}",
                f"{d['coverage_ratio']:.2%}",
                f"{d['balance_pct']:.1%}",
            ], stage_widths, fill=(s % 2 == 0))

    pdf.ln(5)

    # Stage explanations
    pdf.sub_title("Staging Criteria")
    pdf.body_text(
        "Stage 1 (Performing): Loans with no significant increase in credit risk. "
        "12-month ECL is recognized. DPD = 0 with no SICR triggers."
    )
    pdf.body_text(
        "Stage 2 (SICR): Loans with significant increase in credit risk since origination. "
        "Lifetime ECL is recognized. Triggers: DPD >= 30, PD deterioration > 100%, "
        "absolute PD exceeds threshold, or restructuring/forbearance."
    )
    pdf.body_text(
        "Stage 3 (Credit-Impaired): Defaulted loans. Lifetime ECL with 100% PD. "
        "Triggers: DPD >= 90 or write-off."
    )

    # ============================================================
    # RISK GRADES
    # ============================================================
    _sec_offset += 1
    pdf.section_title(f"{_sec_offset}. Risk Grade Distribution")

    grade_labels = {"A": "Low Risk", "B": "Medium-Low", "C": "Medium", "D": "Med-High", "E": "High Risk"}
    grade_cols = ['Grade', 'Description', 'Loans', 'Balance', 'ECL', 'Avg PD']
    grade_widths = [15, 30, 20, 38, 38, 28]
    pdf.table_header(grade_cols, grade_widths)

    for g, d in sorted(summary.get('by_risk_grade', {}).items()):
        pdf.table_row([
            g,
            grade_labels.get(g, ''),
            f"{d['count']:,}",
            f"{cs}{d['balance']:,.0f}",
            f"{cs}{d['ecl']:,.0f}",
            f"{d['avg_pd']:.2%}",
        ], grade_widths, fill=(g in ['B', 'D']))

    # ============================================================
    # DUAL PROVISION COMPARISON
    # ============================================================
    pdf.add_page()
    _sec_offset += 1
    pdf.section_title(f"{_sec_offset}. Dual Provision Comparison")

    pdf.body_text(
        "IFRS 9 requires Expected Credit Loss (ECL) provisioning based on forward-looking estimates. "
        "Regulatory provisions follow local prudential guidelines based on DPD classification. "
        "The institution must hold the HIGHER of the two provisions."
    )
    pdf.ln(3)

    comp_cols = ['Measure', 'IFRS 9 ECL', 'Regulatory', 'Gap']
    comp_widths = [45, 45, 45, 45]
    pdf.table_header(comp_cols, comp_widths)
    pdf.table_row([
        'Total Provision',
        f"{cs}{results.get('ifrs9_total', 0):,.0f}",
        f"{cs}{results.get('regulatory_total', 0):,.0f}",
        f"{cs}{gap:,.0f}",
    ], comp_widths)

    ifrs9_total = results.get('ifrs9_total', 1)
    gap_pct = abs(gap / ifrs9_total * 100) if ifrs9_total > 0 else 0
    pdf.ln(3)
    if gap > 0:
        pdf.body_text(
            f"The IFRS 9 provision is {gap_pct:.1f}% LOWER than regulatory requirements. "
            f"The institution should use the regulatory provision of {cs} {results.get('regulatory_total', 0):,.2f}."
        )
    else:
        pdf.body_text(
            f"The IFRS 9 provision EXCEEDS regulatory requirements by {gap_pct:.1f}%. "
            f"The institution should use the IFRS 9 provision of {cs} {results.get('ifrs9_total', 0):,.2f}."
        )

    # ============================================================
    # SENSITIVITY ANALYSIS
    # ============================================================
    if sensitivity:
        pdf.add_page()
        _sec_offset += 1
        pdf.section_title(f"{_sec_offset}. Sensitivity Analysis")
        pdf.body_text(
            "Sensitivity analysis shows how ECL changes under stressed PD and LGD assumptions. "
            "This helps management understand the range of potential outcomes and set appropriate buffers."
        )

        # PD Shocks
        pdf.sub_title(f"{_sec_offset}.1 PD Sensitivity")
        pd_cols = ['Scenario', 'PD Factor', 'ECL', 'Change', 'Change %']
        pd_widths = [30, 25, 40, 40, 30]
        pdf.table_header(pd_cols, pd_widths)
        for i, shock in enumerate(sensitivity.get('pd_shocks', [])):
            pdf.table_row([
                shock['scenario'],
                f"{shock['pd_multiplier']:.2f}x",
                f"{cs}{shock['ecl']:,.0f}",
                f"{cs}{shock['change_from_base']:,.0f}",
                f"{shock['change_pct']:+.1%}",
            ], pd_widths, fill=(i % 2 == 0))

        pdf.ln(5)

        # LGD Shocks
        pdf.sub_title(f"{_sec_offset}.2 LGD Sensitivity")
        lgd_cols = ['Scenario', 'LGD Factor', 'ECL', 'Change', 'Change %']
        lgd_widths = [30, 25, 40, 40, 30]
        pdf.table_header(lgd_cols, lgd_widths)
        for i, shock in enumerate(sensitivity.get('lgd_shocks', [])):
            pdf.table_row([
                shock['scenario'],
                f"{shock['lgd_multiplier']:.2f}x",
                f"{cs}{shock['ecl']:,.0f}",
                f"{cs}{shock['change_from_base']:,.0f}",
                f"{shock['change_pct']:+.1%}",
            ], lgd_widths, fill=(i % 2 == 0))

        pdf.ln(5)

        # Combined stress
        pdf.sub_title(f"{_sec_offset}.3 Combined Stress Scenarios")
        comb_cols = ['Scenario', 'PD', 'LGD', 'ECL', 'Change %']
        comb_widths = [60, 20, 20, 40, 28]
        pdf.table_header(comb_cols, comb_widths)
        for i, combo in enumerate(sensitivity.get('combined', [])):
            pdf.table_row([
                combo['scenario'],
                f"{combo['pd_multiplier']:.2f}x",
                f"{combo['lgd_multiplier']:.2f}x",
                f"{cs}{combo['ecl']:,.0f}",
                f"{combo['change_pct']:+.1%}",
            ], comb_widths, fill=(i % 2 == 0))

    # ============================================================
    # VINTAGE ANALYSIS
    # ============================================================
    if vintage and vintage.get('by_vintage'):
        pdf.add_page()
        _sec_offset += 1
        pdf.section_title(f"{_sec_offset}. Vintage Analysis")
        pdf.body_text(
            "Vintage analysis groups loans by origination month to identify which cohorts "
            "are performing well and which are deteriorating. Higher PAR 30+ rates and coverage "
            "ratios in older vintages may indicate systemic underwriting issues."
        )

        vin_cols = ['Vintage', 'Loans', 'Balance', 'ECL', 'Coverage', 'PAR30', 'Avg DPD']
        vin_widths = [25, 18, 35, 35, 22, 22, 22]
        pdf.table_header(vin_cols, vin_widths)

        for i, v in enumerate(vintage['by_vintage']):
            pdf.table_row([
                v['vintage'],
                f"{v['count']:,}",
                f"{cs}{v['balance']:,.0f}",
                f"{cs}{v['ecl']:,.0f}",
                f"{v['coverage_ratio']:.2%}",
                f"{v['par_30_pct']:.0%}",
                f"{v['avg_dpd']:.0f}",
            ], vin_widths, fill=(i % 2 == 0))

    # ============================================================
    # LOSS FORECAST
    # ============================================================
    if forecast and forecast.get('forecasts'):
        pdf.add_page()
        _sec_offset += 1
        pdf.section_title(f"{_sec_offset}. Loss Forecast & Liquidity")

        fc_cols = ['Month', 'Expected Loss', 'Forecast Balance', 'Provision Needed']
        fc_widths = [35, 40, 50, 45]
        pdf.table_header(fc_cols, fc_widths)
        for i, f in enumerate(forecast['forecasts']):
            pdf.table_row([
                f['forecast_date'],
                f"{cs}{f['expected_loss']:,.0f}",
                f"{cs}{f['forecasted_balance']:,.0f}",
                f"{cs}{f['forecasted_provision']:,.0f}",
            ], fc_widths, fill=(i % 2 == 0))

        pdf.ln(5)

        liq = forecast.get('liquidity_recommendation', {})
        if liq:
            pdf.sub_title("Liquidity Recommendation")
            pdf.key_value("Base Reserve (3-month avg):", f"{cs} {liq.get('base_reserve', 0):,.2f}")
            pdf.key_value("Stress Buffer (20%):", f"{cs} {liq.get('stress_buffer', 0):,.2f}")
            pdf.key_value("Regulatory Minimum (10%):", f"{cs} {liq.get('regulatory_minimum', 0):,.2f}")
            pdf.key_value("Total Recommended:", f"{cs} {liq.get('total_recommended', 0):,.2f}")

    # ============================================================
    # METHODOLOGY
    # ============================================================
    pdf.add_page()
    _sec_offset += 1
    pdf.section_title(f"{_sec_offset}. Methodology Notes")

    pdf.sub_title("ECL Formula")
    pdf.body_text("ECL = EAD x LGD x PD x Macro Adjustment x Discount Factor")
    pdf.ln(2)

    pdf.sub_title("Probability of Default (PD)")
    pdf.body_text(
        "Base PD is calculated using a logistic function: PD = 1 / (1 + exp((score - 400) / 100)). "
        "Adjustments are applied for days past due (1x-10x multiplier) and loan vintage/seasoning "
        "(1.5x for new loans, 0.9x for seasoned). Lifetime PD uses marginal approach: "
        "PD_lifetime = 1 - (1 - PD_annual)^remaining_years."
    )

    pdf.sub_title("Loss Given Default (LGD)")
    country_code = config.get('country_code', 'KE')
    from services.dataframe_ecl_engine import get_market_config
    mkt = get_market_config(country_code)
    pdf.body_text(
        f"Unsecured LGD by stage: Stage 1 = {mkt['unsecured_lgd']['stage1']:.0%}, "
        f"Stage 2 = {mkt['unsecured_lgd']['stage2']:.0%}, Stage 3 = {mkt['unsecured_lgd']['stage3']:.0%}. "
        f"Secured LGD: 1 - (Collateral x (1 - {mkt['collateral_haircut']:.0%} haircut) - "
        f"{mkt['recovery_cost_rate']:.0%} recovery costs) / Outstanding, discounted at {mkt['discount_rate']:.0%} EIR. "
        f"LGD floor: {mkt['secured_lgd_floor']:.0%}. Stage 2 cure rate adjustment applied."
    )

    pdf.sub_title("Exposure at Default (EAD)")
    pdf.body_text(
        "EAD = Outstanding Balance + Accrued Interest + Future Interest (Stage 1 only). "
        "Future interest is included for Stage 1 loans only, reflecting amortized cost measurement basis."
    )

    pdf.sub_title("Multi-Scenario Weighting")
    pdf.body_text(
        f"Three macro scenarios are applied: Base ({mkt['macro_scenarios']['BASE']:.2f}x, "
        f"weight {mkt['scenario_weights']['base']:.0%}), "
        f"Upside ({mkt['macro_scenarios']['UPSIDE']:.2f}x, weight {mkt['scenario_weights']['upside']:.0%}), "
        f"Downside ({mkt['macro_scenarios']['DOWNSIDE']:.2f}x, weight {mkt['scenario_weights']['downside']:.0%}). "
        "ECL_final = weighted average across all three scenarios."
    )

    pdf.sub_title("NPV Discounting")
    pdf.body_text(
        f"ECL is discounted to present value using the loan's effective interest rate (or market "
        f"default of {mkt['discount_rate']:.0%}). Stage 1: 12-month horizon. Stage 2/3: remaining loan life."
    )

    # ============================================================
    # REGULATORY RULES
    # ============================================================
    _sec_offset += 1
    pdf.section_title(f"{_sec_offset}. Regulatory Provision Rules Applied")

    rules = config.get('regulatory_rules', [])
    if rules:
        rule_cols = ['Classification', 'DPD Range', 'Rate', 'Collateral Deduct']
        rule_widths = [45, 40, 30, 45]
        pdf.table_header(rule_cols, rule_widths)
        for i, r in enumerate(rules):
            dpd_max = 'max' if r.get('dpd_max', 0) >= 999999 else str(r.get('dpd_max', 0))
            pdf.table_row([
                r.get('name', ''),
                f"{r.get('dpd_min', 0)}-{dpd_max}",
                f"{r.get('rate', 0):.1f}%",
                "Yes" if r.get('collateral_deduction', False) else "No",
            ], rule_widths, fill=(i % 2 == 0))

    # ============================================================
    # DISCLAIMER
    # ============================================================
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 4,
        "DISCLAIMER: This report is generated using standardized IFRS 9 methodology with market-level "
        "parameter defaults. PD models use generic logistic curves and DPD-based adjustments, not institution-specific "
        "calibration. LGD rates are industry benchmarks. For auditor-ready models, parameters should be calibrated "
        "to the institution's actual default and recovery data. This report does not constitute financial advice. "
        f"\n\nGenerated: {date.today()} | IFRS 9 Dual Provisioning Platform v3.0 | CreditBox"
    )

    # Output
    return bytes(pdf.output())
