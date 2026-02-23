"""
Automatic Column Mapping Utility
Maps common loan file formats to IFRS9 standard schema
"""
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Dict, Optional
import numpy as np

class ColumnMapper:
    """
    Automatically detect and map columns from various loan file formats
    to IFRS9 standard schema
    """

    # Common column name mappings
    COLUMN_MAPPINGS = {
        # Loan ID variations
        'loan_id': ['loan_id', 'account', 'loan_number', 'account_number', 'loan_account', 'id',
                     'loan no', 'loan ref', 'loan reference', 'account id', 'loan account number'],

        # Customer ID variations
        'customer_id': ['customer_id', 'borrower_id', 'client_id', 'customer_number', 'client',
                        'borrower', 'client id', 'customer no', 'client national id', 'national id'],

        # Product variations
        'product_type': ['product_type', 'product', 'product_name', 'product_id', 'loan_type',
                         'product name', 'product id', 'loan product', 'facility type'],

        # Principal variations
        'outstanding_principal': ['outstanding_principal', 'olb_principal', 'olb principal',
                                  'principal', 'principal_balance', 'outstanding_balance',
                                  'principal balance', 'principal outstanding', 'outstanding amount'],

        # Interest variations
        'accrued_interest': ['accrued_interest', 'olb_interest', 'olb interest', 'interest_balance',
                             'interest outstanding', 'interest accrued', 'accrued interest',
                             'outstanding interest'],

        # Total balance variations
        'outstanding_balance': ['outstanding_balance', 'total_balance', 'olb_principal_interest',
                                'olb principal + interest', 'total_outstanding', 'total balance',
                                'total outstanding', 'payable total', 'overdue and due principal + interest',
                                'net balance', 'book balance', 'exposure'],

        # DPD variations
        'days_past_due': ['days_past_due', 'dpd', 'days_in_arrears', 'days in arrears', 'arrears',
                          'overdue_days', 'overdue days', 'total days in arrears', 'days overdue',
                          'days past due', 'arrears days', 'delinquency days', 'duration in arrears'],

        # Classification variations
        'classification': ['classification', 'loan_classification', 'loan_status', 'category',
                           'diluted classification', 'risk classification', 'asset classification',
                           'loan class', 'loan category', 'risk category', 'status today'],

        # Dates
        'disbursement_date': ['disbursement_date', 'disbursement date', 'origination_date',
                              'loan_date', 'start_date', 'booking date', 'value date',
                              'date disbursed', 'disbursal date', 'drawdown date'],
        'maturity_date': ['maturity_date', 'maturity date', 'end_date', 'expiry_date',
                          'maturity date date', 'expiry', 'due date', 'final payment date',
                          'loan maturity date'],

        # Interest rate
        'interest_rate': ['interest_rate', 'interest rate', 'rate', 'annual rate', 'lending rate',
                          'nominal rate', 'user defined interest rate'],

        # Collateral
        'collateral_value': ['collateral_value', 'value of collateral to consider', 'collateral',
                             'security_value', 'collateral value', 'security value',
                             'collateral amount', 'security amount', 'guarantee value',
                             'pledged value', 'asset value', 'lien value'],

        # Loan amount (original disbursement)
        'loan_amount': ['loan_amount', 'loan amount', 'disbursed amount', 'approved amount',
                        'sanctioned amount', 'facility amount', 'original amount',
                        'principal disbursed'],

        # Credit score
        'credit_score': ['credit_score', 'credit score', 'risk score', 'score',
                         'customer_risk_score', 'crb score', 'fico score', 'bureau score'],

        # Provision
        'provision': ['provision', 'nov provision', 'dec provision', 'ecl', 'allowance',
                      'impairment', 'reserve', 'expected loss'],
    }

    @staticmethod
    def _normalize(name: str) -> str:
        """Normalize column name: lowercase, strip, replace underscores/hyphens with spaces, collapse whitespace."""
        return ' '.join(str(name).lower().strip().replace('_', ' ').replace('-', ' ').split())

    @classmethod
    def detect_and_map(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Automatically detect column names and map to IFRS9 schema.
        Uses normalized matching (case-insensitive, space/underscore agnostic).
        """
        print("🔍 Auto-detecting columns...")

        df_mapped = df.copy()
        column_map = {}
        used_targets = set()  # Prevent duplicate mappings

        # Build normalized lookup: {normalized_name: target_col}
        norm_lookup = {}
        for target_col, possible_names in cls.COLUMN_MAPPINGS.items():
            for name in possible_names:
                norm_lookup[cls._normalize(name)] = target_col

        # Try exact normalized match first
        for col in df.columns:
            col_norm = cls._normalize(col)
            if col_norm in norm_lookup:
                target = norm_lookup[col_norm]
                if target not in used_targets:
                    column_map[col] = target
                    used_targets.add(target)
                    print(f"  ✓ Mapped '{col}' → '{target}'")

        # Second pass: substring/contains match for remaining targets
        remaining_targets = set(cls.COLUMN_MAPPINGS.keys()) - used_targets
        for target_col in remaining_targets:
            possible_names = cls.COLUMN_MAPPINGS[target_col]
            for col in df.columns:
                if col in column_map:
                    continue
                col_norm = cls._normalize(col)
                for name in possible_names:
                    name_norm = cls._normalize(name)
                    # Check if the column contains the mapping name or vice versa
                    if (name_norm in col_norm or col_norm in name_norm) and len(name_norm) >= 3:
                        column_map[col] = target_col
                        used_targets.add(target_col)
                        print(f"  ✓ Mapped '{col}' → '{target_col}' (fuzzy)")
                        break
                if target_col in used_targets:
                    break

        # Rename columns
        df_mapped = df_mapped.rename(columns=column_map)

        return df_mapped, column_map

    @classmethod
    def transform_to_ifrs9_format(cls, df: pd.DataFrame, market: str = "KE") -> pd.DataFrame:
        """
        Transform any loan file format to IFRS9 standard format
        """
        print("\n🔄 Transforming to IFRS9 format...")

        # Auto-detect and map columns
        df_mapped, column_map = cls.detect_and_map(df)

        # Create new DataFrame with IFRS9 schema
        ifrs9_data = []
        reporting_date = date.today()

        for idx, row in df_mapped.iterrows():
            try:
                loan_record = cls._transform_row(row, market, reporting_date, idx)
                if loan_record:
                    ifrs9_data.append(loan_record)
            except Exception as e:
                print(f"  ⚠️  Row {idx+1} skipped: {e}")

        df_ifrs9 = pd.DataFrame(ifrs9_data)

        print(f"✅ Transformed {len(df_ifrs9)} rows successfully")

        return df_ifrs9

    @classmethod
    def _transform_row(cls, row: pd.Series, market: str, reporting_date: date, idx: int) -> Optional[Dict]:
        """Transform a single row to IFRS9 format"""

        # Required: Loan ID
        if 'loan_id' in row and pd.notna(row['loan_id']):
            loan_id = f"{market}-{row['loan_id']}"
        else:
            loan_id = f"{market}-LOAN-{idx+1:06d}"

        # Required: Customer ID
        if 'customer_id' in row and pd.notna(row['customer_id']):
            customer_id = str(row['customer_id'])
        elif 'loan_id' in row:
            customer_id = f"CUST-{row['loan_id']}"
        else:
            customer_id = f"CUST-{idx+1:06d}"

        # Required: Product Type
        product_type = cls._map_product_type(row.get('product_type', ''))

        # Required: Outstanding Principal
        principal = cls._get_float(row, 'outstanding_principal', 0.0)
        if principal <= 0:
            return None  # Skip invalid loans

        # Optional: Other amounts
        balance = cls._get_float(row, 'outstanding_balance', principal)
        accrued_interest = cls._get_float(row, 'accrued_interest', 0.0)

        # Required: DPD
        dpd = cls._get_dpd(row)

        # Required: Credit Score
        credit_score = cls._get_credit_score(row)

        # Optional: Interest Rate (default to 18%)
        interest_rate = cls._get_float(row, 'interest_rate', 0.18)

        # Optional: Dates
        disbursement_date = cls._get_date(row, 'disbursement_date', reporting_date - timedelta(days=180))
        maturity_date = cls._get_date(row, 'maturity_date', reporting_date + timedelta(days=180))

        # Calculate derived fields
        tenure_months = max(1, (maturity_date - disbursement_date).days // 30)
        months_on_book = max(1, (reporting_date - disbursement_date).days // 30)
        remaining_months = max(0, tenure_months - months_on_book)

        # Collateral
        collateral_value = cls._get_float(row, 'collateral_value', 0.0)
        is_secured = collateral_value > 0

        # Map market code to enum name
        market_mapping = {
            'KE': 'KENYA',
            'NG': 'NIGERIA',
            'UG': 'UGANDA',
            'TZ': 'TANZANIA'
        }
        market_value = market_mapping.get(market, market)
        if market_value not in ['KENYA', 'NIGERIA']:
            market_value = 'KENYA'  # Default

        # Build IFRS9 record
        ifrs9_record = {
            'loan_id': loan_id,
            'customer_id': customer_id,
            'market': market_value,
            'product_type': product_type,
            'disbursement_date': disbursement_date,
            'maturity_date': maturity_date,
            'tenure_months': tenure_months,
            'remaining_months': remaining_months,
            'principal_amount': principal,
            'outstanding_principal': principal,
            'outstanding_balance': balance,
            'accrued_interest': accrued_interest,
            'interest_rate': interest_rate,
            'days_past_due': dpd,
            'max_days_past_due': dpd,
            'par_30_flag': dpd >= 30,
            'par_60_flag': dpd >= 60,
            'par_90_flag': dpd >= 90,
            'customer_risk_score': credit_score,
            'origination_risk_score': credit_score,
            'months_on_book': months_on_book,
            'reporting_date': reporting_date,
            'reporting_period': reporting_date.strftime('%Y-%m'),
            'loan_status': 'ACTIVE',
            'is_restructured': False,
            'is_forbearance': False,
            'is_written_off': dpd >= 90,
            'is_secured': is_secured,
            'collateral_value': collateral_value,
            'collateral_type': 'VEHICLE' if is_secured else 'NONE',
        }

        return ifrs9_record

    @staticmethod
    def _get_float(row: pd.Series, col: str, default: float = 0.0) -> float:
        """Safely get float value"""
        if col in row and pd.notna(row[col]):
            try:
                return float(row[col])
            except:
                return default
        return default

    @staticmethod
    def _get_dpd(row: pd.Series) -> int:
        """Get days past due from various sources"""
        # Try direct DPD column
        if 'days_past_due' in row and pd.notna(row['days_past_due']):
            return int(row['days_past_due'])

        # Try classification mapping
        if 'classification' in row:
            classification_map = {
                'normal': 0,
                'watch': 15,
                'special mention': 25,
                'substandard': 45,
                'doubtful': 75,
                'loss': 120
            }
            classification = str(row['classification']).lower()
            return classification_map.get(classification, 0)

        return 0

    @staticmethod
    def _get_credit_score(row: pd.Series) -> int:
        """Get or estimate credit score"""
        # Try direct score column
        if 'credit_score' in row and pd.notna(row['credit_score']):
            return int(row['credit_score'])

        # Estimate from classification
        if 'classification' in row:
            score_map = {
                'normal': 700,
                'watch': 600,
                'special mention': 550,
                'substandard': 520,
                'doubtful': 460,
                'loss': 400
            }
            classification = str(row['classification']).lower()
            return score_map.get(classification, 650)

        return 650  # Default

    @staticmethod
    def _get_date(row: pd.Series, col: str, default: date) -> date:
        """Safely get date value, handling Excel serial numbers and various formats"""
        if col in row and pd.notna(row[col]):
            try:
                val = row[col]
                # Handle Excel date serial numbers (range 25000-60000 covers ~1968-2064)
                if isinstance(val, (int, float)) and 25000 < float(val) < 60000:
                    return (datetime(1899, 12, 30) + timedelta(days=int(val))).date()
                # Handle numpy int/float
                elif isinstance(val, (np.integer, np.floating)) and 25000 < float(val) < 60000:
                    return (datetime(1899, 12, 30) + timedelta(days=int(val))).date()
                # Handle string dates
                elif isinstance(val, str):
                    return pd.to_datetime(val).date()
                # Handle pandas Timestamp
                elif hasattr(val, 'date'):
                    return val.date()
                # Handle date
                elif isinstance(val, date):
                    return val
            except:
                pass
        return default

    @staticmethod
    def _map_product_type(product_name: str) -> str:
        """Map product name to IFRS9 product type"""
        product_lower = str(product_name).lower()

        # Nano/Micro loans
        if any(word in product_lower for word in ['boost', 'nano', 'mini']):
            return 'NANO_LOAN'
        elif 'micro' in product_lower:
            return 'MICRO_LOAN'

        # Secured loans
        elif any(word in product_lower for word in ['logbook', 'vehicle', 'car']):
            return 'LOGBOOK_LOAN'
        elif any(word in product_lower for word in ['asset', 'equipment', 'machinery', 'dealer', 'floor plan']):
            return 'ASSET_FINANCE'
        elif any(word in product_lower for word in ['mortgage', 'property', 'real estate']):
            return 'MORTGAGE'

        # SME
        elif 'sme' in product_lower:
            return 'SME_UNSECURED'

        # Trade finance
        elif any(word in product_lower for word in ['invoice', 'receivable']):
            return 'INVOICE_FINANCE'
        elif 'trade' in product_lower:
            return 'TRADE_FINANCE'

        # Other
        elif any(word in product_lower for word in ['working capital', 'overdraft']):
            return 'WORKING_CAPITAL'
        else:
            return 'BUSINESS_LOAN'
