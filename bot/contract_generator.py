"""Contract document generator.

Produces a plain-text contract ready to be read back over the phone
or emailed to the client.
"""

from __future__ import annotations

from datetime import date, timedelta

from bot.quote_processor import QuoteDetails


CONTRACT_TEMPLATE = """\
=============================================================
          INSURANCE QUOTATION & CONTRACT AGREEMENT
=============================================================
Contract Reference : {ref}
Date Issued        : {issue_date}
Valid Until        : {valid_until}

POLICYHOLDER DETAILS
---------------------
Full Name          : {full_name}
Contact Number     : {phone}
Email Address      : {email}

COVERAGE DETAILS
----------------
Type of Coverage   : {coverage_type}
Coverage Amount    : R {coverage_amount:,.2f}
Policy Term        : {term_years} year(s)

PREMIUM DETAILS
---------------
Monthly Premium    : R {premium_monthly:,.2f}
Annual Premium     : R {premium_annual:,.2f}
Total Premium      : R {total_premium:,.2f}

TERMS & CONDITIONS
------------------
1. This quotation is valid for 30 days from the date of issue.
2. Coverage commences upon receipt of the first premium payment.
3. All claims must be submitted within 60 days of the incident.
4. This policy is governed by the laws of the Republic of South Africa.
5. ArtradePro reserves the right to adjust premiums upon annual review.

ADDITIONAL NOTES
----------------
{notes}

By proceeding with payment, the policyholder agrees to the above
terms and conditions.

=============================================================
        ArtradePro | Quote 2 Contract Voice Bot Service
=============================================================
"""


class ContractGenerator:
    """Generate a formatted contract document from a completed quote."""

    def generate(self, quote: QuoteDetails, contract_ref: str) -> str:
        issue_date = date.today()
        valid_until = issue_date + timedelta(days=30)
        premium_annual = round(quote.premium_monthly * 12, 2)
        total_premium = round(premium_annual * quote.term_years, 2)

        return CONTRACT_TEMPLATE.format(
            ref=contract_ref,
            issue_date=issue_date.strftime("%d %B %Y"),
            valid_until=valid_until.strftime("%d %B %Y"),
            full_name=quote.full_name or "N/A",
            phone=quote.phone or "N/A",
            email=quote.email or "N/A",
            coverage_type=quote.coverage_type.title() if quote.coverage_type else "N/A",
            coverage_amount=quote.coverage_amount,
            term_years=quote.term_years,
            premium_monthly=quote.premium_monthly,
            premium_annual=premium_annual,
            total_premium=total_premium,
            notes=quote.notes or "None",
        )
