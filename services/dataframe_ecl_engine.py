"""
Standalone IFRS 9 ECL Engine - Works on DataFrames (No Database Required)

This engine mirrors the full ECL service methodology (PD, LGD, EAD, Staging, ECL)
but operates directly on pandas DataFrames. Designed for the customer-facing app
where users upload any portfolio file and get instant IFRS 9 results.

Methodology matches:
- services/pd_service.py (score-to-PD logistic, DPD adjustment, vintage adjustment)
- services/lgd_service.py (unsecured rates by stage, secured with collateral recovery)
- services/ead_service.py (principal + accrued interest + future interest)
- services/staging_service.py (Stage 1/2/3 classification with SICR)
- services/ecl_service.py (ECL = EAD x LGD x PD, multi-scenario, NPV discounting)
- utils/market_config.py (KE/NG country-specific parameters)
"""
import math
import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Dict, Any, Optional


# ============================================================================
# MARKET CONFIGURATIONS (mirrors utils/market_config.py)
# ============================================================================
MARKET_CONFIGS = {
    "KE": {
        "name": "Kenya",
        "regulator": "CBK",
        "dpd_stage2_threshold": 30,
        "dpd_stage3_threshold": 90,
        "relative_pd_threshold": 1.0,
        "absolute_pd_threshold": 0.15,
        "unsecured_lgd": {"stage1": 0.45, "stage2": 0.60, "stage3": 0.80},
        "secured_lgd_floor": 0.10,
        "collateral_haircut": 0.30,
        "recovery_cost_rate": 0.15,
        "cure_rates": {"0-30": 0.85, "31-60": 0.50, "61-90": 0.25, "91-180": 0.10, "180+": 0.05},
        "discount_rate": 0.14,
        "stage1_provision_rate": 0.01,
        "stage2_provision_rate": 0.05,
        "stage3_unsecured_rate": 0.50,
        "stage3_secured_rate": 0.20,
        "macro_scenarios": {"BASE": 1.0, "UPSIDE": 0.85, "DOWNSIDE": 1.25},
        "scenario_weights": {"base": 0.50, "upside": 0.25, "downside": 0.25},
    },
    "NG": {
        "name": "Nigeria",
        "regulator": "CBN",
        "dpd_stage2_threshold": 30,
        "dpd_stage3_threshold": 90,
        "relative_pd_threshold": 1.0,
        "absolute_pd_threshold": 0.20,
        "unsecured_lgd": {"stage1": 0.45, "stage2": 0.60, "stage3": 0.85},
        "secured_lgd_floor": 0.10,
        "collateral_haircut": 0.35,
        "recovery_cost_rate": 0.20,
        "cure_rates": {"0-30": 0.80, "31-60": 0.45, "61-90": 0.20, "91-180": 0.08, "180+": 0.03},
        "discount_rate": 0.18,
        "stage1_provision_rate": 0.01,
        "stage2_provision_rate": 0.05,
        "stage3_unsecured_rate": 0.60,
        "stage3_secured_rate": 0.25,
        "macro_scenarios": {"BASE": 1.0, "UPSIDE": 0.85, "DOWNSIDE": 1.30},
        "scenario_weights": {"base": 0.50, "upside": 0.25, "downside": 0.25},
    },
    "GH": {
        "name": "Ghana",
        "regulator": "BoG",
        "dpd_stage2_threshold": 30,
        "dpd_stage3_threshold": 90,
        "relative_pd_threshold": 1.0,
        "absolute_pd_threshold": 0.20,
        "unsecured_lgd": {"stage1": 0.45, "stage2": 0.60, "stage3": 0.85},
        "secured_lgd_floor": 0.10,
        "collateral_haircut": 0.35,
        "recovery_cost_rate": 0.20,
        "cure_rates": {"0-30": 0.78, "31-60": 0.42, "61-90": 0.18, "91-180": 0.07, "180+": 0.03},
        "discount_rate": 0.22,
        "stage1_provision_rate": 0.01,
        "stage2_provision_rate": 0.05,
        "stage3_unsecured_rate": 0.60,
        "stage3_secured_rate": 0.25,
        "macro_scenarios": {"BASE": 1.0, "UPSIDE": 0.85, "DOWNSIDE": 1.30},
        "scenario_weights": {"base": 0.50, "upside": 0.25, "downside": 0.25},
    },
    "UG": {
        "name": "Uganda",
        "regulator": "BoU",
        "dpd_stage2_threshold": 30,
        "dpd_stage3_threshold": 90,
        "relative_pd_threshold": 1.0,
        "absolute_pd_threshold": 0.18,
        "unsecured_lgd": {"stage1": 0.45, "stage2": 0.60, "stage3": 0.82},
        "secured_lgd_floor": 0.10,
        "collateral_haircut": 0.32,
        "recovery_cost_rate": 0.18,
        "cure_rates": {"0-30": 0.82, "31-60": 0.48, "61-90": 0.22, "91-180": 0.09, "180+": 0.04},
        "discount_rate": 0.16,
        "stage1_provision_rate": 0.01,
        "stage2_provision_rate": 0.05,
        "stage3_unsecured_rate": 0.55,
        "stage3_secured_rate": 0.22,
        "macro_scenarios": {"BASE": 1.0, "UPSIDE": 0.85, "DOWNSIDE": 1.25},
        "scenario_weights": {"base": 0.50, "upside": 0.25, "downside": 0.25},
    },
    "TZ": {
        "name": "Tanzania",
        "regulator": "BoT",
        "dpd_stage2_threshold": 30,
        "dpd_stage3_threshold": 90,
        "relative_pd_threshold": 1.0,
        "absolute_pd_threshold": 0.18,
        "unsecured_lgd": {"stage1": 0.45, "stage2": 0.60, "stage3": 0.82},
        "secured_lgd_floor": 0.10,
        "collateral_haircut": 0.32,
        "recovery_cost_rate": 0.18,
        "cure_rates": {"0-30": 0.82, "31-60": 0.48, "61-90": 0.22, "91-180": 0.09, "180+": 0.04},
        "discount_rate": 0.15,
        "stage1_provision_rate": 0.01,
        "stage2_provision_rate": 0.05,
        "stage3_unsecured_rate": 0.55,
        "stage3_secured_rate": 0.22,
        "macro_scenarios": {"BASE": 1.0, "UPSIDE": 0.85, "DOWNSIDE": 1.25},
        "scenario_weights": {"base": 0.50, "upside": 0.25, "downside": 0.25},
    },
    "RW": {
        "name": "Rwanda",
        "regulator": "BNR",
        "dpd_stage2_threshold": 30,
        "dpd_stage3_threshold": 90,
        "relative_pd_threshold": 1.0,
        "absolute_pd_threshold": 0.18,
        "unsecured_lgd": {"stage1": 0.45, "stage2": 0.58, "stage3": 0.80},
        "secured_lgd_floor": 0.10,
        "collateral_haircut": 0.30,
        "recovery_cost_rate": 0.15,
        "cure_rates": {"0-30": 0.83, "31-60": 0.50, "61-90": 0.24, "91-180": 0.10, "180+": 0.04},
        "discount_rate": 0.14,
        "stage1_provision_rate": 0.01,
        "stage2_provision_rate": 0.05,
        "stage3_unsecured_rate": 0.50,
        "stage3_secured_rate": 0.20,
        "macro_scenarios": {"BASE": 1.0, "UPSIDE": 0.85, "DOWNSIDE": 1.25},
        "scenario_weights": {"base": 0.50, "upside": 0.25, "downside": 0.25},
    },
    "ZA": {
        "name": "South Africa",
        "regulator": "SARB",
        "dpd_stage2_threshold": 30,
        "dpd_stage3_threshold": 90,
        "relative_pd_threshold": 1.0,
        "absolute_pd_threshold": 0.15,
        "unsecured_lgd": {"stage1": 0.42, "stage2": 0.55, "stage3": 0.75},
        "secured_lgd_floor": 0.10,
        "collateral_haircut": 0.25,
        "recovery_cost_rate": 0.12,
        "cure_rates": {"0-30": 0.88, "31-60": 0.55, "61-90": 0.30, "91-180": 0.12, "180+": 0.05},
        "discount_rate": 0.11,
        "stage1_provision_rate": 0.01,
        "stage2_provision_rate": 0.05,
        "stage3_unsecured_rate": 0.45,
        "stage3_secured_rate": 0.18,
        "macro_scenarios": {"BASE": 1.0, "UPSIDE": 0.90, "DOWNSIDE": 1.20},
        "scenario_weights": {"base": 0.50, "upside": 0.25, "downside": 0.25},
    },
}

