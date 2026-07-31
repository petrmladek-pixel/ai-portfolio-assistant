"""Tests for currency formatting functionality."""

from decimal import Decimal

from portfolio_assistant.routers.web import format_currency


class TestCurrencyFormatting:
    """Test suite for currency formatting function."""

    def test_format_zero_value(self):
        """Test formatting of exact zero value."""
        result = format_currency(Decimal("0"))
        assert result == "0.00"

    def test_format_negative_value(self):
        """Test formatting of negative values."""
        result = format_currency(Decimal("-1234.56"))
        assert result == "-1 234,56"

    def test_format_large_value(self):
        """Test formatting of large values."""
        result = format_currency(Decimal("1000000"))
        assert result == "1 000 000,00"

    def test_format_small_value(self):
        """Test formatting of small values."""
        result = format_currency(Decimal("12.34"))
        assert result == "12,34"

    def test_format_value_with_many_decimals(self):
        """Test formatting of values with more than 2 decimal places."""
        result = format_currency(Decimal("123.456789"))
        assert result == "123,46"  # Should round to 2 decimal places

    def test_format_very_large_value(self):
        """Test formatting of very large values."""
        result = format_currency(Decimal("1234567890.12"))
        assert result == "1 234 567 890,12"

    def test_format_decimal_with_trailing_zeros(self):
        """Test formatting of values with trailing zeros."""
        result = format_currency(Decimal("100.00"))
        assert result == "100,00"

    def test_format_decimal_with_one_decimal(self):
        """Test formatting of values with one decimal place."""
        result = format_currency(Decimal("100.5"))
        assert result == "100,50"  # Should pad to 2 decimal places

    def test_format_currency_edge_cases(self):
        """Test edge cases for currency formatting."""
        # Very small positive value
        result = format_currency(Decimal("0.01"))
        assert result == "0,01"

        # Very small negative value
        result = format_currency(Decimal("-0.01"))
        assert result == "-0,01"

        # Value with no decimal part
        result = format_currency(Decimal("1000"))
        assert result == "1 000,00"

    def test_format_currency_with_different_thousand_separators(self):
        """Test that thousand separators are correctly placed."""
        # 4 digits - no thousand separator needed
        result = format_currency(Decimal("1234.56"))
        assert result == "1 234,56"

        # 5 digits - one thousand separator
        result = format_currency(Decimal("12345.67"))
        assert result == "12 345,67"

        # 7 digits - two thousand separators
        result = format_currency(Decimal("1234567.89"))
        assert result == "1 234 567,89"

        # 10 digits - three thousand separators
        result = format_currency(Decimal("1234567890.12"))
        assert result == "1 234 567 890,12"
