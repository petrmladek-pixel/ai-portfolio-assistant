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

    pos2 = portfolio.positions[1]
    assert pos2.ticker == "MSFT"
    assert pos2.name == "Microsoft Corp."
    assert pos2.quantity == Decimal("5")
    assert pos2.average_price == Decimal("300.00")
    assert pos2.currency == Currency.USD


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
    assert portfolio.positions[0].ticker == "AAPL"


def test_degiro_parser_isin_and_symbol(degiro_parser, mock_degiro_csv_isin_and_symbol):
    portfolio = degiro_parser.parse_sync(mock_degiro_csv_isin_and_symbol)
    assert portfolio.broker_name == "DEGIRO"
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].ticker == "AAPL"


def test_to_anonymized_weights(degiro_parser, mock_degiro_csv_en):
    portfolio = degiro_parser.parse_sync(mock_degiro_csv_en)
    anonymized_portfolio = portfolio.to_anonymized()

    assert anonymized_portfolio.broker_name == "DEGIRO"
    assert len(anonymized_portfolio.positions) == 2

    total_weight = sum(pos.weight for pos in anonymized_portfolio.positions)
    assert total_weight == Decimal("1.00")

    # Verify individual weights are correctly calculated
    pos1_val = Decimal("10") * Decimal("150.00")  # 1500
    pos2_val = Decimal("5") * Decimal("300.00")  # 1500
    total_val = pos1_val + pos2_val  # 3000

    expected_weight_pos1 = pos1_val / total_val
    expected_weight_pos2 = pos2_val / total_val

    assert anonymized_portfolio.positions[0].weight == expected_weight_pos1
    assert anonymized_portfolio.positions[1].weight == expected_weight_pos2