# DPD adjustment factors for PD (mirrors market_config.py)
DPD_ADJUSTMENTS = {0: 1.0, 15: 1.5, 30: 2.5, 45: 4.0, 60: 6.0, 90: 10.0}


def get_market_config(country_code: str) -> Dict[str, Any]:
    """Get config for a country, defaulting to KE if not found."""
    return MARKET_CONFIGS.get(country_code, MARKET_CONFIGS["KE"])


# ============================================================================
# PD CALCULATION (mirrors services/pd_service.py)
# ============================================================================

def _score_to_pd(score: int) -> float:
    """Logistic score-to-PD: PD = 1 / (1 + exp((score - 400) / 100))"""
    try:
        pd_val = 1 / (1 + math.exp((score - 400) / 100))
        return max(0.0001, min(pd_val, 0.9999))
    except (ValueError, OverflowError):
        if score >= 700: return 0.03
        elif score >= 550: return 0.10
        elif score >= 450: return 0.20
        elif score >= 350: return 0.40
        else: return 0.60


def _get_dpd_adjustment(dpd: int) -> float:
    """DPD-based PD multiplier (1x to 10x)."""
    for threshold in sorted(DPD_ADJUSTMENTS.keys(), reverse=True):
        if dpd >= threshold:
            return DPD_ADJUSTMENTS[threshold]
    return 1.0


def _get_vintage_adjustment(months_on_book: int) -> float:
    """Vintage adjustment: new loans riskier, seasoned loans safer."""
    if months_on_book < 3: return 1.5
    elif months_on_book < 6: return 1.2
    elif months_on_book < 12: return 1.0
    elif months_on_book < 24: return 0.95
    else: return 0.90


def calculate_pd(score: int, dpd: int, months_on_book: int,
                 remaining_months: int, stage: int) -> Dict[str, float]:
    """
    Calculate 12-month and lifetime PD.

    12-month PD = base_pd * dpd_adj * vintage_adj
    Lifetime PD = 1 - (1 - pd_12m)^remaining_years
    """
    base_pd = _score_to_pd(score)
    dpd_adj = _get_dpd_adjustment(dpd)
    vintage_adj = _get_vintage_adjustment(months_on_book)

    pd_12m = min(base_pd * dpd_adj * vintage_adj, 1.0)

    # Lifetime PD
    remaining_years = max(remaining_months / 12.0, 1.0)
    try:
        pd_lifetime = 1 - math.pow(1 - pd_12m, remaining_years)
    except (ValueError, OverflowError):
        pd_lifetime = min(pd_12m * remaining_years, 1.0)
    pd_lifetime = min(pd_lifetime, 1.0)

    # PD at origination (base only, no adjustments)
    pd_origination = base_pd

    # Select PD based on stage
    pd_used = pd_lifetime if stage in [2, 3] else pd_12m

    return {
        "pd_12_month": pd_12m,
        "pd_lifetime": pd_lifetime,
        "pd_at_origination": pd_origination,
        "pd_used": pd_used,
        "base_pd": base_pd,
        "dpd_adjustment": dpd_adj,
        "vintage_adjustment": vintage_adj,
    }


