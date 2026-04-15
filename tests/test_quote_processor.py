"""Tests for quote processing and premium calculation."""

import pytest
from bot.quote_processor import QuoteDetails, QuoteProcessor, calculate_premium, BASE_RATES


class TestQuoteDetails:
    def test_is_complete_true(self):
        q = QuoteDetails(
            full_name="Jane Doe",
            coverage_type="life",
            coverage_amount=500_000,
            term_years=10,
        )
        assert q.is_complete() is True

    def test_is_complete_missing_name(self):
        q = QuoteDetails(coverage_type="life", coverage_amount=500_000, term_years=10)
        assert q.is_complete() is False

    def test_is_complete_missing_coverage_type(self):
        q = QuoteDetails(full_name="Jane Doe", coverage_amount=500_000, term_years=10)
        assert q.is_complete() is False

    def test_is_complete_zero_amount(self):
        q = QuoteDetails(full_name="Jane Doe", coverage_type="life", coverage_amount=0, term_years=10)
        assert q.is_complete() is False

    def test_is_complete_zero_term(self):
        q = QuoteDetails(full_name="Jane Doe", coverage_type="life", coverage_amount=500_000, term_years=0)
        assert q.is_complete() is False

    def test_missing_fields_all_missing(self):
        q = QuoteDetails()
        missing = q.missing_fields()
        assert "full name" in missing
        assert "coverage type" in missing
        assert "coverage amount" in missing
        assert "term in years" in missing

    def test_missing_fields_none_missing(self):
        q = QuoteDetails(
            full_name="Jane Doe",
            coverage_type="life",
            coverage_amount=500_000,
            term_years=10,
        )
        assert q.missing_fields() == []

    def test_to_dict(self):
        q = QuoteDetails(full_name="John", coverage_type="auto")
        d = q.to_dict()
        assert d["full_name"] == "John"
        assert d["coverage_type"] == "auto"


class TestCalculatePremium:
    def test_life_coverage(self):
        q = QuoteDetails(coverage_type="life", coverage_amount=500_000, term_years=1)
        premium = calculate_premium(q)
        assert premium == round(500_000 * BASE_RATES["life"], 2)

    def test_health_coverage(self):
        q = QuoteDetails(coverage_type="health", coverage_amount=100_000, term_years=1)
        premium = calculate_premium(q)
        assert premium == round(100_000 * BASE_RATES["health"], 2)

    def test_long_term_discount_10_years(self):
        q_short = QuoteDetails(coverage_type="life", coverage_amount=500_000, term_years=1)
        q_long = QuoteDetails(coverage_type="life", coverage_amount=500_000, term_years=10)
        assert calculate_premium(q_long) < calculate_premium(q_short)

    def test_medium_term_discount_5_years(self):
        q_short = QuoteDetails(coverage_type="life", coverage_amount=500_000, term_years=1)
        q_mid = QuoteDetails(coverage_type="life", coverage_amount=500_000, term_years=5)
        assert calculate_premium(q_mid) < calculate_premium(q_short)

    def test_unknown_coverage_type_uses_default(self):
        q = QuoteDetails(coverage_type="unknown_type", coverage_amount=100_000, term_years=1)
        premium = calculate_premium(q)
        # Should use the default rate of 0.003
        assert premium == round(100_000 * 0.003, 2)


class TestQuoteProcessor:
    def setup_method(self):
        self.processor = QuoteProcessor()

    def test_process_full_data(self):
        raw = {
            "full_name": "Alice Smith",
            "email": "alice@example.com",
            "phone": "0821234567",
            "coverage_type": "property",
            "coverage_amount": 1_000_000,
            "term_years": 20,
            "notes": "Some notes",
        }
        quote = self.processor.process(raw)
        assert quote.full_name == "Alice Smith"
        assert quote.coverage_amount == 1_000_000
        assert quote.term_years == 20
        assert quote.premium_monthly > 0

    def test_process_missing_optional_fields(self):
        raw = {
            "full_name": "Bob Jones",
            "coverage_type": "auto",
            "coverage_amount": 200_000,
            "term_years": 5,
        }
        quote = self.processor.process(raw)
        assert quote.email == ""
        assert quote.phone == ""

    def test_process_zero_amount_no_premium(self):
        raw = {
            "full_name": "Bob Jones",
            "coverage_type": "auto",
            "coverage_amount": 0,
            "term_years": 5,
        }
        quote = self.processor.process(raw)
        assert quote.premium_monthly == 0.0

    def test_summarise(self):
        raw = {
            "full_name": "Carol White",
            "coverage_type": "life",
            "coverage_amount": 500_000,
            "term_years": 10,
        }
        quote = self.processor.process(raw)
        summary = self.processor.summarise(quote)
        assert "Carol White" in summary
        assert "Life" in summary
        assert "500,000" in summary
        assert "10" in summary
