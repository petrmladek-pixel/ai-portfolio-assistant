"""Tests for the Fio e-Broker CSV parser."""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from portfolio_assistant.models.portfolio import Currency
from portfolio_assistant.services.isin_resolver import YahooISINResolver
from portfolio_assistant.services.parser.fio_broker import FioBrokerPortfolioParser


@pytest.fixture
def fio_parser():
    """Fixture for creating a Fio e-Broker parser."""
    return FioBrokerPortfolioParser()


@pytest.fixture
def mock_isin_resolver():
    """Fixture for creating a mock ISIN resolver."""
    resolver = AsyncMock(spec=YahooISINResolver)
    return resolver


@pytest.fixture
def fio_parser_with_mock_resolver(mock_isin_resolver):
    """Fixture for creating a Fio e-Broker parser with mock ISIN resolver."""
    return FioBrokerPortfolioParser(isin_resolver=mock_isin_resolver)


def test_fio_parser_initialization(fio_parser):
    """Test that the Fio e-Broker parser initializes correctly."""
    assert fio_parser.broker_name == "Fio e-Broker"
    assert isinstance(fio_parser.isin_resolver, YahooISINResolver)


def test_fio_parser_header_mapping(fio_parser):
    """Test that the Fio e-Broker parser correctly maps headers."""
    headers = ["ISIN", "Symbol", "Množství", "Cena", "Měna"]
    header_map = fio_parser._map_headers(headers)

    assert header_map["isin"] == "ISIN"
    assert header_map["symbol"] == "Symbol"
    assert header_map["quantity"] == "Množství"
    assert header_map["price"] == "Cena"
    assert header_map["currency"] == "Měna"


def test_fio_parser_header_mapping_english(fio_parser):
    """Test that the Fio e-Broker parser correctly maps English headers."""
    headers = ["ISIN", "Symbol", "Quantity", "Price", "Currency"]
    header_map = fio_parser._map_headers(headers)

    assert header_map["isin"] == "ISIN"
    assert header_map["symbol"] == "Symbol"
    assert header_map["quantity"] == "Quantity"
    assert header_map["price"] == "Price"
    assert header_map["currency"] == "Currency"


def test_fio_parser_decimal_cleaning(fio_parser):
    """Test that the Fio e-Broker parser correctly cleans Czech decimal formatting."""
    # Test Czech formatting with comma as decimal separator
    result = fio_parser.clean_decimal("1 234,56")
    assert result == Decimal("1234.56")

    # Test with spaces and non-breaking spaces
    result = fio_parser.clean_decimal("1\xa0234,56")
    assert result == Decimal("1234.56")

    # Test standard decimal formatting
    result = fio_parser.clean_decimal("1234.56")
    assert result == Decimal("1234.56")


@pytest.mark.asyncio
async def test_fio_parser_async_parsing_success(
    fio_parser_with_mock_resolver, mock_isin_resolver
):
    """Test asynchronous parsing of Fio e-Broker CSV with successful ISIN resolution."""
    # Create test CSV content with ISINs that need resolution
    csv_content = """ISIN;Symbol;Množství;Cena;Měna
US0378331005;;10;150,50;USD
US5949181045;;5;300,25;USD
"""

    file_content = csv_content.encode("utf-8")

    # Mock ISIN resolution
    mock_isin_resolver.resolve_isin.side_effect = lambda isin: (
        "AAPL" if isin == "US0378331005" else "MSFT"
    )

    # Parse the CSV asynchronously
    portfolio = await fio_parser_with_mock_resolver.parse(file_content)

    # Verify ISIN resolution was called
    mock_isin_resolver.resolve_isin.assert_any_call("US0378331005")
    mock_isin_resolver.resolve_isin.assert_any_call("US5949181045")

    # Verify positions
    assert len(portfolio.positions) == 2

    # Verify first position (resolved AAPL)
    aapl = portfolio.positions[0]
    assert aapl.ticker == "AAPL"
    assert aapl.name == "Asset US0378331005"
    assert aapl.quantity == Decimal("10")
    assert aapl.average_price == Decimal("150.50")
    assert aapl.currency == Currency.USD

    # Verify second position (resolved MSFT)
    msft = portfolio.positions[1]
    assert msft.ticker == "MSFT"
    assert msft.name == "Asset US5949181045"
    assert msft.quantity == Decimal("5")
    assert msft.average_price == Decimal("300.25")
    assert msft.currency == Currency.USD


@pytest.mark.asyncio
async def test_fio_parser_async_parsing_unknown_isin(
    fio_parser_with_mock_resolver, mock_isin_resolver
):
    """Test asynchronous parsing of Fio e-Broker CSV with unresolved ISIN."""
    # Create test CSV content with an ISIN that cannot be resolved
    csv_content = """ISIN;Symbol;Množství;Cena;Měna
INVALID_ISIN;;10;150,50;USD
"""

    file_content = csv_content.encode("utf-8")

    # Mock ISIN resolution to return None (unresolved)
    mock_isin_resolver.resolve_isin.return_value = None

    # Parse the CSV asynchronously
    portfolio = await fio_parser_with_mock_resolver.parse(file_content)

    # Verify ISIN resolution was called
    mock_isin_resolver.resolve_isin.assert_called_once_with("INVALID_ISIN")

    # Verify that unknown ISINs are marked as UNKNOWN with zero values
    assert len(portfolio.positions) == 1
    unknown_asset = portfolio.positions[0]
    assert unknown_asset.ticker == "UNKNOWN"
    assert unknown_asset.name == "Unknown Asset (ISIN: INVALID_ISIN)"
    assert unknown_asset.quantity == Decimal("0.00")
    assert unknown_asset.average_price == Decimal("0.00")
    assert unknown_asset.currency == Currency.USD


