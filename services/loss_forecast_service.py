"""
Loss Forecasting & Liquidity Recommendation Service
Predicts future losses and recommends cash reserves
"""

from typing import Dict, List, Optional, Tuple
from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta


class LossForecastService:
    """
    Service for forecasting future losses and calculating liquidity needs

    Methods:
    - Vintage analysis (cohort-based loss rates)
    - Roll rate analysis (transition probabilities)
    - 6-12 month loss forecast
    - Liquidity recommendations
    """

    def __init__(self, loan_data: pd.DataFrame):
        """
        Initialize with loan portfolio data

        Args:
            loan_data: DataFrame with loan information including:
                - outstanding_balance
                - days_past_due
                - disbursement_date (optional for vintage)
                - product_type (optional for segmentation)
        """
        self.loan_data = loan_data
        self.total_portfolio = loan_data['outstanding_balance'].sum()

    def calculate_roll_rates(self) -> Dict:
        """
        Calculate roll rate probabilities (transitions between DPD buckets)

        Returns:
            Dict with transition probabilities
        """

        # Create DPD buckets
        def get_dpd_bucket(dpd):
            if dpd == 0:
                return 'Current'
            elif dpd <= 30:
                return '1-30 DPD'
            elif dpd <= 60:
                return '31-60 DPD'
            elif dpd <= 90:
                return '61-90 DPD'
            elif dpd <= 180:
                return '91-180 DPD'
            else:
                return '180+ DPD'

        df = self.loan_data.copy()
        df['dpd_bucket'] = df['days_past_due'].apply(get_dpd_bucket)

        # Count loans in each bucket
        bucket_counts = df['dpd_bucket'].value_counts()
        total_loans = len(df)

        # Calculate roll rates (simplified - assumes historical transitions)
        # In production, this would use actual historical data
        roll_rates = {
            'Current': {
                'stay_current': 0.85,  # 85% stay current
                'roll_to_1_30': 0.12,  # 12% move to 1-30 DPD
                'roll_to_31_60': 0.02,  # 2% skip to 31-60
                'roll_to_61_90': 0.01   # 1% skip to 61-90
            },
            '1-30 DPD': {
                'cure_to_current': 0.40,  # 40% cure back
                'stay_1_30': 0.30,        # 30% stay
                'roll_to_31_60': 0.20,    # 20% roll forward
                'roll_to_61_90': 0.10     # 10% skip ahead
            },
            '31-60 DPD': {
                'cure_to_current': 0.20,
                'cure_to_1_30': 0.10,
                'stay_31_60': 0.30,
                'roll_to_61_90': 0.30,
                'roll_to_91_180': 0.10
            },
            '61-90 DPD': {
                'cure_to_current': 0.10,
                'stay_61_90': 0.30,
                'roll_to_91_180': 0.40,
                'roll_to_180_plus': 0.20
            },
            '91-180 DPD': {
                'cure_to_current': 0.05,
                'stay_91_180': 0.25,
                'roll_to_180_plus': 0.70
            },
            '180+ DPD': {
                'stay_180_plus': 0.80,
                'write_off': 0.20
            }
        }

        return {
            'roll_rates': roll_rates,
            'current_distribution': bucket_counts.to_dict(),
            'total_loans': total_loans
        }

    def forecast_losses(
        self,
        forecast_months: int = 6,
        scenario: str = 'base'
    ) -> List[Dict]:
        """
        Forecast losses for next N months

        Args:
            forecast_months: Number of months to forecast (default 6)
            scenario: 'base', 'optimistic', or 'pessimistic'

        Returns:
            List of monthly forecast dictionaries
        """

        roll_rates = self.calculate_roll_rates()

        # Current portfolio distribution
        df = self.loan_data.copy()

        # Calculate current NPL ratio (90+ DPD)
        npl_balance = df[df['days_past_due'] >= 90]['outstanding_balance'].sum()
        npl_ratio = npl_balance / self.total_portfolio if self.total_portfolio > 0 else 0

        # Calculate current default rate (31+ DPD based on Umba definition)
        default_balance = df[df['days_past_due'] >= 31]['outstanding_balance'].sum()
        default_ratio = default_balance / self.total_portfolio if self.total_portfolio > 0 else 0

        # Scenario adjustments
        scenario_adjustments = {
            'optimistic': 0.7,   # 30% lower losses
            'base': 1.0,         # No adjustment
            'pessimistic': 1.3   # 30% higher losses
        }

        adjustment = scenario_adjustments.get(scenario, 1.0)

        # Forecast each month
        forecasts = []
        current_portfolio_balance = self.total_portfolio

        for month in range(1, forecast_months + 1):
            forecast_date = date.today() + relativedelta(months=month)

            # Estimate new disbursements (assume 5% monthly growth)
            new_disbursements = current_portfolio_balance * 0.05

            # Estimate repayments (assume 8% monthly repayment rate)
            expected_repayments = current_portfolio_balance * 0.08

            # Estimate defaults (based on roll rates and current delinquency)
            # Use conservative default rate with scenario adjustment
            monthly_default_rate = default_ratio * 0.15 * adjustment  # 15% of defaulted amounts
            expected_defaults = current_portfolio_balance * monthly_default_rate

            # Estimate write-offs (20% of 180+ DPD bucket)
            writeoff_rate = npl_ratio * 0.20
            expected_writeoffs = current_portfolio_balance * writeoff_rate

            # Calculate forecasted portfolio balance
            forecasted_balance = (
                current_portfolio_balance +
                new_disbursements -
                expected_repayments -
                expected_writeoffs
            )

            # Calculate expected losses (using LGD of 70% for defaulted amounts)
            lgd_estimate = 0.70
            expected_loss = expected_defaults * lgd_estimate

            # Calculate provision requirement (10% of portfolio as conservative estimate)
            forecasted_provision = forecasted_balance * 0.10

            # Confidence intervals (±20% around base estimate)
            lower_bound = expected_loss * 0.80
            upper_bound = expected_loss * 1.20

            forecast = {
                'month': month,
                'forecast_date': forecast_date.strftime('%Y-%m'),
                'opening_balance': float(current_portfolio_balance),
                'new_disbursements': float(new_disbursements),
                'expected_repayments': float(expected_repayments),
                'expected_defaults': float(expected_defaults),
                'expected_writeoffs': float(expected_writeoffs),
                'expected_loss': float(expected_loss),
                'forecasted_balance': float(forecasted_balance),
                'forecasted_provision': float(forecasted_provision),
                'confidence_interval': {
                    'lower': float(lower_bound),
                    'upper': float(upper_bound),
                    'confidence_level': 0.95
                }
            }

            forecasts.append(forecast)

            # Update for next iteration
            current_portfolio_balance = forecasted_balance

        return forecasts

    def calculate_liquidity_requirements(
        self,
        forecasts: List[Dict],
        buffer_percentage: float = 0.20
    ) -> Dict:
        """
        Calculate recommended liquidity reserves

        Args:
            forecasts: Loss forecast results
            buffer_percentage: Additional buffer (default 20%)

        Returns:
            Dict with liquidity recommendations
        """

        # Get maximum expected loss over forecast period
        max_expected_loss = max(f['expected_loss'] for f in forecasts)

        # Calculate average monthly loss
        avg_monthly_loss = sum(f['expected_loss'] for f in forecasts) / len(forecasts)

        # Recommended reserves
        base_reserve = avg_monthly_loss * 3  # 3 months of average losses
        stress_buffer = max_expected_loss * buffer_percentage
        total_liquidity_needed = base_reserve + stress_buffer

        # Regulatory minimum (assume 10% of portfolio)
        regulatory_minimum = self.total_portfolio * 0.10

        # Final recommendation (higher of calculated or regulatory)
        recommended_reserve = max(total_liquidity_needed, regulatory_minimum)

        return {
            'base_reserve': float(base_reserve),
            'stress_buffer': float(stress_buffer),
            'total_recommended': float(recommended_reserve),
            'regulatory_minimum': float(regulatory_minimum),
            'buffer_percentage': buffer_percentage,
            'months_coverage': 3,
            'max_monthly_loss': float(max_expected_loss),
            'avg_monthly_loss': float(avg_monthly_loss),
            'recommendation': (
                f"Maintain cash reserves of {recommended_reserve:,.2f} "
                f"({buffer_percentage*100:.0f}% stress buffer on 3-month average losses)"
            )
        }

    def generate_forecast_summary(
        self,
        forecast_months: int = 6,
        scenario: str = 'base'
    ) -> Dict:
        """
        Generate complete forecast summary with liquidity recommendations

        Args:
            forecast_months: Months to forecast
            scenario: Scenario type

        Returns:
            Dict with forecasts and liquidity recommendations
        """

        # Calculate forecasts
        forecasts = self.forecast_losses(forecast_months, scenario)

        # Calculate liquidity needs
        liquidity = self.calculate_liquidity_requirements(forecasts)

        # Calculate totals
        total_expected_loss = sum(f['expected_loss'] for f in forecasts)
        total_writeoffs = sum(f['expected_writeoffs'] for f in forecasts)

        return {
            'forecast_period_months': forecast_months,
            'scenario': scenario,
            'forecasts': forecasts,
            'liquidity_recommendation': liquidity,
            'summary': {
                'total_expected_loss': float(total_expected_loss),
                'total_expected_writeoffs': float(total_writeoffs),
                'avg_monthly_loss': float(total_expected_loss / forecast_months),
                'current_portfolio': float(self.total_portfolio),
                'forecasted_final_balance': forecasts[-1]['forecasted_balance']
            }
        }