# ============================================================================
# STAGING (mirrors services/staging_service.py)
# ============================================================================

def classify_stage(dpd: int, score: int, months_on_book: int,
                   remaining_months: int, is_restructured: bool,
                   is_written_off: bool, config: Dict) -> Dict[str, Any]:
    """
    Classify loan into Stage 1/2/3 using IFRS 9 SICR criteria.

    Stage 3: DPD >= 90 or written off (credit-impaired)
    Stage 2: DPD >= 30, restructured, or SICR detected (PD deterioration)
    Stage 1: Performing
    """
    triggers = []
    reason_parts = []

    # Stage 3 checks
    if dpd >= config["dpd_stage3_threshold"]:
        triggers.append("DPD_90_BACKSTOP")
        reason_parts.append(f"DPD {dpd} >= {config['dpd_stage3_threshold']}")
    if is_written_off:
        triggers.append("WRITTEN_OFF")
        reason_parts.append("Loan written off")

    if triggers:
        return {
            "stage": 3,
            "triggers": triggers,
            "reason": "; ".join(reason_parts),
        }

    # Stage 2 checks
    if dpd >= config["dpd_stage2_threshold"]:
        triggers.append("DPD_30_BACKSTOP")
        reason_parts.append(f"DPD {dpd} >= {config['dpd_stage2_threshold']}")

    if is_restructured:
        triggers.append("RESTRUCTURED")
        reason_parts.append("Loan restructured")

    # PD-based SICR: relative increase > threshold
    pd_current = _score_to_pd(score) * _get_dpd_adjustment(dpd) * _get_vintage_adjustment(months_on_book)
    pd_origination = _score_to_pd(score)
    if pd_origination > 0:
        relative_increase = (pd_current - pd_origination) / pd_origination
        if relative_increase > config["relative_pd_threshold"]:
            triggers.append("RELATIVE_PD_INCREASE")
            reason_parts.append(f"PD increased {relative_increase:.0%} from origination")

    # Absolute PD threshold
    if pd_current > config["absolute_pd_threshold"]:
        triggers.append("ABSOLUTE_PD_THRESHOLD")
        reason_parts.append(f"PD {pd_current:.1%} > {config['absolute_pd_threshold']:.0%} threshold")

    if triggers:
        return {
            "stage": 2,
            "triggers": triggers,
            "reason": "; ".join(reason_parts),
        }

    return {
        "stage": 1,
        "triggers": [],
        "reason": "Performing - no SICR indicators",
    }


# ============================================================================
# LGD CALCULATION (mirrors services/lgd_service.py)
# ============================================================================

def _get_cure_rate(dpd: int, config: Dict) -> float:
    """Get cure rate based on DPD bucket."""
    cure_rates = config["cure_rates"]
    if dpd <= 30: return cure_rates["0-30"]
    elif dpd <= 60: return cure_rates["31-60"]
    elif dpd <= 90: return cure_rates["61-90"]
    elif dpd <= 180: return cure_rates["91-180"]
    else: return cure_rates["180+"]


def calculate_lgd(stage: int, dpd: int, is_secured: bool,
                  collateral_value: float, outstanding_balance: float,
                  config: Dict) -> Dict[str, Any]:
    """
    Calculate LGD.

    Unsecured: fixed rates by stage with cure rate adjustment for Stage 2
    Secured: LGD = 1 - (collateral_recovery_NPV / outstanding_balance)
    """
    if is_secured and collateral_value > 0:
        # Secured LGD
        haircut = config["collateral_haircut"]
        recovery_cost_rate = config["recovery_cost_rate"]
        discount_rate = config["discount_rate"]
        recovery_months = 12  # Default

        recoverable = collateral_value * (1 - haircut)
        costs = collateral_value * recovery_cost_rate
        net_recovery = recoverable - costs

        # NPV discount
        years = recovery_months / 12.0
        try:
            discount_factor = 1 / math.pow(1 + discount_rate, years)
        except (ValueError, OverflowError, ZeroDivisionError):
            discount_factor = 1.0
        npv_recovery = net_recovery * discount_factor

        if outstanding_balance > 0:
            lgd = 1 - (npv_recovery / outstanding_balance)
        else:
            lgd = config["unsecured_lgd"].get(f"stage{stage}", 0.45)

        # Apply floor
        lgd_floor = config["secured_lgd_floor"]
        lgd = max(lgd, lgd_floor)
        lgd = min(lgd, 1.0)

        return {
            "lgd": lgd,
            "method": "secured",
            "collateral_recovery_npv": npv_recovery,
            "recovery_costs": costs,
        }
    else:
        # Unsecured LGD
        base_lgd = config["unsecured_lgd"].get(f"stage{stage}", 0.45)

        # Cure rate adjustment for Stage 2
        if stage == 2:
            cure_rate = _get_cure_rate(dpd, config)
            adjusted_lgd = base_lgd * (1 - cure_rate * 0.3)
        else:
            adjusted_lgd = base_lgd

        return {
            "lgd": min(adjusted_lgd, 1.0),
            "method": "unsecured",
            "base_lgd": base_lgd,
            "collateral_recovery_npv": 0.0,
            "recovery_costs": 0.0,
        }


# ============================================================================
# EAD CALCULATION (mirrors services/ead_service.py)
# ============================================================================

def calculate_ead(outstanding_balance: float, accrued_interest: float,
                  interest_rate: float, remaining_months: int,
                  stage: int) -> Dict[str, float]:
    """
    Calculate Exposure at Default.

    EAD = Outstanding Balance + Accrued Interest + Future Interest (Stage 1 only)
    """
    principal = outstanding_balance
    accrued = accrued_interest

    # Future interest only for Stage 1
    if stage == 1 and interest_rate > 0 and remaining_months > 0:
        remaining_days = remaining_months * 30
        future_interest = principal * (interest_rate / 365) * remaining_days
    else:
        future_interest = 0.0

    ead = principal + accrued + future_interest
    return {
        "ead": max(ead, 0.0),
        "principal": principal,
        "accrued_interest": accrued,
        "future_interest": future_interest,
    }


