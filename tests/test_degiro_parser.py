from decimal import Decimal

import pytest

from portfolio_assistant.models.portfolio import (
    Currency,
)
from portfolio_assistant.services.parser.degiro import DegiroPortfolioParser


@pytest.fixture
def degiro_parser():
    return DegiroPortfolioParser()


# Mock CSV contents for various languages and scenarios
@pytest.fixture
def mock_degiro_csv_cz():
    return """Produkt,Symbol/ISIN,Množství,Uzavírací,Hodnota,,Hodnota v EUR
            ADR ON SONY GROUP CORP,US8356993076,2,"22,29",USD,"16539,18","14547,86"
            ALLIANZ SE,DE0008404005,3,"430,40",EUR,"5595,20","5595,20"
            """.encode()


@pytest.fixture
def mock_degiro_csv_with_bom():
    # Add UTF-8 BOM to the beginning of the CSV content
    bom = b"\xef\xbb\xbf"  # UTF-8 BOM
    csv_content = """Produkt,Symbol/ISIN,Množství,Uzavírací,Hodnota,,Hodnota v EUR
            ADR ON SONY GROUP CORP,US8356993076,1,"100,00",USD,"10000,00","8500,00"
            """.encode()
    return bom + csv_content


def test_degiro_parser_cz(degiro_parser, mock_degiro_csv_cz):
    portfolio = degiro_parser.parse_sync(mock_degiro_csv_cz)
    assert portfolio.broker_name == "DEGIRO"
    assert len(portfolio.positions) == 2

    # Test a USD position
    pos_sony = next(
        (p for p in portfolio.positions if p.name == "ADR ON SONY GROUP CORP"), None
    )
    assert pos_sony is not None
    assert pos_sony.ticker == "US8356993076"
    assert pos_sony.name == "ADR ON SONY GROUP CORP"
    assert pos_sony.quantity == Decimal("2")
    assert pos_sony.average_price == Decimal("22.29")
    assert pos_sony.currency == Currency.USD

    # Test EUR position
    pos_allianz = next((p for p in portfolio.positions if p.name == "ALLIANZ SE"), None)
    assert pos_allianz is not None
    assert pos_allianz.ticker == "DE0008404005"
    assert pos_allianz.name == "ALLIANZ SE"
    assert pos_allianz.quantity == Decimal("3")
    assert pos_allianz.average_price == Decimal("430.40")
    assert pos_allianz.currency == Currency.EUR


@pytest.mark.skip(reason="English DEGIRO format not officially supported")
def test_degiro_parser_comma_delimiter(degiro_parser, mock_degiro_csv_comma_delimiter):
    portfolio = degiro_parser.parse_sync(mock_degiro_csv_comma_delimiter)
    assert portfolio.broker_name == "DEGIRO"
    assert len(portfolio.positions) == 2

    pos1 = portfolio.positions[0]
    assert pos1.ticker == "AAPL"
    assert pos1.name == "Apple Inc."
    assert pos1.quantity == Decimal("10")
    assert pos1.average_price == Decimal("150.00")
    assert pos1.currency == Currency.USD


def test_degiro_parser_with_bom(degiro_parser, mock_degiro_csv_with_bom):
    portfolio = degiro_parser.parse_sync(mock_degiro_csv_with_bom)
    assert portfolio.broker_name == "DEGIRO"
    assert len(portfolio.positions) == 1

    # Test the position with BOM handling
    pos = portfolio.positions[0]
    assert pos.ticker == "US8356993076"
    assert pos.name == "ADR ON SONY GROUP CORP"
    assert pos.quantity == Decimal("1")
    assert pos.average_price == Decimal("100.00")
    assert pos.currency == Currency.USD


@pytest.mark.skip(reason="English DEGIRO format not officially supported")
def test_degiro_parser_isin_and_symbol(degiro_parser, mock_degiro_csv_isin_and_symbol):
    portfolio = degiro_parser.parse_sync(mock_degiro_csv_isin_and_symbol)
    assert portfolio.broker_name == "DEGIRO"
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].ticker == "AAPL"