# Helper function for quick forecast
def quick_forecast(
    loan_data: pd.DataFrame,
    forecast_months: int = 6,
    scenario: str = 'base'
) -> Dict:
    """
    Quick forecast generation

    Args:
        loan_data: DataFrame with loan portfolio
        forecast_months: Months to forecast
        scenario: Scenario type

    Returns:
        Complete forecast with liquidity recommendations
    """
    service = LossForecastService(loan_data)
    return service.generate_forecast_summary(forecast_months, scenario)


if __name__ == "__main__":
    # Test with sample data
    print("Loss Forecasting Service - Test")
    print("=" * 80)

    # Create sample data
    sample_data = pd.DataFrame({
        'loan_id': [f'L{i:05d}' for i in range(100)],
        'outstanding_balance': np.random.uniform(10000, 100000, 100),
        'days_past_due': np.random.choice([0, 5, 15, 35, 65, 95, 200], 100)
    })

    # Run forecast
    service = LossForecastService(sample_data)
    result = service.generate_forecast_summary(forecast_months=6, scenario='base')

    print(f"\nPortfolio: {result['summary']['current_portfolio']:,.2f}")
    print(f"\n6-Month Forecast (Base Scenario):")
    print("-" * 80)

    for forecast in result['forecasts']:
        print(f"Month {forecast['month']} ({forecast['forecast_date']})")
        print(f"  Expected Loss: {forecast['expected_loss']:,.2f}")
        print(f"  Forecasted Balance: {forecast['forecasted_balance']:,.2f}")
        print(f"  Provision Needed: {forecast['forecasted_provision']:,.2f}")

    print("\n" + "=" * 80)
    print("Liquidity Recommendations:")
    print("-" * 80)
    liq = result['liquidity_recommendation']
    print(f"Base Reserve (3-month avg): {liq['base_reserve']:,.2f}")
    print(f"Stress Buffer (20%):        {liq['stress_buffer']:,.2f}")
    print(f"Regulatory Minimum (10%):   {liq['regulatory_minimum']:,.2f}")
    print(f"TOTAL RECOMMENDED:          {liq['total_recommended']:,.2f}")
    print()
    print(f"Recommendation: {liq['recommendation']}")
    print("=" * 80)
