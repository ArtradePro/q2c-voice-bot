"""Tests for the contract generator."""

import pytest
from datetime import date, timedelta
from bot.contract_generator import ContractGenerator
from bot.quote_processor import QuoteDetails


class TestContractGenerator:
    def setup_method(self):
        self.gen = ContractGenerator()
        self.quote = QuoteDetails(
            full_name="David Kim",
            email="david@example.com",
            phone="0831234567",
            coverage_type="life",
            coverage_amount=500_000,
            premium_monthly=1_000,
            term_years=10,
            notes="Test note",
        )

    def test_contains_contract_reference(self):
        contract = self.gen.generate(self.quote, "Q2C-ABCD1234")
        assert "Q2C-ABCD1234" in contract

    def test_contains_policyholder_name(self):
        contract = self.gen.generate(self.quote, "REF001")
        assert "David Kim" in contract

    def test_contains_coverage_details(self):
        contract = self.gen.generate(self.quote, "REF001")
        assert "500,000.00" in contract
        assert "10" in contract

    def test_contains_premium_details(self):
        contract = self.gen.generate(self.quote, "REF001")
        assert "1,000.00" in contract

    def test_contains_issue_date(self):
        today_str = date.today().strftime("%d %B %Y")
        contract = self.gen.generate(self.quote, "REF001")
        assert today_str in contract

    def test_contains_valid_until(self):
        valid_str = (date.today() + timedelta(days=30)).strftime("%d %B %Y")
        contract = self.gen.generate(self.quote, "REF001")
        assert valid_str in contract

    def test_annual_premium_calculation(self):
        contract = self.gen.generate(self.quote, "REF001")
        # Annual premium = 1000 * 12 = 12,000
        assert "12,000.00" in contract

    def test_total_premium_calculation(self):
        contract = self.gen.generate(self.quote, "REF001")
        # Total premium = 12,000 * 10 = 120,000
        assert "120,000.00" in contract

    def test_missing_optional_fields_show_na(self):
        q = QuoteDetails(
            full_name="Test User",
            coverage_type="auto",
            coverage_amount=200_000,
            premium_monthly=800,
            term_years=5,
        )
        contract = self.gen.generate(q, "REF002")
        assert "N/A" in contract

    def test_notes_included(self):
        contract = self.gen.generate(self.quote, "REF001")
        assert "Test note" in contract