# ============================================================================
# ECL CALCULATION (mirrors services/ecl_service.py)
# ============================================================================

def calculate_ecl(ead: float, lgd: float, pd_val: float,
                  interest_rate: float, remaining_months: int,
                  stage: int, config: Dict,
                  use_multi_scenario: bool = True) -> Dict[str, float]:
    """
    Calculate Expected Credit Loss.

    ECL = EAD x LGD x PD x Macro Adjustment x Discount Factor

    Multi-scenario: weighted average of Base (50%), Upside (25%), Downside (25%)
    """
    # Base ECL
    ecl_base = ead * lgd * pd_val

    # Macro adjustment (base scenario)
    macro_base = config["macro_scenarios"]["BASE"]
    ecl_adjusted = ecl_base * macro_base

    # NPV discount factor
    eir = interest_rate if interest_rate > 0 else config["discount_rate"]
    if stage == 1:
        years = 1.0
    else:
        years = max(remaining_months / 12.0, 0.5)
    try:
        discount_factor = 1 / math.pow(1 + eir, years)
        discount_factor = max(0.0, min(discount_factor, 1.0))
    except (ValueError, OverflowError, ZeroDivisionError):
        discount_factor = 1.0

    ecl_discounted = ecl_adjusted * discount_factor

    if use_multi_scenario:
        # Multi-scenario weighted ECL
        weights = config["scenario_weights"]
        macro_up = config["macro_scenarios"]["UPSIDE"]
        macro_down = config["macro_scenarios"]["DOWNSIDE"]

        ecl_upside = ead * lgd * pd_val * macro_up * discount_factor
        ecl_downside = ead * lgd * pd_val * macro_down * discount_factor

        ecl_weighted = (
            ecl_discounted * weights["base"] +
            ecl_upside * weights["upside"] +
            ecl_downside * weights["downside"]
        )
        ecl_final = ecl_weighted
    else:
        ecl_upside = 0.0
        ecl_downside = 0.0
        ecl_final = ecl_discounted

    return {
        "ecl_base": ecl_base,
        "ecl_adjusted": ecl_adjusted,
        "discount_factor": discount_factor,
        "ecl_discounted": ecl_discounted,
        "ecl_upside": ecl_upside,
        "ecl_downside": ecl_downside,
        "ecl_final": ecl_final,
    }


# ============================================================================
# RISK GRADING
# ============================================================================

def get_risk_grade(score: int) -> str:
    """Map credit score to risk grade."""
    if score >= 700: return "A"
    elif score >= 550: return "B"
    elif score >= 450: return "C"
    elif score >= 350: return "D"
    else: return "E"


def get_risk_grade_label(grade: str) -> str:
    labels = {"A": "Low Risk", "B": "Medium-Low Risk", "C": "Medium Risk",
              "D": "Medium-High Risk", "E": "High Risk"}
    return labels.get(grade, "Unknown")


# ============================================================================
# MAIN ENGINE: Process entire DataFrame
# ============================================================================

