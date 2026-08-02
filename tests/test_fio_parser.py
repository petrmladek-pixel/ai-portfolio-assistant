from decimal import Decimal

import pytest

from portfolio_assistant.models.portfolio import Currency
from portfolio_assistant.services.parser.fio import FioPortfolioParser


@pytest.mark.asyncio
async def test_fio_parser_real_format():
    parser = FioPortfolioParser()
    # Real format snippet provided by user
    csv_content = (
        "Symbol;Akcie;Kurz;Majetek;Kusy;Nákup;Prodej;Výnosy;Akcie;Kurz;Majetek;Zisk;Výnos;Detail;\n"
        "BAACSG;0;0,00;0,00;81;48 105;;;81;403,00;32 643,00;-15 462,28;-32,14%;;\n"
        "BAAGECBA;0;68,50;0,00;135;15 102;;3 272,50;135;192,20;25 947,00;"
        "14 117,86;93,49%;;\n"
        "CZK;0;1,00;0,00;920;;144 000;-25,94;920;1,00;919,66;-25,94;;;\n"
        "Součet (CZK);;;0,00;;;;13 421,76;;;159 259,66;15 259,66;8,64%;;\n"
    ).encode()

    portfolio = await parser.parse_async_internal(csv_content)

    assert portfolio.broker_name == "FIO e-Broker"
    # CZK and Součet should be skipped
    assert len(portfolio.positions) == 2

    pos1 = portfolio.positions[0]
    assert (
        pos1.ticker == "BAACSG"
    )  # Assuming resolver returns same for now or we mock it
    assert pos1.quantity == Decimal("81")
    assert pos1.average_price == Decimal("403.00")
    assert pos1.currency == Currency.CZK

    pos2 = portfolio.positions[1]
    assert pos2.ticker == "BAAGECBA"
    assert pos2.quantity == Decimal("135")
    assert pos2.average_price == Decimal("192.20")
    assert pos2.currency == Currency.CZK
