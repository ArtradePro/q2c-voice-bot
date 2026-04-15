"""Quote data model and processing logic for the Quote-to-Contract voice bot."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class QuoteDetails:
    """All information gathered from the caller to produce a contract."""

    # Contact
    full_name: str = ""
    email: str = ""
    phone: str = ""

    # Coverage
    coverage_type: str = ""        # e.g. "life", "health", "auto", "property"
    coverage_amount: float = 0.0   # Rands / currency amount
    premium_monthly: float = 0.0

    # Term
    term_years: int = 0

    # Extra notes captured during the call
    notes: str = ""

    def is_complete(self) -> bool:
        """Return True when the minimum required fields are filled."""
        return bool(
            self.full_name
            and self.coverage_type
            and self.coverage_amount > 0
            and self.term_years > 0
        )

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.full_name:
            missing.append("full name")
        if not self.coverage_type:
            missing.append("coverage type")
        if self.coverage_amount <= 0:
            missing.append("coverage amount")
        if self.term_years <= 0:
            missing.append("term in years")
        return missing

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Premium calculator
# ---------------------------------------------------------------------------

BASE_RATES: dict[str, float] = {
    "life": 0.002,
    "health": 0.003,
    "auto": 0.004,
    "property": 0.0025,
}


def calculate_premium(quote: QuoteDetails) -> float:
    """Return the estimated monthly premium for the given quote."""
    coverage_key = quote.coverage_type.lower().strip()
    rate = BASE_RATES.get(coverage_key, 0.003)
    monthly = quote.coverage_amount * rate
    # Slight discount for longer terms
    if quote.term_years >= 10:
        monthly *= 0.90
    elif quote.term_years >= 5:
        monthly *= 0.95
    return round(monthly, 2)


# ---------------------------------------------------------------------------
# Quote processor
# ---------------------------------------------------------------------------


class QuoteProcessor:
    """Parse and enrich a QuoteDetails object extracted by the LLM."""

    def process(self, raw: dict) -> QuoteDetails:
        """Build a QuoteDetails from a raw dictionary (LLM output)."""
        quote = QuoteDetails(
            full_name=raw.get("full_name", ""),
            email=raw.get("email", ""),
            phone=raw.get("phone", ""),
            coverage_type=raw.get("coverage_type", ""),
            coverage_amount=float(raw.get("coverage_amount") or 0),
            term_years=int(raw.get("term_years") or 0),
            notes=raw.get("notes", ""),
        )
        if quote.coverage_amount > 0 and quote.term_years > 0:
            quote.premium_monthly = calculate_premium(quote)
        return quote

    def summarise(self, quote: QuoteDetails) -> str:
        """Return a human-readable summary of the quote."""
        lines = [
            f"Name: {quote.full_name}",
            f"Coverage type: {quote.coverage_type.title()}",
            f"Coverage amount: R{quote.coverage_amount:,.2f}",
            f"Term: {quote.term_years} year(s)",
            f"Estimated monthly premium: R{quote.premium_monthly:,.2f}",
        ]
        if quote.email:
            lines.append(f"Email: {quote.email}")
        return "\n".join(lines)