def run_ifrs9_ecl(
    df: pd.DataFrame,
    country_code: str,
    reporting_date: date,
    license_type: str = "Commercial Bank",
    use_multi_scenario: bool = True,
) -> pd.DataFrame:
    """
    Run full IFRS 9 ECL calculation on a loan portfolio DataFrame.

    Required columns (after column mapping):
        - loan_id
        - outstanding_balance
        - days_past_due

    Optional columns (auto-defaulted if missing):
        - collateral_value (default: 0)
        - interest_rate (default: market discount rate)
        - credit_score / customer_risk_score (default: estimated from DPD)
        - disbursement_date, maturity_date (default: estimated)
        - accrued_interest (default: 0)
        - is_restructured (default: False)
        - is_written_off (default: False)
        - product_type (default: BUSINESS_LOAN)

    Returns:
        Enriched DataFrame with all IFRS 9 columns added.
    """
    config = get_market_config(country_code)
    result = df.copy()

    # --- Fill missing optional columns ---
    if 'collateral_value' not in result.columns:
        result['collateral_value'] = 0.0
    result['collateral_value'] = pd.to_numeric(result['collateral_value'], errors='coerce').fillna(0.0)

    if 'accrued_interest' not in result.columns:
        result['accrued_interest'] = 0.0
    result['accrued_interest'] = pd.to_numeric(result['accrued_interest'], errors='coerce').fillna(0.0)

    if 'interest_rate' not in result.columns:
        result['interest_rate'] = config['discount_rate']
    result['interest_rate'] = pd.to_numeric(result['interest_rate'], errors='coerce').fillna(config['discount_rate'])

    # Estimate credit score from DPD if not provided
    if 'credit_score' not in result.columns and 'customer_risk_score' not in result.columns:
        result['credit_score'] = result['days_past_due'].apply(_estimate_score_from_dpd)
    elif 'customer_risk_score' in result.columns:
        result['credit_score'] = pd.to_numeric(result['customer_risk_score'], errors='coerce').fillna(650)
    result['credit_score'] = pd.to_numeric(result['credit_score'], errors='coerce').fillna(650).astype(int)

    # Dates
    if 'disbursement_date' not in result.columns:
        result['disbursement_date'] = reporting_date - timedelta(days=180)
    if 'maturity_date' not in result.columns:
        result['maturity_date'] = reporting_date + timedelta(days=180)

    # Calculate months on book and remaining months
    result['_disb_date'] = pd.to_datetime(result['disbursement_date'], errors='coerce')
    result['_mat_date'] = pd.to_datetime(result['maturity_date'], errors='coerce')
    result['_disb_date'] = result['_disb_date'].fillna(pd.Timestamp(reporting_date - timedelta(days=180)))
    result['_mat_date'] = result['_mat_date'].fillna(pd.Timestamp(reporting_date + timedelta(days=180)))

    result['months_on_book'] = ((pd.Timestamp(reporting_date) - result['_disb_date']).dt.days / 30).clip(lower=1).astype(int)
    result['remaining_months'] = ((result['_mat_date'] - pd.Timestamp(reporting_date)).dt.days / 30).clip(lower=0).astype(int)

    # Boolean flags
    if 'is_restructured' not in result.columns:
        result['is_restructured'] = False
    if 'is_written_off' not in result.columns:
        result['is_written_off'] = False

    result['outstanding_balance'] = pd.to_numeric(result['outstanding_balance'], errors='coerce').fillna(0.0)
    result['days_past_due'] = pd.to_numeric(result['days_past_due'], errors='coerce').fillna(0).astype(int)

    # Is secured
    result['is_secured'] = result['collateral_value'] > 0

    # --- Run IFRS 9 calculations row by row ---
    ifrs9_results = []

    for idx, row in result.iterrows():
        dpd = int(row['days_past_due'])
        score = int(row['credit_score'])
        mob = int(row['months_on_book'])
        rem = int(row['remaining_months'])
        balance = float(row['outstanding_balance'])
        collateral = float(row['collateral_value'])
        accrued = float(row['accrued_interest'])
        ir = float(row['interest_rate'])
        is_restructured = bool(row.get('is_restructured', False))
        is_written_off = bool(row.get('is_written_off', False))
        is_secured = bool(row['is_secured'])

        # 1. Stage classification
        staging = classify_stage(dpd, score, mob, rem, is_restructured, is_written_off, config)
        stage = staging["stage"]

        # 2. PD calculation
        pd_result = calculate_pd(score, dpd, mob, rem, stage)

        # 3. LGD calculation
        lgd_result = calculate_lgd(stage, dpd, is_secured, collateral, balance, config)

        # 4. EAD calculation
        ead_result = calculate_ead(balance, accrued, ir, rem, stage)

        # 5. ECL calculation
        ecl_result = calculate_ecl(
            ead_result["ead"], lgd_result["lgd"], pd_result["pd_used"],
            ir, rem, stage, config, use_multi_scenario
        )

        # 6. Risk grade
        risk_grade = get_risk_grade(score)

        ifrs9_results.append({
            # Staging
            'ifrs9_stage': stage,
            'stage_label': f"Stage {stage}",
            'sicr_triggers': "|".join(staging["triggers"]) if staging["triggers"] else "None",
            'staging_reason': staging["reason"],
            # PD
            'pd_12_month': pd_result["pd_12_month"],
            'pd_lifetime': pd_result["pd_lifetime"],
            'pd_used': pd_result["pd_used"],
            'risk_grade': risk_grade,
            'risk_grade_label': get_risk_grade_label(risk_grade),
            # LGD
            'lgd': lgd_result["lgd"],
            'lgd_method': lgd_result["method"],
            'collateral_recovery_npv': lgd_result["collateral_recovery_npv"],
            # EAD
            'ead': ead_result["ead"],
            'ead_principal': ead_result["principal"],
            'ead_accrued_interest': ead_result["accrued_interest"],
            'ead_future_interest': ead_result["future_interest"],
            # ECL
            'ecl_base': ecl_result["ecl_base"],
            'ecl_final': ecl_result["ecl_final"],
            'ecl_upside': ecl_result["ecl_upside"],
            'ecl_downside': ecl_result["ecl_downside"],
            'discount_factor': ecl_result["discount_factor"],
            # Provision rate
            'ifrs9_provision': ecl_result["ecl_final"],
            'ifrs9_rate': ecl_result["ecl_final"] / balance if balance > 0 else 0.0,
            'coverage_ratio': ecl_result["ecl_final"] / ead_result["ead"] if ead_result["ead"] > 0 else 0.0,
        })

    # Merge results back
    ifrs9_df = pd.DataFrame(ifrs9_results, index=result.index)
    result = pd.concat([result, ifrs9_df], axis=1)

    # Clean up temp columns
    result.drop(columns=['_disb_date', '_mat_date'], inplace=True, errors='ignore')

    return result


def _estimate_score_from_dpd(dpd: int) -> int:
    """Estimate credit score from DPD when no score is available."""
    if dpd == 0: return 680
    elif dpd <= 15: return 620
    elif dpd <= 30: return 560
    elif dpd <= 60: return 500
    elif dpd <= 90: return 440
    elif dpd <= 180: return 380
    else: return 350


# ============================================================================
# PORTFOLIO SUMMARY STATISTICS
# ============================================================================