@pytest.mark.asyncio
async def test_fio_parser_cp1250_encoding(fio_parser):
    """Test that the Fio e-Broker parser handles CP1250 encoding."""
    # Create test CSV content with Czech characters in CP1250 encoding
    csv_content = """ISIN;Symbol;Množství;Cena;Měna
CZ0009009145;CEZ;100;500,25;CZK
"""

    # Encode as CP1250
    file_content = csv_content.encode("cp1250")

    # Parse the CSV
    portfolio = await fio_parser.parse(file_content)

    # Verify positions
    assert len(portfolio.positions) == 1

    # Verify Czech character handling in name (ticker is ASCII-only)
    cez = portfolio.positions[0]
    assert cez.ticker == "CEZ"
    assert cez.name == "CEZ"
    assert cez.quantity == Decimal("100")
    assert cez.average_price == Decimal("500.25")
    assert cez.currency == Currency.CZK


@pytest.mark.asyncio
async def test_fio_parser_empty_file(fio_parser):
    """Test that the Fio e-Broker parser handles empty files."""
    file_content = b""

    with pytest.raises(ValueError, match="Empty file content provided"):
        await fio_parser.parse(file_content)


@pytest.mark.asyncio
async def test_fio_parser_missing_columns(fio_parser):
    """Test that the Fio e-Broker parser handles missing columns."""
    # Create CSV without required columns
    csv_content = """ISIN;Symbol
US0378331005;AAPL
"""

    file_content = csv_content.encode("utf-8")

    with pytest.raises(ValueError, match="Missing essential columns"):
        await fio_parser.parse(file_content)


@pytest.mark.asyncio
async def test_fio_parser_invalid_numeric_data(fio_parser, capfd):
    """Test that the Fio e-Broker parser handles invalid numeric data."""
    # Create CSV with invalid numeric data
    csv_content = """ISIN;Symbol;Množství;Cena;Měna
US0378331005;AAPL;invalid;150,50;USD
US5949181045;MSFT;5;invalid;USD
"""

    file_content = csv_content.encode("utf-8")

    # Parse the CSV (should skip invalid rows and log errors)
    portfolio = await fio_parser.parse(file_content)

    # Verify only valid positions are included
    assert len(portfolio.positions) == 0  # Both rows have invalid data

    # Capture and verify error output
    captured = capfd.readouterr()
    assert "Skipping row due to numeric parsing error" in captured.out


@pytest.mark.asyncio
async def test_fio_parser_zero_quantity(fio_parser):
    """Test that the Fio e-Broker parser filters out positions with zero quantity."""
    # Create CSV with zero quantity
    csv_content = """ISIN;Symbol;Množství;Cena;Měna
US0378331005;AAPL;0;150,50;USD
US5949181045;MSFT;5;300,25;USD
"""

    file_content = csv_content.encode("utf-8")

    # Parse the CSV
    portfolio = await fio_parser.parse(file_content)

    # Verify only positions with positive quantity are included
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].ticker == "MSFT"


@pytest.mark.asyncio
async def test_fio_parser_zero_price(fio_parser):
    """Test that the Fio e-Broker parser filters out positions with zero price."""
    # Create CSV with zero price
    csv_content = """ISIN;Symbol;Množství;Cena;Měna
US0378331005;AAPL;10;0;USD
US5949181045;MSFT;5;300,25;USD
"""

    file_content = csv_content.encode("utf-8")

    # Parse the CSV
    portfolio = await fio_parser.parse(file_content)

    # Verify only positions with positive price are included
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].ticker == "MSFT"


@pytest.mark.asyncio
async def test_fio_parser_async_fio_symbol(
    fio_parser_with_mock_resolver, mock_isin_resolver
):
    """Test asynchronous parsing of Fio e-Broker CSV with successful ISIN resolution."""
    # Create test CSV content with ISINs that need resolution
    csv_content = """
Symbol;Akcie;Kurz;Majetek;Kusy;Nákup;Prodej;Výnosy;Akcie;Kurz;Majetek;Zisk;Výnos;Detail;
BAACSG;0;0,00;0,00;81;48 105;;;81;403,00;32 643,00;-15 462,28;-32,14%;;
BAAGECBA;0;68,50;0,00;135;15 102;;3 272,50;135;192,20;25 947,00;14 117,86;93,49%;;
"""

    file_content = csv_content.encode("utf-8")

    # Mock ISIN resolution
    mock_isin_resolver.resolve_isin.side_effect = lambda isin: (
        "BAACSG" if isin == "BAACSG" else "BAAGECBA"
    )

    # Parse the CSV asynchronously
    portfolio = await fio_parser_with_mock_resolver.parse(file_content)

    # Verify ISIN resolution was NEVER called (resolved locally via FIO_LOCAL_MAPPINGS)
    mock_isin_resolver.resolve_isin.assert_not_called()

    # Verify positions
    assert len(portfolio.positions) == 2

    # Verify first position (resolved BAACSG)
    pos1 = portfolio.positions[0]
    assert pos1.ticker == "CSG.PR"
    assert pos1.name == "BAACSG"
    assert pos1.quantity == Decimal("81")
    assert pos1.average_price == Decimal("403.00")
    assert pos1.currency == Currency.CZK

    # Verify second position (resolved BAAGECBA)
    pos2 = portfolio.positions[1]
    assert pos2.ticker == "MONET.PR"
    assert pos2.name == "BAAGECBA"
    assert pos2.quantity == Decimal("135")
    assert pos2.average_price == Decimal("192.20")
    assert pos2.currency == Currency.CZK
