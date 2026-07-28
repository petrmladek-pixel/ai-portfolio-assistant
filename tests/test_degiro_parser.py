import codecs
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
    return """Produkt;Symbol/ISIN;Množství;BPE;Měna;Tržní cena;Hodnota;Unreal. zisk;
Unreal. zisk %
Apple Inc.;US0378331005;10;150,00;USD;170,00;1700,00;200,00;13,33
Microsoft Corp.;US5949181045;5;300,00;USD;320,00;1600,00;100,00;6,67
Flatex Cash;NL0012046714;1000;1,00;EUR;1,00;1000,00;0,00;0,00
""".encode()

@pytest.fixture
def mock_degiro_csv_en():
    return b"""Product;Symbol/ISIN;Quantity;Break-even price;Currency;Market price;
Value;Unreal. profit;Unreal. profit %
Apple Inc.;US0378331005;10;150.00;USD;170.00;1700.00;200.00;13.33
Microsoft Corp.;US5949181045;5;300.00;USD;320.00;1600.00;100.00;6.67
EUR Cash;;1000;1.00;EUR;1.00;1000.00;0.00;0.00
"""

@pytest.fixture
def mock_degiro_csv_comma_delimiter():
    return b"""Product,Symbol/ISIN,Quantity,Break-even price,Currency,Market price,
Value,Unreal. profit,Unreal. profit %
Apple Inc.,US0378331005,10,150.00,USD,170.00,1700.00,200.00,13.33
Microsoft Corp.,US5949181045,5,300.00,USD,320.00,1600.00,100.00,6.67
"""

@pytest.fixture
def mock_degiro_csv_with_bom():
    return codecs.BOM_UTF8 + b"""Product;Symbol/ISIN;Quantity;Break-even price;Currency;
Market price;Value;Unreal. profit;Unreal. profit %
Apple Inc.;US0378331005;10;150.00;USD;170.00;1700.00;200.00;13.33
"""

@pytest.fixture
def mock_degiro_csv_isin_and_symbol():
    return b"""Product;Symbol/ISIN;Quantity;Break-even price;Currency;Market price;
Value;Unreal. profit;Unreal. profit %
Apple Inc.;AAPL - US0378331005;10;150.00;USD;170.00;1700.00;200.00;13.33
"""

def test_degiro_parser_cz(degiro_parser, mock_degiro_csv_cz):
    portfolio = degiro_parser.parse_sync(mock_degiro_csv_cz)
    assert portfolio.broker_name == "DEGIRO"
    assert len(portfolio.positions) == 2

    pos1 = portfolio.positions[0]
    assert pos1.ticker == "AAPL"
    assert pos1.name == "Apple Inc."
    assert pos1.quantity == Decimal("10")
    assert pos1.average_price == Decimal("150.00")
    assert pos1.currency == Currency.USD

    pos2 = portfolio.positions[1]
    assert pos2.ticker == "MSFT"
    assert pos2.name == "Microsoft Corp."
    assert pos2.quantity == Decimal("5")
    assert pos2.average_price == Decimal("300.00")
    assert pos2.currency == Currency.USD

def test_degiro_parser_en(degiro_parser, mock_degiro_csv_en):
    portfolio = degiro_parser.parse_sync(mock_degiro_csv_en)
    assert portfolio.broker_name == "DEGIRO"
    assert len(portfolio.positions) == 2

    pos1 = portfolio.positions[0]
    assert pos1.ticker == "AAPL"
    assert pos1.name == "Apple Inc."
    assert pos1.quantity == Decimal("10")
    assert pos1.average_price == Decimal("150.00")
    assert pos1.currency == Currency.USD

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
    pos1_val = Decimal("10") * Decimal("150.00") # 1500
    pos2_val = Decimal("5") * Decimal("300.00") # 1500
    total_val = pos1_val + pos2_val # 3000

    expected_weight_pos1 = pos1_val / total_val
    expected_weight_pos2 = pos2_val / total_val

    assert anonymized_portfolio.positions[0].weight == expected_weight_pos1
    assert anonymized_portfolio.positions[1].weight == expected_weight_pos2