def generate_portfolio_summary(df: pd.DataFrame, currency_symbol: str = "") -> Dict[str, Any]:
    """Generate comprehensive portfolio-level IFRS 9 summary from enriched DataFrame."""
    total_balance = df['outstanding_balance'].sum()
    total_ead = df['ead'].sum()
    total_ecl = df['ifrs9_provision'].sum()
    total_collateral = df['collateral_value'].sum()

    # By stage
    stage_summary = {}
    for stage in [1, 2, 3]:
        stage_df = df[df['ifrs9_stage'] == stage]
        stage_balance = stage_df['outstanding_balance'].sum()
        stage_ead = stage_df['ead'].sum()
        stage_ecl = stage_df['ifrs9_provision'].sum()
        stage_summary[stage] = {
            'count': len(stage_df),
            'balance': stage_balance,
            'ead': stage_ead,
            'ecl': stage_ecl,
            'coverage_ratio': stage_ecl / stage_ead if stage_ead > 0 else 0.0,
            'balance_pct': stage_balance / total_balance if total_balance > 0 else 0.0,
        }

    # By risk grade
    grade_summary = {}
    for grade in ['A', 'B', 'C', 'D', 'E']:
        grade_df = df[df['risk_grade'] == grade]
        if len(grade_df) > 0:
            grade_summary[grade] = {
                'count': len(grade_df),
                'balance': grade_df['outstanding_balance'].sum(),
                'ecl': grade_df['ifrs9_provision'].sum(),
                'avg_pd': grade_df['pd_used'].mean(),
            }

    # Sensitivity (ECL under different scenarios)
    sensitivity = {}
    if 'ecl_upside' in df.columns and 'ecl_downside' in df.columns:
        sensitivity = {
            'base': total_ecl,
            'upside': df['ecl_upside'].sum() if df['ecl_upside'].sum() > 0 else total_ecl * 0.85,
            'downside': df['ecl_downside'].sum() if df['ecl_downside'].sum() > 0 else total_ecl * 1.25,
        }

    return {
        'total_loans': len(df),
        'total_balance': total_balance,
        'total_ead': total_ead,
        'total_ecl': total_ecl,
        'total_collateral': total_collateral,
        'overall_coverage_ratio': total_ecl / total_ead if total_ead > 0 else 0.0,
        'overall_provision_rate': total_ecl / total_balance if total_balance > 0 else 0.0,
        'by_stage': stage_summary,
        'by_risk_grade': grade_summary,
        'sensitivity': sensitivity,
    }


# ============================================================================
# SENSITIVITY ANALYSIS
# ============================================================================

def run_sensitivity_analysis(
    df: pd.DataFrame,
    country_code: str,
) -> Dict[str, Any]:
    """
    Run PD and LGD shock analysis on an already-calculated portfolio.

    Shocks the base ECL by adjusting PD and LGD multipliers and recalculating.
    Returns tables showing ECL under each scenario.

    Args:
        df: DataFrame already enriched by run_ifrs9_ecl()
        country_code: Country code for market config

    Returns:
        Dict with 'pd_shocks', 'lgd_shocks', and 'combined' tables.
    """
    config = get_market_config(country_code)
    base_ecl = df['ifrs9_provision'].sum()
    base_ead = df['ead'].sum()

    # PD shock scenarios
    pd_shock_factors = [
        ("-50%", 0.50), ("-30%", 0.70), ("-20%", 0.80), ("-10%", 0.90),
        ("Base", 1.00),
        ("+10%", 1.10), ("+20%", 1.20), ("+30%", 1.30), ("+50%", 1.50),
    ]

    pd_shocks = []
    for label, factor in pd_shock_factors:
        # ECL scales linearly with PD (ECL = EAD x LGD x PD)
        shocked_ecl = (df['ead'] * df['lgd'] * df['pd_used'] * factor * df['discount_factor']).sum()
        # Apply multi-scenario weighting
        weights = config["scenario_weights"]
        macro_up = config["macro_scenarios"]["UPSIDE"]
        macro_down = config["macro_scenarios"]["DOWNSIDE"]
        shocked_ecl_weighted = shocked_ecl * (
            weights["base"] + weights["upside"] * macro_up + weights["downside"] * macro_down
        )
        pd_shocks.append({
            'scenario': label,
            'pd_multiplier': factor,
            'ecl': shocked_ecl_weighted,
            'change_from_base': shocked_ecl_weighted - base_ecl,
            'change_pct': (shocked_ecl_weighted - base_ecl) / base_ecl if base_ecl > 0 else 0,
            'coverage_ratio': shocked_ecl_weighted / base_ead if base_ead > 0 else 0,
        })

    # LGD shock scenarios
    lgd_shock_factors = [
        ("-30%", 0.70), ("-20%", 0.80), ("-10%", 0.90),
        ("Base", 1.00),
        ("+10%", 1.10), ("+20%", 1.20), ("+30%", 1.30),
    ]

    lgd_shocks = []
    for label, factor in lgd_shock_factors:
        shocked_lgd = (df['lgd'] * factor).clip(upper=1.0)
        shocked_ecl = (df['ead'] * shocked_lgd * df['pd_used'] * df['discount_factor']).sum()
        weights = config["scenario_weights"]
        macro_up = config["macro_scenarios"]["UPSIDE"]
        macro_down = config["macro_scenarios"]["DOWNSIDE"]
        shocked_ecl_weighted = shocked_ecl * (
            weights["base"] + weights["upside"] * macro_up + weights["downside"] * macro_down
        )
        lgd_shocks.append({
            'scenario': label,
            'lgd_multiplier': factor,
            'ecl': shocked_ecl_weighted,
            'change_from_base': shocked_ecl_weighted - base_ecl,
            'change_pct': (shocked_ecl_weighted - base_ecl) / base_ecl if base_ecl > 0 else 0,
            'coverage_ratio': shocked_ecl_weighted / base_ead if base_ead > 0 else 0,
        })

    # Combined stress: simultaneous PD and LGD shocks (3x3 matrix)
    combined_scenarios = [
        ("PD -20% / LGD -20%", 0.80, 0.80),
        ("PD -20% / LGD Base", 0.80, 1.00),
        ("PD -20% / LGD +20%", 0.80, 1.20),
        ("PD Base / LGD -20%", 1.00, 0.80),
        ("Base", 1.00, 1.00),
        ("PD Base / LGD +20%", 1.00, 1.20),
        ("PD +20% / LGD -20%", 1.20, 0.80),
        ("PD +20% / LGD Base", 1.20, 1.00),
        ("PD +20% / LGD +20%", 1.20, 1.20),
        ("Severe Stress (PD +50% / LGD +30%)", 1.50, 1.30),
    ]

    combined = []
    for label, pd_factor, lgd_factor in combined_scenarios:
        shocked_lgd = (df['lgd'] * lgd_factor).clip(upper=1.0)
        shocked_ecl = (df['ead'] * shocked_lgd * df['pd_used'] * pd_factor * df['discount_factor']).sum()
        weights = config["scenario_weights"]
        macro_up = config["macro_scenarios"]["UPSIDE"]
        macro_down = config["macro_scenarios"]["DOWNSIDE"]
        shocked_ecl_weighted = shocked_ecl * (
            weights["base"] + weights["upside"] * macro_up + weights["downside"] * macro_down
        )
        combined.append({
            'scenario': label,
            'pd_multiplier': pd_factor,
            'lgd_multiplier': lgd_factor,
            'ecl': shocked_ecl_weighted,
            'change_from_base': shocked_ecl_weighted - base_ecl,
            'change_pct': (shocked_ecl_weighted - base_ecl) / base_ecl if base_ecl > 0 else 0,
        })

    return {
        'base_ecl': base_ecl,
        'base_ead': base_ead,
        'pd_shocks': pd_shocks,
        'lgd_shocks': lgd_shocks,
        'combined': combined,
    }


