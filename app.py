#!/usr/bin/env python3
"""
IFRS 9 Dual Provisioning Platform - Customer Facing Application
5-step workflow: Setup → Rules → Upload (intelligent mapping) → Calculate (full ECL) → Report
With authentication via streamlit-authenticator.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import json
import io
import sys
from pathlib import Path
import streamlit_authenticator as stauth

sys.path.insert(0, str(Path(__file__).parent))

from services.loss_forecast_service import LossForecastService
from services.dataframe_ecl_engine import (
    run_ifrs9_ecl,
    generate_portfolio_summary,
    get_market_config,
    run_sensitivity_analysis,
    run_vintage_analysis,
    run_cohort_analysis,
    MARKET_CONFIGS,
)
from services.pdf_report_generator import generate_pdf_report
from utils.column_mapper import ColumnMapper


def get_risk_grade_label(grade):
    """Map risk grade letter to human-readable label."""
    labels = {"A": "Low Risk", "B": "Medium-Low", "C": "Medium", "D": "Med-High", "E": "High Risk"}
    return labels.get(grade, "")


# Page config
st.set_page_config(
    page_title="IFRS 9 Dual Provisioning Platform",
    page_icon="⚖️",
    layout="wide"
)

# ============================================================================
# AUTHENTICATION
# ============================================================================
# Load credentials from .streamlit/secrets.toml or environment
try:
    credentials = {
        "usernames": {}
    }
    # Read users from secrets
    users_section = st.secrets.get("credentials", {}).get("usernames", {})
    for username, user_data in users_section.items():
        credentials["usernames"][username] = {
            "email": user_data.get("email", f"{username}@creditbox.io"),
            "name": user_data.get("name", username),
            "password": user_data.get("password", ""),
        }

    cookie_config = {
        "name": "ifrs9_auth",
        "key": st.secrets.get("cookie", {}).get("key", "ifrs9_secret_key_change_me"),
        "expiry_days": st.secrets.get("cookie", {}).get("expiry_days", 7),
    }

    authenticator = stauth.Authenticate(
        credentials,
        cookie_config["name"],
        cookie_config["key"],
        cookie_config["expiry_days"],
    )

    authenticator.login()

    if st.session_state.get("authentication_status") is False:
        st.error("Username or password is incorrect")
        st.stop()
    elif st.session_state.get("authentication_status") is None:
        st.info("Please enter your credentials to access the IFRS 9 platform")
        st.stop()

    # User is authenticated — show logout in sidebar
    with st.sidebar:
        st.write(f"Logged in as **{st.session_state.get('name', '')}**")
        authenticator.logout("Logout", "sidebar")

except Exception as e:
    # If secrets are not configured (local dev), skip auth
    if "secrets" in str(e).lower() or "No secrets found" in str(e):
        pass  # Allow unauthenticated access in local dev
    else:
        st.warning(f"Auth config issue: {e}. Running without authentication.")

# ============================================================================
# APP CONTENT (only reached if authenticated or auth skipped)
# ============================================================================

# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'config' not in st.session_state:
    st.session_state.config = {}
if 'loan_data' not in st.session_state:
    st.session_state.loan_data = None
if 'results' not in st.session_state:
    st.session_state.results = None
if 'column_mapping' not in st.session_state:
    st.session_state.column_mapping = None
if 'raw_upload' not in st.session_state:
    st.session_state.raw_upload = None

# Title
st.title("IFRS 9 + Regulatory Dual Provisioning Platform")
st.markdown("**Simple 5-Step Process** | Upload Any Portfolio | Intelligent Field Detection | Full ECL Engine")

# Progress bar
progress_steps = ["Setup", "Rules", "Data", "Calculate", "Report"]
current_step = st.session_state.step
progress = current_step / 5

st.progress(progress)
st.markdown(f"**Step {current_step} of 5:** {progress_steps[current_step-1]}")
st.markdown("---")

# ============================================================================
# STEP 1: INSTITUTION SETUP
# ============================================================================
if st.session_state.step == 1:
    st.header("Step 1: Institution Setup")
    st.markdown("Tell us about your institution so we can apply the correct IFRS 9 parameters")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Your Institution")

        institution_name = st.text_input(
            "Institution Name",
            value=st.session_state.config.get('institution_name', ''),
            placeholder="e.g., ABC Microfinance Bank"
        )

        country = st.selectbox(
            "Country",
            options=[
                ("KE", "Kenya"),
                ("NG", "Nigeria"),
                ("UG", "Uganda"),
                ("TZ", "Tanzania"),
                ("RW", "Rwanda"),
                ("GH", "Ghana"),
                ("ZA", "South Africa")
            ],
            format_func=lambda x: x[1],
            index=0
        )

        # Auto-detect currency
        currency_map = {
            "KE": ("KES", "KSh"),
            "NG": ("NGN", "₦"),
            "UG": ("UGX", "USh"),
            "TZ": ("TZS", "TSh"),
            "RW": ("RWF", "RF"),
            "GH": ("GHS", "GH₵"),
            "ZA": ("ZAR", "R")
        }

        currency_code, currency_symbol = currency_map.get(country[0], ("USD", "$"))
        st.info(f"💱 **Currency:** {currency_code} ({currency_symbol})")

    with col2:
        st.subheader("2. Regulatory Details")

        regulator_map = {
            "KE": "CBK (Central Bank of Kenya)",
            "NG": "CBN (Central Bank of Nigeria)",
            "UG": "BoU (Bank of Uganda)",
            "TZ": "BoT (Bank of Tanzania)",
            "RW": "BNR (National Bank of Rwanda)",
            "GH": "BoG (Bank of Ghana)",
            "ZA": "SARB (South African Reserve Bank)"
        }

        regulator = regulator_map.get(country[0], "")
        st.markdown(f"**Your Regulator:** {regulator}")

        license_type = st.selectbox(
            "License Type / Institution Type",
            options=[
                "Commercial Bank",
                "Microfinance Bank",
                "Microfinance Institution",
                "Digital Lender / Digital Money Lender",
                "Finance Company",
                "Finance House",
                "Leasing Company",
                "Mortgage Finance Company",
                "SACCO",
                "Credit Union",
                "Community Bank",
                "Cooperative Bank",
                "Asset Finance Company",
                "Factoring Company",
                "Peer-to-Peer Platform"
            ],
            help="Select your institution license type"
        )

        reporting_date = st.date_input(
            "Reporting Date",
            value=date.today(),
            help="Date for provision calculation"
        )

    # Show market-specific IFRS 9 parameters
    st.markdown("---")
    market_cfg = get_market_config(country[0])
    st.subheader("IFRS 9 Parameters for " + country[1])
    param_col1, param_col2, param_col3 = st.columns(3)
    with param_col1:
        st.markdown(f"""
        **Staging Thresholds:**
        - Stage 2 DPD: >= {market_cfg['dpd_stage2_threshold']} days
        - Stage 3 DPD: >= {market_cfg['dpd_stage3_threshold']} days
        - Absolute PD threshold: {market_cfg['absolute_pd_threshold']:.0%}
        """)
    with param_col2:
        st.markdown(f"""
        **LGD (Unsecured):**
        - Stage 1: {market_cfg['unsecured_lgd']['stage1']:.0%}
        - Stage 2: {market_cfg['unsecured_lgd']['stage2']:.0%}
        - Stage 3: {market_cfg['unsecured_lgd']['stage3']:.0%}
        """)
    with param_col3:
        st.markdown(f"""
        **Other Parameters:**
        - Discount Rate (EIR): {market_cfg['discount_rate']:.0%}
        - Collateral Haircut: {market_cfg['collateral_haircut']:.0%}
        - Recovery Cost: {market_cfg['recovery_cost_rate']:.0%}
        """)

    st.markdown("---")
    if st.button("Next: Configure Provision Rules →", type="primary"):
        st.session_state.config.update({
            'institution_name': institution_name,
            'country_code': country[0],
            'country_name': country[1],
            'currency_code': currency_code,
            'currency_symbol': currency_symbol,
            'regulator': regulator,
            'license_type': license_type,
            'reporting_date': reporting_date
        })
        st.session_state.step = 2
        st.rerun()

# ============================================================================
# STEP 2: CONFIGURE REGULATORY PROVISION RULES
# ============================================================================
elif st.session_state.step == 2:
    st.header("Step 2: Configure Your Regulatory Provision Rules")

    config = st.session_state.config

    st.info(f"""
    **Institution:** {config['institution_name']}
    **Country:** {config['country_name']}
    **Regulator:** {config['regulator']}
    **License Type:** {config['license_type']}
    **Currency:** {config['currency_symbol']} ({config['currency_code']})
    """)

    st.markdown("---")

    st.markdown("""
    ### Enter Your Regulatory Provision Rules

    Define provision rates based on Days Past Due (DPD) as required by your regulator.

    **Common Structure:**
    - **Performing/Current:** 0-30 DPD → Low provision (1-3%)
    - **Watch/OLEM:** 30-90 DPD → Medium provision (5-10%)
    - **Substandard:** 90-180 DPD → High provision (25-50%)
    - **Doubtful:** 180-360 DPD → Very high provision (50-75%)
    - **Loss:** 360+ DPD → Full provision (100%)

    **Adjust to match YOUR regulator's requirements!**
    """)

    # Initialize rules based on country if not exist
    if 'regulatory_rules' not in st.session_state.config:
        country_code = config.get('country_code', 'KE')
        if country_code == 'NG':
            # CBN Prudential Guidelines
            st.session_state.config['regulatory_rules'] = [
                {"name": "Current", "dpd_min": 0, "dpd_max": 0, "rate": 1.0, "collateral_deduction": False},
                {"name": "OLEM", "dpd_min": 1, "dpd_max": 90, "rate": 5.0, "collateral_deduction": False},
                {"name": "Substandard", "dpd_min": 91, "dpd_max": 180, "rate": 25.0, "collateral_deduction": True},
                {"name": "Doubtful", "dpd_min": 181, "dpd_max": 360, "rate": 50.0, "collateral_deduction": True},
                {"name": "Loss", "dpd_min": 361, "dpd_max": 999999, "rate": 100.0, "collateral_deduction": True}
            ]
        elif country_code == 'KE':
            # CBK Prudential Guidelines
            st.session_state.config['regulatory_rules'] = [
                {"name": "Normal", "dpd_min": 0, "dpd_max": 30, "rate": 1.0, "collateral_deduction": False},
                {"name": "Watch", "dpd_min": 31, "dpd_max": 90, "rate": 5.0, "collateral_deduction": False},
                {"name": "Substandard", "dpd_min": 91, "dpd_max": 180, "rate": 25.0, "collateral_deduction": True},
                {"name": "Doubtful", "dpd_min": 181, "dpd_max": 360, "rate": 75.0, "collateral_deduction": True},
                {"name": "Loss", "dpd_min": 361, "dpd_max": 999999, "rate": 100.0, "collateral_deduction": True}
            ]
        else:
            # Generic default
            st.session_state.config['regulatory_rules'] = [
                {"name": "Normal/Current", "dpd_min": 0, "dpd_max": 30, "rate": 1.0, "collateral_deduction": False},
                {"name": "Watch", "dpd_min": 31, "dpd_max": 90, "rate": 5.0, "collateral_deduction": False},
                {"name": "Substandard", "dpd_min": 91, "dpd_max": 180, "rate": 25.0, "collateral_deduction": True},
                {"name": "Doubtful", "dpd_min": 181, "dpd_max": 360, "rate": 75.0, "collateral_deduction": True},
                {"name": "Loss", "dpd_min": 361, "dpd_max": 999999, "rate": 100.0, "collateral_deduction": True}
            ]

    st.markdown("---")

    # Edit rules
    st.subheader("Your Provision Rules:")

    rules = st.session_state.config['regulatory_rules']

    for i, rule in enumerate(rules):
        with st.expander(f"Rule {i+1}: {rule['name']}", expanded=True):
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1.5, 1.5])

            with col1:
                rule['name'] = st.text_input(
                    "Classification Name",
                    value=rule['name'],
                    key=f"name_{i}",
                    help="e.g., Normal, Substandard, Doubtful, Loss"
                )

            with col2:
                rule['dpd_min'] = st.number_input(
                    "DPD Min",
                    min_value=0,
                    value=rule['dpd_min'],
                    key=f"min_{i}"
                )

            with col3:
                dpd_max_val = 999999 if rule['dpd_max'] >= 999999 else rule['dpd_max']
                rule['dpd_max'] = st.number_input(
                    "DPD Max",
                    min_value=0,
                    value=dpd_max_val,
                    key=f"max_{i}",
                    help="Use large number like 999999 for open-ended"
                )

            with col4:
                rule['rate'] = st.number_input(
                    "Provision %",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(rule['rate']),
                    step=1.0,
                    key=f"rate_{i}"
                )

            with col5:
                rule['collateral_deduction'] = st.checkbox(
                    "Deduct Collateral?",
                    value=rule['collateral_deduction'],
                    key=f"coll_{i}",
                    help="Provision on (Balance - Security)?"
                )

            if st.button(f"Remove Rule {i+1}", key=f"del_{i}"):
                rules.pop(i)
                st.rerun()

    # Add rule button
    if st.button("+ Add Another Rule"):
        rules.append({
            "name": "New Classification",
            "dpd_min": 0,
            "dpd_max": 30,
            "rate": 1.0,
            "collateral_deduction": False
        })
        st.rerun()

    st.markdown("---")

    # Preview rules
    st.subheader("Rules Preview:")

    preview_df = pd.DataFrame([
        {
            "Classification": r['name'],
            "DPD Range": f"{r['dpd_min']}-{r['dpd_max'] if r['dpd_max'] < 999999 else 'max'}",
            "Provision %": f"{r['rate']:.1f}%",
            "Base": "(Balance - Security)" if r['collateral_deduction'] else "Full Balance"
        }
        for r in rules
    ])

    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    # Validate rules for gaps
    sorted_rules = sorted(rules, key=lambda r: r['dpd_min'])
    for i in range(len(sorted_rules) - 1):
        current_max = sorted_rules[i]['dpd_max']
        next_min = sorted_rules[i + 1]['dpd_min']
        if next_min - current_max > 1:
            st.error(
                f"Rule gap detected: DPD {current_max + 1}-{next_min - 1} is not covered by any "
                f"classification. Loans in this range will default to 1% provision. "
                f"Please fix before proceeding."
            )

    # Navigation
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back"):
            st.session_state.step = 1
            st.rerun()
    with col2:
        if st.button("Next: Upload Loan Data →", type="primary"):
            st.session_state.step = 3
            st.rerun()

# ============================================================================
# STEP 3: UPLOAD LOAN DATA (with Intelligent Column Mapping)
# ============================================================================
elif st.session_state.step == 3:
    st.header("Step 3: Upload Your Loan Data")

    config = st.session_state.config

    st.info(f"""
    **Institution:** {config['institution_name']} | {config['license_type']}
    **Regulator:** {config['regulator']} | Currency: {config['currency_symbol']}
    **Reporting Date:** {config['reporting_date']}
    **Rules Configured:** {len(config.get('regulatory_rules', []))} provision rules
    """)

    st.markdown("---")

    st.markdown("""
    ### Upload any loan portfolio file - we auto-detect your columns

    **Supported formats:** Excel (.xlsx, .xls) or CSV

    We automatically recognize common column names like:
    - **Loan ID:** `account`, `loan_number`, `account_number`, `loan_id`, `id`
    - **Balance:** `outstanding_balance`, `olb_principal`, `total_balance`, `principal`
    - **DPD:** `days_past_due`, `dpd`, `days_in_arrears`, `arrears`, `overdue_days`
    - **Collateral:** `collateral_value`, `security_value`, `collateral`
    - **And more:** classification, disbursement_date, interest_rate, product_type...

    If we can't auto-detect a required field, you can map it manually below.
    """)

    uploaded_file = st.file_uploader(
        "Upload Loan Data (Excel or CSV)",
        type=['xlsx', 'xls', 'csv'],
        help="Upload your loan tape - any format, we'll auto-detect the columns"
    )

    if uploaded_file:
        # Read file - handle multiple sheets for Excel
        raw_df = None
        try:
            if uploaded_file.name.endswith('.csv'):
                raw_df = pd.read_csv(uploaded_file)
            else:
                xls = pd.ExcelFile(uploaded_file)
                if len(xls.sheet_names) == 0:
                    st.error("This Excel file contains no worksheets. Please re-export it from your source system and try again.")
                elif len(xls.sheet_names) > 1:
                    sheet = st.selectbox("Select sheet:", xls.sheet_names)
                    raw_df = pd.read_excel(uploaded_file, sheet_name=sheet)
                else:
                    raw_df = pd.read_excel(uploaded_file, sheet_name=xls.sheet_names[0])
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.info("Try re-saving as .xlsx from Excel or export as CSV instead.")

        if raw_df is not None and len(raw_df) > 0:
            st.success(f"Loaded **{len(raw_df):,}** rows with **{len(raw_df.columns)}** columns")

            # Show raw data preview
            with st.expander("Raw Data Preview (first 5 rows)", expanded=False):
                st.dataframe(raw_df.head(5), use_container_width=True)

            st.markdown("---")

            # ============================================================
            # INTELLIGENT COLUMN MAPPING
            # ============================================================
            st.subheader("Column Mapping")

            # Run auto-detection
            mapped_df, auto_map = ColumnMapper.detect_and_map(raw_df)

            # Required fields and their status
            REQUIRED_FIELDS = ['loan_id', 'outstanding_balance', 'days_past_due']
            OPTIONAL_FIELDS = [
                'collateral_value', 'customer_id', 'product_type', 'disbursement_date',
                'maturity_date', 'interest_rate', 'accrued_interest', 'credit_score',
                'customer_risk_score', 'classification', 'outstanding_principal'
            ]

            # Build reverse map for display
            reverse_map = {v: k for k, v in auto_map.items()}

            # Show auto-detected mappings
            st.markdown("**Auto-detected mappings:**")
            if auto_map:
                mapping_rows = []
                for original_col, target_col in auto_map.items():
                    status = "Required" if target_col in REQUIRED_FIELDS else "Optional"
                    mapping_rows.append({
                        "Your Column": original_col,
                        "Mapped To": target_col,
                        "Status": status,
                    })
                mapping_display = pd.DataFrame(mapping_rows)
                st.dataframe(mapping_display, use_container_width=True, hide_index=True)
            else:
                st.warning("No columns were auto-detected. Please map manually below.")

            # Auto-resolve common field alternatives
            # outstanding_principal can serve as outstanding_balance
            if 'outstanding_balance' not in mapped_df.columns and 'outstanding_principal' in mapped_df.columns:
                mapped_df['outstanding_balance'] = mapped_df['outstanding_principal']
                st.info("Using `outstanding_principal` as `outstanding_balance`")

            # classification can be used to derive DPD if no DPD column
            if 'days_past_due' not in mapped_df.columns and 'classification' in mapped_df.columns:
                classification_dpd_map = {
                    'normal': 0, 'current': 0, 'performing': 0,
                    'watch': 15, 'olem': 15, 'special mention': 25,
                    'substandard': 45, 'doubtful': 120, 'loss': 200,
                }
                mapped_df['days_past_due'] = mapped_df['classification'].str.lower().map(classification_dpd_map).fillna(0).astype(int)
                st.info("Derived `days_past_due` from `classification` column")

            # Check which required fields are still missing
            missing_required = [f for f in REQUIRED_FIELDS if f not in mapped_df.columns]

            if missing_required:
                st.warning(f"Missing required fields: **{', '.join(missing_required)}**. Please map them below:")

                # Manual mapping UI for missing required fields
                unmapped_cols = ["(skip)"] + list(raw_df.columns)
                manual_overrides = {}

                for field in missing_required:
                    selected = st.selectbox(
                        f"Map to `{field}`:",
                        options=unmapped_cols,
                        key=f"manual_map_{field}",
                        help=f"Select the column from your file that represents {field}"
                    )
                    if selected != "(skip)":
                        manual_overrides[selected] = field

                # Apply manual overrides
                if manual_overrides:
                    mapped_df = mapped_df.rename(columns=manual_overrides)

            # Also let user override optional fields
            with st.expander("Advanced: Map additional optional fields"):
                unmapped_cols = ["(skip)"] + [c for c in raw_df.columns if c not in auto_map]
                unmapped_targets = [f for f in OPTIONAL_FIELDS if f not in mapped_df.columns]

                if unmapped_targets and unmapped_cols:
                    for field in unmapped_targets[:6]:  # Show up to 6
                        selected = st.selectbox(
                            f"Map to `{field}`:",
                            options=unmapped_cols,
                            key=f"opt_map_{field}",
                        )
                        if selected != "(skip)":
                            mapped_df = mapped_df.rename(columns={selected: field})

            # Final validation
            st.markdown("---")
            still_missing = [f for f in REQUIRED_FIELDS if f not in mapped_df.columns]

            if still_missing:
                st.error(f"Cannot proceed - missing required columns: **{', '.join(still_missing)}**")
                st.markdown("Please map these columns above, or ensure your file contains columns with standard names.")
            else:
                st.success("All required columns mapped successfully")

                # Show mapped data preview
                preview_cols = [c for c in REQUIRED_FIELDS + OPTIONAL_FIELDS if c in mapped_df.columns]
                st.subheader("Mapped Data Preview")
                st.dataframe(mapped_df[preview_cols].head(10), use_container_width=True)

                # Summary stats
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Loans", f"{len(mapped_df):,}")
                with col2:
                    total_bal = pd.to_numeric(mapped_df['outstanding_balance'], errors='coerce').sum()
                    st.metric("Total Balance", f"{config['currency_symbol']} {total_bal:,.0f}")
                with col3:
                    dpd_col = pd.to_numeric(mapped_df['days_past_due'], errors='coerce')
                    par30 = (dpd_col >= 30).sum()
                    st.metric("PAR 30+", f"{par30:,} ({par30/len(mapped_df)*100:.1f}%)")
                with col4:
                    has_collateral = 'collateral_value' in mapped_df.columns
                    if has_collateral:
                        secured = (pd.to_numeric(mapped_df['collateral_value'], errors='coerce') > 0).sum()
                        st.metric("Secured Loans", f"{secured:,}")
                    else:
                        st.metric("Secured Loans", "N/A (no collateral data)")

                # Store mapped data
                st.session_state.loan_data = mapped_df
                st.session_state.column_mapping = auto_map

                # Navigation
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("← Back"):
                        st.session_state.step = 2
                        st.rerun()
                with col2:
                    if st.button("Next: Calculate Provisions →", type="primary"):
                        st.session_state.step = 4
                        st.rerun()

# ============================================================================
# STEP 4: CALCULATE DUAL PROVISIONS (Full ECL Engine)
# ============================================================================
elif st.session_state.step == 4:
    st.header("Step 4: Calculate Dual Provisions")

    if st.session_state.loan_data is None:
        st.error("No loan data uploaded!")
        if st.button("← Back to Upload"):
            st.session_state.step = 3
            st.rerun()
    else:
        config = st.session_state.config
        df = st.session_state.loan_data
        country_code = config['country_code']
        market_cfg = get_market_config(country_code)

        st.info(f"""
        **Ready to Calculate:**
        - Institution: {config['institution_name']} ({config['license_type']})
        - Country: {config['country_name']} ({config['regulator']})
        - Loans: {len(df):,}
        - Regulatory Rules: {len(config['regulatory_rules'])} classifications
        - IFRS 9 Engine: Full ECL (PD x LGD x EAD) with {country_code} market parameters
        - Currency: {config['currency_symbol']}
        """)

        st.markdown("---")

        if st.button("Calculate IFRS 9 + Regulatory Provisions", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()

            # ============================================================
            # PHASE A: IFRS 9 ECL Calculation (Full Engine)
            # ============================================================
            status_text.text("Running IFRS 9 ECL engine (PD, LGD, EAD, Staging)...")
            progress_bar.progress(20)

            df_ecl = run_ifrs9_ecl(
                df=df,
                country_code=country_code,
                reporting_date=config['reporting_date'],
                license_type=config['license_type'],
                use_multi_scenario=True,
            )

            progress_bar.progress(60)

            # ============================================================
            # PHASE B: Regulatory Provision Calculation
            # ============================================================
            status_text.text("Calculating regulatory provisions...")

            def calculate_regulatory(row):
                dpd = int(row['days_past_due'])
                balance = float(row['outstanding_balance'])
                security = float(row.get('collateral_value', 0))

                for rule in config['regulatory_rules']:
                    if rule['dpd_min'] <= dpd <= rule['dpd_max']:
                        rate = rule['rate'] / 100
                        if rule['collateral_deduction']:
                            base = max(balance - security, 0)
                        else:
                            base = balance
                        provision = base * rate
                        return pd.Series({
                            'reg_classification': rule['name'],
                            'reg_base': base,
                            'reg_rate': rate,
                            'reg_provision': provision
                        })

                return pd.Series({
                    'reg_classification': 'Unclassified',
                    'reg_base': balance,
                    'reg_rate': 0.01,
                    'reg_provision': balance * 0.01
                })

            reg_data = df_ecl.apply(calculate_regulatory, axis=1)
            df_ecl = pd.concat([df_ecl, reg_data], axis=1)

            progress_bar.progress(80)

            # ============================================================
            # PHASE C: Gap Analysis & Final Provision
            # ============================================================
            status_text.text("Computing gap analysis...")

            df_ecl['gap'] = df_ecl['reg_provision'] - df_ecl['ifrs9_provision']
            df_ecl['final_provision'] = df_ecl[['ifrs9_provision', 'reg_provision']].max(axis=1)

            # Generate portfolio summary
            portfolio_summary = generate_portfolio_summary(df_ecl, config['currency_symbol'])

            # Build results
            results = {
                'total_loans': len(df_ecl),
                'total_balance': df_ecl['outstanding_balance'].sum(),
                'total_ead': df_ecl['ead'].sum(),
                'total_security': df_ecl['collateral_value'].sum(),
                'ifrs9_total': df_ecl['ifrs9_provision'].sum(),
                'regulatory_total': df_ecl['reg_provision'].sum(),
                'final_total': df_ecl['final_provision'].sum(),
                'gap': df_ecl['reg_provision'].sum() - df_ecl['ifrs9_provision'].sum(),
                'loan_data': df_ecl,
                'portfolio_summary': portfolio_summary,
                'country_code': country_code,
            }

            st.session_state.results = results
            progress_bar.progress(100)
            status_text.text("Calculation complete!")

            st.success("All calculations complete!")

        # Show results if calculated
        if st.session_state.results:
            results = st.session_state.results

            st.markdown("---")
            st.subheader("Results Summary")

            # Top-level metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "IFRS 9 ECL Provision",
                    f"{config['currency_symbol']} {results['ifrs9_total']:,.2f}"
                )

            with col2:
                st.metric(
                    "Regulatory Provision",
                    f"{config['currency_symbol']} {results['regulatory_total']:,.2f}"
                )

            with col3:
                gap = results['gap']
                ifrs9_total = results['ifrs9_total']
                gap_pct = abs(gap / ifrs9_total * 100) if ifrs9_total > 0 else 0
                st.metric(
                    "Gap",
                    f"{config['currency_symbol']} {abs(gap):,.2f}",
                    delta=f"{'Under' if gap > 0 else 'Over'} by {gap_pct:.1f}%"
                )

            with col4:
                st.metric(
                    "Final Provision (Higher-of)",
                    f"{config['currency_symbol']} {results['final_total']:,.2f}",
                )

            st.markdown("---")

            # Recommendation
            if gap > 0:
                st.error(f"""
                **UNDER-PROVISIONED**

                Your IFRS 9 ECL provision is **{gap_pct:.1f}% lower** than regulatory requirements.

                **Use Regulatory Provision:** {config['currency_symbol']} {results['regulatory_total']:,.2f}
                """)
            else:
                st.success(f"""
                **COMPLIANT**

                Your IFRS 9 ECL provision **exceeds** regulatory requirements by **{gap_pct:.1f}%**.

                **Use IFRS 9 Provision:** {config['currency_symbol']} {results['ifrs9_total']:,.2f}
                """)

            # ============================================================
            # IFRS 9 STAGE BREAKDOWN
            # ============================================================
            st.markdown("---")
            st.subheader("IFRS 9 Stage Distribution")

            summary = results['portfolio_summary']
            stage_data = summary['by_stage']

            stage_col1, stage_col2 = st.columns([2, 1])

            with stage_col1:
                stage_table = pd.DataFrame([
                    {
                        "Stage": f"Stage {s}",
                        "Loans": f"{d['count']:,}",
                        "Balance": f"{config['currency_symbol']} {d['balance']:,.0f}",
                        "EAD": f"{config['currency_symbol']} {d['ead']:,.0f}",
                        "ECL": f"{config['currency_symbol']} {d['ecl']:,.0f}",
                        "Coverage": f"{d['coverage_ratio']:.2%}",
                        "% of Book": f"{d['balance_pct']:.1%}",
                    }
                    for s, d in stage_data.items() if d['count'] > 0
                ])
                st.dataframe(stage_table, use_container_width=True, hide_index=True)

            with stage_col2:
                # Stage distribution pie
                pie_data = pd.DataFrame([
                    {"Stage": f"Stage {s}", "Balance": d['balance']}
                    for s, d in stage_data.items() if d['count'] > 0
                ])
                if not pie_data.empty:
                    fig_pie = px.pie(pie_data, values='Balance', names='Stage',
                                    title='Exposure by Stage',
                                    color_discrete_sequence=['#2ecc71', '#f39c12', '#e74c3c'])
                    fig_pie.update_layout(height=300, margin=dict(t=40, b=0, l=0, r=0))
                    st.plotly_chart(fig_pie, use_container_width=True)

            # ============================================================
            # PROVISION COMPARISON CHART
            # ============================================================
            st.markdown("---")
            st.subheader("Dual Provision Comparison")

            fig = go.Figure(data=[
                go.Bar(name='IFRS 9 ECL', x=['Provision'], y=[results['ifrs9_total']],
                       marker_color='#3498db', text=[f"{config['currency_symbol']} {results['ifrs9_total']:,.0f}"],
                       textposition='auto'),
                go.Bar(name='Regulatory', x=['Provision'], y=[results['regulatory_total']],
                       marker_color='#e67e22', text=[f"{config['currency_symbol']} {results['regulatory_total']:,.0f}"],
                       textposition='auto')
            ])
            fig.update_layout(
                title='IFRS 9 vs Regulatory Provision',
                yaxis_title=f'Amount ({config["currency_symbol"]})',
                barmode='group',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

            # ============================================================
            # RISK GRADE DISTRIBUTION
            # ============================================================
            if 'by_risk_grade' in summary and summary['by_risk_grade']:
                st.markdown("---")
                st.subheader("Risk Grade Distribution")

                grade_table = pd.DataFrame([
                    {
                        "Grade": f"{g} ({get_risk_grade_label(g)})" if g else g,
                        "Loans": f"{d['count']:,}",
                        "Balance": f"{config['currency_symbol']} {d['balance']:,.0f}",
                        "ECL": f"{config['currency_symbol']} {d['ecl']:,.0f}",
                        "Avg PD": f"{d['avg_pd']:.2%}",
                    }
                    for g, d in sorted(summary['by_risk_grade'].items())
                ])
                st.dataframe(grade_table, use_container_width=True, hide_index=True)

            # ============================================================
            # LOSS FORECASTING & LIQUIDITY
            # ============================================================
            st.markdown("---")
            st.subheader("Loss Forecast & Liquidity Recommendations")

            df_ecl = results['loan_data']
            forecast_service = LossForecastService(df_ecl)
            forecast_result = forecast_service.generate_forecast_summary(
                forecast_months=6,
                scenario='base'
            )
            st.session_state.results['forecast'] = forecast_result

            fcol1, fcol2 = st.columns(2)

            with fcol1:
                st.markdown("### 6-Month Loss Forecast")
                forecast_df = pd.DataFrame([
                    {
                        "Month": f['forecast_date'],
                        "Expected Loss": f"{config['currency_symbol']} {f['expected_loss']:,.0f}",
                        "Forecasted Balance": f"{config['currency_symbol']} {f['forecasted_balance']:,.0f}",
                        "Provision Needed": f"{config['currency_symbol']} {f['forecasted_provision']:,.0f}"
                    }
                    for f in forecast_result['forecasts']
                ])
                st.dataframe(forecast_df, use_container_width=True, hide_index=True)

                total_loss = forecast_result['summary']['total_expected_loss']
                st.metric("Total Expected Loss (6 months)",
                          f"{config['currency_symbol']} {total_loss:,.2f}")

            with fcol2:
                st.markdown("### Liquidity Recommendations")
                liq = forecast_result['liquidity_recommendation']
                st.info(f"""
                **Required Cash Reserves:**

                Base Reserve (3-month avg):
                {config['currency_symbol']} {liq['base_reserve']:,.2f}

                Stress Buffer (20%):
                {config['currency_symbol']} {liq['stress_buffer']:,.2f}

                Regulatory Minimum (10% of portfolio):
                {config['currency_symbol']} {liq['regulatory_minimum']:,.2f}

                **TOTAL RECOMMENDED:**
                {config['currency_symbol']} {liq['total_recommended']:,.2f}
                """)

            # Loss forecast chart
            st.markdown("---")
            forecast_chart_df = pd.DataFrame([
                {"Month": f['forecast_date'], "Expected Loss": f['expected_loss']}
                for f in forecast_result['forecasts']
            ])
            fig_forecast = px.line(
                forecast_chart_df, x='Month', y='Expected Loss',
                title='6-Month Loss Forecast', markers=True
            )
            fig_forecast.update_layout(
                yaxis_title=f'Expected Loss ({config["currency_symbol"]})',
                height=350
            )
            st.plotly_chart(fig_forecast, use_container_width=True)

            # ============================================================
            # SENSITIVITY ANALYSIS
            # ============================================================
            st.markdown("---")
            st.subheader("Sensitivity Analysis")
            st.caption("How ECL changes under stressed PD and LGD assumptions")

            sensitivity = run_sensitivity_analysis(df_ecl, country_code)
            st.session_state.results['sensitivity'] = sensitivity

            sens_tab1, sens_tab2, sens_tab3 = st.tabs(["PD Shocks", "LGD Shocks", "Combined Stress"])

            with sens_tab1:
                pd_shock_df = pd.DataFrame([
                    {
                        "Scenario": s['scenario'],
                        "PD Factor": f"{s['pd_multiplier']:.2f}x",
                        "ECL": f"{config['currency_symbol']} {s['ecl']:,.0f}",
                        "Change": f"{config['currency_symbol']} {s['change_from_base']:+,.0f}",
                        "Change %": f"{s['change_pct']:+.1%}",
                    }
                    for s in sensitivity['pd_shocks']
                ])
                st.dataframe(pd_shock_df, use_container_width=True, hide_index=True)

                # PD sensitivity chart
                pd_chart_data = pd.DataFrame([
                    {"Scenario": s['scenario'], "ECL": s['ecl']}
                    for s in sensitivity['pd_shocks']
                ])
                fig_pd = px.bar(pd_chart_data, x='Scenario', y='ECL',
                                title='ECL Under PD Stress Scenarios',
                                color_discrete_sequence=['#3498db'])
                fig_pd.update_layout(yaxis_title=f'ECL ({config["currency_symbol"]})', height=350)
                st.plotly_chart(fig_pd, use_container_width=True)

            with sens_tab2:
                lgd_shock_df = pd.DataFrame([
                    {
                        "Scenario": s['scenario'],
                        "LGD Factor": f"{s['lgd_multiplier']:.2f}x",
                        "ECL": f"{config['currency_symbol']} {s['ecl']:,.0f}",
                        "Change": f"{config['currency_symbol']} {s['change_from_base']:+,.0f}",
                        "Change %": f"{s['change_pct']:+.1%}",
                    }
                    for s in sensitivity['lgd_shocks']
                ])
                st.dataframe(lgd_shock_df, use_container_width=True, hide_index=True)

                lgd_chart_data = pd.DataFrame([
                    {"Scenario": s['scenario'], "ECL": s['ecl']}
                    for s in sensitivity['lgd_shocks']
                ])
                fig_lgd = px.bar(lgd_chart_data, x='Scenario', y='ECL',
                                 title='ECL Under LGD Stress Scenarios',
                                 color_discrete_sequence=['#e67e22'])
                fig_lgd.update_layout(yaxis_title=f'ECL ({config["currency_symbol"]})', height=350)
                st.plotly_chart(fig_lgd, use_container_width=True)

            with sens_tab3:
                comb_df = pd.DataFrame([
                    {
                        "Scenario": s['scenario'],
                        "PD": f"{s['pd_multiplier']:.2f}x",
                        "LGD": f"{s['lgd_multiplier']:.2f}x",
                        "ECL": f"{config['currency_symbol']} {s['ecl']:,.0f}",
                        "Change %": f"{s['change_pct']:+.1%}",
                    }
                    for s in sensitivity['combined']
                ])
                st.dataframe(comb_df, use_container_width=True, hide_index=True)

                # Severe stress callout
                severe = [s for s in sensitivity['combined'] if 'Severe' in s['scenario']]
                if severe:
                    s = severe[0]
                    st.warning(f"""
                    **Severe Stress Scenario (PD +50% / LGD +30%):**
                    ECL = {config['currency_symbol']} {s['ecl']:,.0f}
                    ({s['change_pct']:+.1%} from base)
                    """)

            # ============================================================
            # VINTAGE ANALYSIS
            # ============================================================
            st.markdown("---")
            st.subheader("Vintage Analysis")
            st.caption("Portfolio performance by origination cohort")

            vintage = run_vintage_analysis(df_ecl)
            st.session_state.results['vintage'] = vintage

            if vintage and vintage.get('by_vintage'):
                vin_tab1, vin_tab2 = st.tabs(["Vintage Summary", "DPD Heatmap"])

                with vin_tab1:
                    vin_df = pd.DataFrame([
                        {
                            "Vintage": v['vintage'],
                            "Loans": f"{v['count']:,}",
                            "Balance": f"{config['currency_symbol']} {v['balance']:,.0f}",
                            "ECL": f"{config['currency_symbol']} {v['ecl']:,.0f}",
                            "Coverage": f"{v['coverage_ratio']:.2%}",
                            "PAR 30+": f"{v['par_30_pct']:.0%}",
                            "PAR 90+": f"{v['par_90_pct']:.0%}",
                            "Avg DPD": f"{v['avg_dpd']:.0f}",
                            "Stg1 %": f"{v['stage_1_pct']:.0%}",
                            "Stg2 %": f"{v['stage_2_pct']:.0%}",
                            "Stg3 %": f"{v['stage_3_pct']:.0%}",
                        }
                        for v in vintage['by_vintage']
                    ])
                    st.dataframe(vin_df, use_container_width=True, hide_index=True)

                    # Coverage by vintage chart
                    vin_chart = pd.DataFrame([
                        {"Vintage": v['vintage'], "Coverage %": v['coverage_ratio'] * 100, "PAR 30+": v['par_30_pct'] * 100}
                        for v in vintage['by_vintage']
                    ])
                    fig_vin = px.bar(vin_chart, x='Vintage', y=['Coverage %', 'PAR 30+'],
                                     title='Coverage & PAR 30+ by Vintage', barmode='group')
                    fig_vin.update_layout(yaxis_title='%', height=350)
                    st.plotly_chart(fig_vin, use_container_width=True)

                with vin_tab2:
                    if vintage.get('dpd_by_vintage'):
                        heatmap_data = pd.DataFrame(vintage['dpd_by_vintage'])
                        heatmap_data = heatmap_data.set_index('vintage').drop(columns=['count'], errors='ignore')
                        # Convert to percentages for display
                        heatmap_display = (heatmap_data * 100).round(1)

                        st.markdown("**DPD Distribution by Vintage (% of loans)**")
                        st.dataframe(
                            heatmap_display.style.background_gradient(cmap='YlOrRd', axis=None),
                            use_container_width=True,
                        )
            else:
                st.info("No disbursement date data available for vintage analysis. "
                        "Include a `disbursement_date` column in your upload for vintage breakdowns.")

            # ============================================================
            # COHORT ANALYSIS (Product, Secured/Unsecured, DPD Buckets)
            # ============================================================
            st.markdown("---")
            st.subheader("Cohort Drill-Down Analysis")
            st.caption("Product-level, secured vs unsecured, and DPD bucket breakdowns")

            cohort = run_cohort_analysis(df_ecl)
            st.session_state.results['cohort'] = cohort

            cohort_tab1, cohort_tab2, cohort_tab3 = st.tabs([
                "Product Breakdown", "Secured vs Unsecured", "DPD Buckets"
            ])

            with cohort_tab1:
                if cohort.get('by_product'):
                    prod_df = pd.DataFrame([
                        {
                            "Product": p['cohort'],
                            "Loans": f"{p['count']:,}",
                            "Balance": f"{config['currency_symbol']} {p['balance']:,.0f}",
                            "ECL": f"{config['currency_symbol']} {p['ecl']:,.0f}",
                            "Coverage": f"{p['coverage_ratio']:.2%}",
                            "PAR 30+": f"{p['par_30_pct']:.0%}",
                            "PAR 90+": f"{p['par_90_pct']:.0%}",
                            "Avg DPD": f"{p['avg_dpd']:.0f}",
                            "Stg1 %": f"{p['stage_1_pct']:.0%}",
                            "Stg2 %": f"{p['stage_2_pct']:.0%}",
                            "Stg3 %": f"{p['stage_3_pct']:.0%}",
                        }
                        for p in cohort['by_product']
                    ])
                    st.dataframe(prod_df, use_container_width=True, hide_index=True)

                    # Product ECL chart
                    prod_chart = pd.DataFrame([
                        {"Product": p['cohort'], "ECL": p['ecl'], "Balance": p['balance']}
                        for p in cohort['by_product']
                    ]).sort_values('ECL', ascending=False).head(10)
                    fig_prod = px.bar(prod_chart, x='Product', y='ECL',
                                      title='Top 10 Products by ECL',
                                      color_discrete_sequence=['#e74c3c'])
                    fig_prod.update_layout(
                        yaxis_title=f'ECL ({config["currency_symbol"]})',
                        xaxis_tickangle=-45, height=400
                    )
                    st.plotly_chart(fig_prod, use_container_width=True)

                    # Problem products callout
                    if cohort.get('problem_products'):
                        st.markdown("#### Problem Products")
                        for pp in cohort['problem_products']:
                            issues_text = '; '.join(pp.get('issues', []))
                            st.error(f"""
                            **{pp['product']}** - {pp['count']} loans, {config['currency_symbol']} {pp['balance']:,.0f} balance
                            - Avg DPD: {pp['avg_dpd']:.0f} | PAR 90+: {pp['par_90_pct']:.0%}
                            - Issues: {issues_text}
                            - Recommendation: {pp.get('recommendation', 'Review immediately')}
                            """)

                    # Healthy products callout
                    if cohort.get('healthy_products'):
                        st.markdown("#### Healthy Products (PAR 30+ < 10%)")
                        for hp in cohort['healthy_products']:
                            st.success(f"""
                            **{hp['cohort']}** - {hp['count']} loans, {config['currency_symbol']} {hp['balance']:,.0f} balance
                            - PAR 30+: {hp['par_30_pct']:.0%} | Coverage: {hp['coverage_ratio']:.2%}
                            """)
                else:
                    st.info("No product type data detected for product breakdown.")

            with cohort_tab2:
                if cohort.get('by_security'):
                    sec_df = pd.DataFrame([
                        {
                            "Type": s['cohort'],
                            "Loans": f"{s['count']:,}",
                            "Balance": f"{config['currency_symbol']} {s['balance']:,.0f}",
                            "ECL": f"{config['currency_symbol']} {s['ecl']:,.0f}",
                            "Coverage": f"{s['coverage_ratio']:.2%}",
                            "PAR 30+": f"{s['par_30_pct']:.0%}",
                            "Avg DPD": f"{s['avg_dpd']:.0f}",
                            "Stg1 %": f"{s['stage_1_pct']:.0%}",
                            "Stg2 %": f"{s['stage_2_pct']:.0%}",
                            "Stg3 %": f"{s['stage_3_pct']:.0%}",
                        }
                        for s in cohort['by_security']
                    ])
                    st.dataframe(sec_df, use_container_width=True, hide_index=True)

                    # Secured vs Unsecured comparison chart
                    sec_chart = pd.DataFrame([
                        {"Type": s['cohort'], "Coverage %": s['coverage_ratio'] * 100,
                         "PAR 30+": s['par_30_pct'] * 100}
                        for s in cohort['by_security']
                    ])
                    fig_sec = px.bar(sec_chart, x='Type', y=['Coverage %', 'PAR 30+'],
                                     title='Secured vs Unsecured: Coverage & PAR 30+',
                                     barmode='group')
                    fig_sec.update_layout(yaxis_title='%', height=350)
                    st.plotly_chart(fig_sec, use_container_width=True)
                else:
                    st.info("No collateral data detected for secured/unsecured breakdown.")

            with cohort_tab3:
                if cohort.get('by_dpd_bucket'):
                    dpd_df = pd.DataFrame([
                        {
                            "DPD Bucket": b['cohort'],
                            "Loans": f"{b['count']:,}",
                            "Balance": f"{config['currency_symbol']} {b['balance']:,.0f}",
                            "ECL": f"{config['currency_symbol']} {b['ecl']:,.0f}",
                            "Coverage": f"{b['coverage_ratio']:.2%}",
                            "% of Book": f"{b['balance'] / max(results['total_balance'], 1):.1%}",
                        }
                        for b in cohort['by_dpd_bucket']
                    ])
                    st.dataframe(dpd_df, use_container_width=True, hide_index=True)

                    # DPD bucket distribution chart
                    dpd_chart = pd.DataFrame([
                        {"Bucket": b['cohort'], "Balance": b['balance'], "ECL": b['ecl']}
                        for b in cohort['by_dpd_bucket']
                    ])
                    fig_dpd = px.bar(dpd_chart, x='Bucket', y=['Balance', 'ECL'],
                                      title='Balance & ECL by DPD Bucket', barmode='group')
                    fig_dpd.update_layout(
                        yaxis_title=f'{config["currency_symbol"]}', height=350
                    )
                    st.plotly_chart(fig_dpd, use_container_width=True)
                else:
                    st.info("No DPD data detected for bucket distribution.")

            # Navigation
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("← Back"):
                    st.session_state.step = 3
                    st.rerun()
            with col2:
                if st.button("Next: Generate Report →", type="primary"):
                    st.session_state.step = 5
                    st.rerun()

# ============================================================================
# STEP 5: GENERATE COMPREHENSIVE REPORT
# ============================================================================
elif st.session_state.step == 5:
    st.header("Step 5: Download Your Comprehensive Report")

    if st.session_state.results is None:
        st.error("No results to report!")
        if st.button("← Back"):
            st.session_state.step = 4
            st.rerun()
    else:
        results = st.session_state.results
        config = st.session_state.config
        df = results['loan_data']
        summary = results.get('portfolio_summary', {})
        forecast = results.get('forecast', {})
        sensitivity = results.get('sensitivity')
        vintage = results.get('vintage')
        cohort = results.get('cohort')
        liq = forecast.get('liquidity_recommendation', {}) if forecast else {}

        st.success("All calculations complete!")

        st.markdown("---")

        # Report summary
        st.subheader("Your Report Includes:")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            **Section 1: Executive Summary**
            - Key metrics and recommendation
            - Provision comparison table
            - Over/under provision status

            **Section 2: IFRS 9 ECL Analysis**
            - Stage classification (PD/LGD/EAD based)
            - ECL by stage with coverage ratios
            - Risk grade distribution
            - SICR trigger analysis

            **Section 3: Regulatory Analysis**
            - Classification breakdown
            - Provision by classification
            - Collateral impact analysis
            """)

        with col2:
            st.markdown("""
            **Section 4: Dual Provision Comparison**
            - Side-by-side IFRS 9 vs Regulatory
            - Gap analysis per loan
            - Final provision (higher-of)

            **Section 5: Sensitivity Analysis**
            - PD shock table (9 scenarios)
            - LGD shock table (7 scenarios)
            - Combined stress matrix (10 scenarios)

            **Section 6: Vintage Analysis**
            - Cohort performance by origination month
            - PAR 30+/90+ by vintage
            - DPD distribution heatmap

            **Section 7: Cohort Drill-Down**
            - Product-level ECL analysis
            - Problem products with recommendations
            - Secured vs unsecured comparison
            - DPD bucket distribution

            **Section 8: Loss Forecast & Liquidity**
            - 6-month expected losses
            - Liquidity recommendations

            **Section 9: Loan-Level Detail**
            - Full IFRS 9 output per loan
            - PD, LGD, EAD, ECL breakdown
            """)

        st.markdown("---")

        # Download options
        st.subheader("Download Reports")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("### Excel Report (Full)")

            # Build multi-sheet Excel
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                # Sheet 1: Executive Summary
                exec_rows = [
                    {'Metric': 'Institution', 'Value': config['institution_name']},
                    {'Metric': 'Country', 'Value': config['country_name']},
                    {'Metric': 'Regulator', 'Value': config['regulator']},
                    {'Metric': 'License Type', 'Value': config['license_type']},
                    {'Metric': 'Reporting Date', 'Value': str(config['reporting_date'])},
                    {'Metric': 'Total Loans', 'Value': results['total_loans']},
                    {'Metric': f"Total Balance ({config['currency_code']})", 'Value': results['total_balance']},
                    {'Metric': f"Total EAD ({config['currency_code']})", 'Value': results.get('total_ead', 0)},
                    {'Metric': f"Total Collateral ({config['currency_code']})", 'Value': results['total_security']},
                    {'Metric': '', 'Value': ''},
                    {'Metric': f"IFRS 9 ECL Provision ({config['currency_code']})", 'Value': results['ifrs9_total']},
                    {'Metric': f"Regulatory Provision ({config['currency_code']})", 'Value': results['regulatory_total']},
                    {'Metric': f"Gap ({config['currency_code']})", 'Value': results['gap']},
                    {'Metric': f"Final Provision ({config['currency_code']})", 'Value': results['final_total']},
                    {'Metric': 'Status', 'Value': 'UNDER-PROVISIONED' if results['gap'] > 0 else 'COMPLIANT'},
                    {'Metric': 'Overall Coverage Ratio', 'Value': summary.get('overall_coverage_ratio', 0)},
                ]
                pd.DataFrame(exec_rows).to_excel(writer, sheet_name='Executive Summary', index=False)

                # Sheet 2: Stage Distribution
                stage_rows = []
                for s, d in summary.get('by_stage', {}).items():
                    stage_rows.append({
                        'Stage': f'Stage {s}',
                        'Loan Count': d['count'],
                        'Balance': d['balance'],
                        'EAD': d['ead'],
                        'ECL': d['ecl'],
                        'Coverage Ratio': d['coverage_ratio'],
                        '% of Book': d['balance_pct'],
                    })
                if stage_rows:
                    pd.DataFrame(stage_rows).to_excel(writer, sheet_name='Stage Distribution', index=False)

                # Sheet 3: Loan-Level Detail
                detail_cols = [c for c in [
                    'loan_id', 'outstanding_balance', 'days_past_due', 'collateral_value',
                    'credit_score', 'ifrs9_stage', 'stage_label', 'staging_reason',
                    'pd_12_month', 'pd_lifetime', 'pd_used', 'risk_grade',
                    'lgd', 'lgd_method', 'ead',
                    'ecl_base', 'ecl_final', 'discount_factor',
                    'ifrs9_provision', 'ifrs9_rate', 'coverage_ratio',
                    'reg_classification', 'reg_provision', 'gap', 'final_provision',
                ] if c in df.columns]
                df[detail_cols].to_excel(writer, sheet_name='Loan Details', index=False)

                # Sheet 4: Risk Grades
                grade_rows = []
                for g, d in sorted(summary.get('by_risk_grade', {}).items()):
                    grade_rows.append({
                        'Risk Grade': g,
                        'Loan Count': d['count'],
                        'Balance': d['balance'],
                        'ECL': d['ecl'],
                        'Average PD': d['avg_pd'],
                    })
                if grade_rows:
                    pd.DataFrame(grade_rows).to_excel(writer, sheet_name='Risk Grades', index=False)

                # Sheet 5: Loss Forecast
                if forecast and 'forecasts' in forecast:
                    forecast_rows = []
                    for f in forecast['forecasts']:
                        forecast_rows.append({
                            'Month': f['forecast_date'],
                            'Expected Loss': f['expected_loss'],
                            'Forecasted Balance': f['forecasted_balance'],
                            'Provision Needed': f['forecasted_provision'],
                        })
                    pd.DataFrame(forecast_rows).to_excel(writer, sheet_name='Loss Forecast', index=False)

                # Sheet 6: Sensitivity Analysis
                if sensitivity:
                    pd_shock_rows = [{
                        'Scenario': s['scenario'], 'PD Factor': s['pd_multiplier'],
                        'ECL': s['ecl'], 'Change': s['change_from_base'],
                        'Change %': s['change_pct'], 'Coverage': s['coverage_ratio'],
                    } for s in sensitivity.get('pd_shocks', [])]
                    if pd_shock_rows:
                        pd.DataFrame(pd_shock_rows).to_excel(writer, sheet_name='PD Sensitivity', index=False)

                    lgd_shock_rows = [{
                        'Scenario': s['scenario'], 'LGD Factor': s['lgd_multiplier'],
                        'ECL': s['ecl'], 'Change': s['change_from_base'],
                        'Change %': s['change_pct'],
                    } for s in sensitivity.get('lgd_shocks', [])]
                    if lgd_shock_rows:
                        pd.DataFrame(lgd_shock_rows).to_excel(writer, sheet_name='LGD Sensitivity', index=False)

                    combined_rows = [{
                        'Scenario': s['scenario'], 'PD Factor': s['pd_multiplier'],
                        'LGD Factor': s['lgd_multiplier'], 'ECL': s['ecl'],
                        'Change %': s['change_pct'],
                    } for s in sensitivity.get('combined', [])]
                    if combined_rows:
                        pd.DataFrame(combined_rows).to_excel(writer, sheet_name='Combined Stress', index=False)

                # Sheet 7: Vintage Analysis
                if vintage and vintage.get('by_vintage'):
                    pd.DataFrame(vintage['by_vintage']).to_excel(writer, sheet_name='Vintage Analysis', index=False)
                    if vintage.get('dpd_by_vintage'):
                        pd.DataFrame(vintage['dpd_by_vintage']).to_excel(writer, sheet_name='Vintage DPD Heatmap', index=False)

                # Sheet 8-10: Cohort Analysis
                if cohort:
                    if cohort.get('by_product'):
                        pd.DataFrame(cohort['by_product']).to_excel(
                            writer, sheet_name='Product Breakdown', index=False)
                    if cohort.get('by_security'):
                        pd.DataFrame(cohort['by_security']).to_excel(
                            writer, sheet_name='Secured vs Unsecured', index=False)
                    if cohort.get('by_dpd_bucket'):
                        pd.DataFrame(cohort['by_dpd_bucket']).to_excel(
                            writer, sheet_name='DPD Buckets', index=False)

                # Sheet 11: Regulatory Rules Used
                pd.DataFrame(config['regulatory_rules']).to_excel(
                    writer, sheet_name='Regulatory Rules', index=False
                )

            st.download_button(
                "Download Excel Report",
                data=excel_buffer.getvalue(),
                file_name=f"IFRS9_Report_{config['institution_name'].replace(' ', '_')}_{config['reporting_date']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with col2:
            st.markdown("### PDF Report (Professional)")

            try:
                pdf_bytes = generate_pdf_report(
                    config=config,
                    results=results,
                    summary=summary,
                    sensitivity=sensitivity,
                    vintage=vintage,
                    forecast=forecast,
                    cohort=cohort,
                )
                st.download_button(
                    "Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"IFRS9_Report_{config['institution_name'].replace(' ', '_')}_{config['reporting_date']}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"PDF generation failed: {e}")
                st.info("Install fpdf2: `pip install fpdf2`")

        with col3:
            st.markdown("### JSON Export (API)")

            export_data = {
                'institution': {k: str(v) for k, v in config.items() if k != 'regulatory_rules'},
                'regulatory_rules': config.get('regulatory_rules', []),
                'results': {
                    'total_loans': results['total_loans'],
                    'total_balance': results['total_balance'],
                    'total_ead': results.get('total_ead', 0),
                    'ifrs9_provision': results['ifrs9_total'],
                    'regulatory_provision': results['regulatory_total'],
                    'gap': results['gap'],
                    'final_provision': results['final_total'],
                    'overall_coverage_ratio': summary.get('overall_coverage_ratio', 0),
                },
                'stage_distribution': {
                    f"stage_{s}": {
                        'count': d['count'],
                        'balance': d['balance'],
                        'ecl': d['ecl'],
                        'coverage_ratio': d['coverage_ratio'],
                    }
                    for s, d in summary.get('by_stage', {}).items()
                },
                'methodology': {
                    'ecl_formula': 'EAD x LGD x PD x Macro x Discount',
                    'market': config['country_code'],
                    'multi_scenario': True,
                    'scenario_weights': get_market_config(config['country_code'])['scenario_weights'],
                },
            }

            st.download_button(
                "Download JSON",
                data=json.dumps(export_data, indent=2, default=str),
                file_name=f"IFRS9_Data_{config['reporting_date']}.json",
                mime="application/json",
                use_container_width=True
            )

        st.markdown("---")

        # Navigation
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back"):
                st.session_state.step = 4
                st.rerun()
        with col2:
            if st.button("Start New Calculation", type="primary"):
                st.session_state.step = 1
                st.session_state.results = None
                st.session_state.loan_data = None
                st.session_state.column_mapping = None
                st.rerun()

# Sidebar help
st.sidebar.markdown("---")
st.sidebar.markdown("### Need Help?")
st.sidebar.markdown("""
**Current Step:** {}/5

**Quick Guide:**
1. Setup institution details
2. Configure provision rules
3. Upload loan data (any format)
4. Calculate provisions (full ECL)
5. Download reports

**Supported Countries:**
KE, NG, UG, TZ, RW, GH, ZA

**Support:** support@creditbox.io
""".format(st.session_state.step))

# Footer
st.markdown("---")
st.caption("IFRS 9 Dual Provisioning Platform v3.0 | Full ECL Engine | CreditBox")