# ============================================================================
# VINTAGE ANALYSIS
# ============================================================================

def run_vintage_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze portfolio performance by origination vintage (disbursement month).

    Groups loans by disbursement cohort and shows ECL, DPD distribution,
    and coverage ratios per vintage.

    Args:
        df: DataFrame already enriched by run_ifrs9_ecl()

    Returns:
        Dict with 'by_vintage' table and 'dpd_by_vintage' breakdown.
    """
    result_df = df.copy()

    # Determine vintage column
    if 'disbursement_date' in result_df.columns:
        result_df['_vintage_date'] = pd.to_datetime(result_df['disbursement_date'], errors='coerce')
    elif '_disb_date' in result_df.columns:
        result_df['_vintage_date'] = result_df['_disb_date']
    else:
        # No date info - return empty
        return {'by_vintage': [], 'dpd_by_vintage': []}

    result_df['vintage'] = result_df['_vintage_date'].dt.to_period('M').astype(str)
    result_df = result_df.dropna(subset=['vintage'])

    # Aggregate by vintage
    vintages = []
    for vintage, group in sorted(result_df.groupby('vintage')):
        count = len(group)
        balance = group['outstanding_balance'].sum()
        ead = group['ead'].sum()
        ecl = group['ifrs9_provision'].sum()
        avg_dpd = group['days_past_due'].mean()
        par30 = (group['days_past_due'] >= 30).sum()
        par90 = (group['days_past_due'] >= 90).sum()
        avg_pd = group['pd_used'].mean()
        avg_mob = group['months_on_book'].mean() if 'months_on_book' in group.columns else 0

        # Stage distribution within vintage
        s1 = (group['ifrs9_stage'] == 1).sum()
        s2 = (group['ifrs9_stage'] == 2).sum()
        s3 = (group['ifrs9_stage'] == 3).sum()

        vintages.append({
            'vintage': vintage,
            'count': count,
            'balance': balance,
            'ead': ead,
            'ecl': ecl,
            'coverage_ratio': ecl / ead if ead > 0 else 0,
            'avg_dpd': avg_dpd,
            'par_30_pct': par30 / count if count > 0 else 0,
            'par_90_pct': par90 / count if count > 0 else 0,
            'avg_pd': avg_pd,
            'avg_months_on_book': avg_mob,
            'stage_1_pct': s1 / count if count > 0 else 0,
            'stage_2_pct': s2 / count if count > 0 else 0,
            'stage_3_pct': s3 / count if count > 0 else 0,
        })

    # DPD bucket breakdown by vintage (for heatmap)
    dpd_by_vintage = []
    dpd_buckets = [
        ('Current', 0, 0), ('1-30', 1, 30), ('31-60', 31, 60),
        ('61-90', 61, 90), ('91-180', 91, 180), ('180+', 181, 99999),
    ]
    for vintage, group in sorted(result_df.groupby('vintage')):
        row = {'vintage': vintage, 'count': len(group)}
        for bucket_name, dpd_min, dpd_max in dpd_buckets:
            bucket_count = ((group['days_past_due'] >= dpd_min) & (group['days_past_due'] <= dpd_max)).sum()
            row[bucket_name] = bucket_count / len(group) if len(group) > 0 else 0
        dpd_by_vintage.append(row)

    return {
        'by_vintage': vintages,
        'dpd_by_vintage': dpd_by_vintage,
    }


# ============================================================================
# COHORT / DRILL-DOWN ANALYSIS
# ============================================================================

def _analyze_cohort(group: pd.DataFrame, cohort_name: str) -> Dict[str, Any]:
    """Compute standard metrics for a cohort (product, secured/unsecured, etc.)."""
    count = len(group)
    if count == 0:
        return None

    balance = group['outstanding_balance'].sum()
    ead = group['ead'].sum()
    ecl = group['ifrs9_provision'].sum()
    collateral = group['collateral_value'].sum() if 'collateral_value' in group.columns else 0
    avg_dpd = group['days_past_due'].mean()
    max_dpd = group['days_past_due'].max()
    par30 = (group['days_past_due'] >= 30).sum()
    par90 = (group['days_past_due'] >= 90).sum()
    avg_pd = group['pd_used'].mean() if 'pd_used' in group.columns else 0
    avg_lgd = group['lgd'].mean() if 'lgd' in group.columns else 0

    s1 = (group['ifrs9_stage'] == 1).sum()
    s2 = (group['ifrs9_stage'] == 2).sum()
    s3 = (group['ifrs9_stage'] == 3).sum()

    reg_prov = group['reg_provision'].sum() if 'reg_provision' in group.columns else 0

    return {
        'cohort': cohort_name,
        'count': count,
        'balance': balance,
        'ead': ead,
        'ecl': ecl,
        'reg_provision': reg_prov,
        'collateral': collateral,
        'coverage_ratio': ecl / ead if ead > 0 else 0,
        'avg_dpd': avg_dpd,
        'max_dpd': max_dpd,
        'par_30_count': par30,
        'par_30_pct': par30 / count if count > 0 else 0,
        'par_90_count': par90,
        'par_90_pct': par90 / count if count > 0 else 0,
        'avg_pd': avg_pd,
        'avg_lgd': avg_lgd,
        'stage_1_pct': s1 / count if count > 0 else 0,
        'stage_2_pct': s2 / count if count > 0 else 0,
        'stage_3_pct': s3 / count if count > 0 else 0,
        'stage_3_count': s3,
        'balance_pct': 0,  # filled in later
    }


def run_cohort_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Drill-down analysis by product, secured/unsecured, and other cohorts.

    Args:
        df: DataFrame already enriched by run_ifrs9_ecl() and regulatory calc.

    Returns:
        Dict with 'by_product', 'by_security', 'by_dpd_bucket', and 'problem_products'.
    """
    total_balance = df['outstanding_balance'].sum()

    # ── 1. Product Breakdown ──
    by_product = []
    product_col = None
    for col in ['product_type', 'product_name', 'product']:
        if col in df.columns:
            product_col = col
            break

    if product_col:
        for name, group in df.groupby(product_col):
            result = _analyze_cohort(group, str(name))
            if result:
                result['balance_pct'] = result['balance'] / total_balance if total_balance > 0 else 0
                by_product.append(result)
        by_product.sort(key=lambda x: x['balance'], reverse=True)

    # ── 2. Secured vs Unsecured ──
    by_security = []
    if 'collateral_value' in df.columns:
        secured_mask = pd.to_numeric(df['collateral_value'], errors='coerce').fillna(0) > 0
        for label, mask in [('Secured', secured_mask), ('Unsecured', ~secured_mask)]:
            group = df[mask]
            if len(group) > 0:
                result = _analyze_cohort(group, label)
                if result:
                    result['balance_pct'] = result['balance'] / total_balance if total_balance > 0 else 0
                    by_security.append(result)

    # ── 3. DPD Bucket Breakdown ──
    dpd_buckets = [
        ('Current (0 DPD)', 0, 0),
        ('1-30 DPD', 1, 30),
        ('31-60 DPD', 31, 60),
        ('61-90 DPD', 61, 90),
        ('91-180 DPD', 91, 180),
        ('181-360 DPD', 181, 360),
        ('360+ DPD', 361, 999999),
    ]
    by_dpd_bucket = []
    for label, dpd_min, dpd_max in dpd_buckets:
        mask = (df['days_past_due'] >= dpd_min) & (df['days_past_due'] <= dpd_max)
        group = df[mask]
        if len(group) > 0:
            result = _analyze_cohort(group, label)
            if result:
                result['balance_pct'] = result['balance'] / total_balance if total_balance > 0 else 0
                by_dpd_bucket.append(result)

    # ── 4. Identify Problem Products ──
    problem_products = []
    for p in by_product:
        issues = []
        if p['par_90_pct'] > 0.50:
            issues.append(f"{p['par_90_pct']:.0%} PAR90 - majority defaulted")
        elif p['par_90_pct'] > 0.20:
            issues.append(f"{p['par_90_pct']:.0%} PAR90 - elevated defaults")
        if p['avg_dpd'] > 180:
            issues.append(f"Avg DPD {p['avg_dpd']:.0f} days - should be written off")
        if p['stage_3_pct'] > 0.50:
            issues.append(f"{p['stage_3_pct']:.0%} Stage 3 concentration")
        if p['par_30_pct'] > 0.80:
            issues.append(f"{p['par_30_pct']:.0%} PAR30 - product is non-performing")

        if issues:
            problem_products.append({
                'product': p['cohort'],
                'count': p['count'],
                'balance': p['balance'],
                'avg_dpd': p['avg_dpd'],
                'max_dpd': p['max_dpd'],
                'par_90_pct': p['par_90_pct'],
                'ecl': p['ecl'],
                'issues': issues,
                'recommendation': _product_recommendation(p),
            })

    # ── 5. Healthy Products ──
    healthy_products = [p for p in by_product if p['par_30_pct'] < 0.05 and p['count'] >= 5]

    return {
        'by_product': by_product,
        'by_security': by_security,
        'by_dpd_bucket': by_dpd_bucket,
        'problem_products': problem_products,
        'healthy_products': healthy_products,
        'product_column': product_col,
    }


def _product_recommendation(p: Dict[str, Any]) -> str:
    """Generate a specific recommendation for a problem product."""
    if p['avg_dpd'] > 360:
        return (f"WRITE OFF: This product has avg DPD of {p['avg_dpd']:.0f} days. "
                f"All {p['count']} loans should be written off immediately per regulatory guidelines. "
                f"Transfer to recovery unit and pursue collateral liquidation where applicable.")
    elif p['par_90_pct'] > 0.80:
        return (f"SUSPEND & RECOVER: {p['par_90_pct']:.0%} of loans are 90+ DPD. "
                f"Suspend new origination for this product. Assign dedicated collections team. "
                f"Evaluate if product design/terms need fundamental restructuring before re-launch.")
    elif p['par_90_pct'] > 0.50:
        return (f"INTENSIVE COLLECTIONS: {p['par_90_pct']:.0%} PAR90 indicates serious delinquency. "
                f"Escalate to senior collections. Review underwriting criteria - are borrowers being "
                f"properly assessed? Consider mandatory collateral requirements.")
    elif p['par_30_pct'] > 0.30:
        return (f"EARLY INTERVENTION: {p['par_30_pct']:.0%} PAR30 is a warning signal. "
                f"Implement proactive SMS/call campaigns before loans migrate to 90+ DPD. "
                f"Review repayment frequency and loan sizing for this product.")
    else:
        return (f"MONITOR: Product shows early signs of stress with {p['par_30_pct']:.0%} PAR30. "
                f"Increase monitoring frequency and review recent originations.")
