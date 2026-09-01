"""Unit tests for the Valuation Engine subsystem."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from portfolio_assistant.exceptions.valuation import ValuationError
from portfolio_assistant.models.portfolio import (
    AnonymizedPortfolio,
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.models.valuation import ValuedPortfolio
from portfolio_assistant.services.market_data.base import BaseMarketDataService
from portfolio_assistant.services.valuation.engine import ValuationService


@pytest.fixture
def mock_market_data_service():
    """Fixture for a mocked BaseMarketDataService."""
    mock_service = AsyncMock(spec=BaseMarketDataService)
    return mock_service


@pytest.fixture
def valuation_service(mock_market_data_service):
    """Fixture for ValuationService with a mocked market data service."""
    return ValuationService(market_data_service=mock_market_data_service)


@pytest.fixture
def sample_imported_portfolio():
    """Fixture for a sample ImportedPortfolio with mixed currencies."""
    return ImportedPortfolio(
        broker_name="TestBroker",
        imported_at=datetime(2023, 1, 1, tzinfo=UTC),
        positions=[
            StockPosition(
                ticker="MSFT",
                name="Microsoft",
                quantity=Decimal("10"),
                average_price=Decimal("100.00"),
                currency=Currency.USD,
            ),
            StockPosition(
                ticker="GOOG",
                name="Google",
                quantity=Decimal("5"),
                average_price=Decimal("200.00"),
                currency=Currency.USD,
            ),
            StockPosition(
                ticker="BMW",
                name="BMW AG",
                quantity=Decimal("20"),
                average_price=Decimal("50.00"),
                currency=Currency.EUR,
            ),
            StockPosition(
                ticker="CEZ",
                name="CEZ AS",
                quantity=Decimal("100"),
                average_price=Decimal("500.00"),
                currency=Currency.CZK,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_value_portfolio_happy_path(
    valuation_service,
    mock_market_data_service,
    sample_imported_portfolio,
):
    """Test valuation of a multi-currency portfolio to CZK (happy path)."""
    # Mock market data responses
    mock_market_data_service.get_current_prices.return_value = {
        "MSFT": Decimal("150.00"),
        "GOOG": Decimal("250.00"),
        "BMW": Decimal("60.00"),
        "CEZ": Decimal("550.00"),
    }

    def get_exchange_rate(from_currency, to_currency):
        rates = {
            Currency.USD: Decimal("22.00"),  # USD to CZK
            Currency.EUR: Decimal("25.00"),  # EUR to CZK
        }
        return rates.get(from_currency)

    mock_market_data_service.get_exchange_rate.side_effect = get_exchange_rate

    valued_portfolio = await valuation_service.value_portfolio_async(
        sample_imported_portfolio,
        target_currency=Currency.CZK,
    )

    assert isinstance(valued_portfolio, ValuedPortfolio)
    assert valued_portfolio.broker_name == "TestBroker"
    assert valued_portfolio.target_currency == Currency.CZK
    assert len(valued_portfolio.positions) == 4
    assert valued_portfolio.total_value > 0

    # MSFT position (USD -> CZK)
    msft_pos = next(p for p in valued_portfolio.positions if p.ticker == "MSFT")
    assert msft_pos.currency_original == Currency.USD
    assert msft_pos.currency_target == Currency.CZK
    assert msft_pos.unit_price_original == Decimal("150.00")
    # 150.00 USD * 22.00 CZK/USD = 3300.00 CZK
    assert msft_pos.unit_price_target == Decimal("3300.00")
    # 10 quantity * 3300.00 CZK = 33000.00 CZK
    assert msft_pos.total_value_target == Decimal("33000.00")

    # GOOG position (USD -> CZK)
    goog_pos = next(p for p in valued_portfolio.positions if p.ticker == "GOOG")
    assert goog_pos.currency_original == Currency.USD
    assert goog_pos.currency_target == Currency.CZK
    assert goog_pos.unit_price_original == Decimal("250.00")
    # 250.00 USD * 22.00 CZK/USD = 5500.00 CZK
    assert goog_pos.unit_price_target == Decimal("5500.00")
    # 5 quantity * 5500.00 CZK = 27500.00 CZK
    assert goog_pos.total_value_target == Decimal("27500.00")

    # CEZ position (CZK -> CZK) - moved up for consistent order for checks
    cez_pos = next(p for p in valued_portfolio.positions if p.ticker == "CEZ")
    assert cez_pos.currency_original == Currency.CZK
    assert cez_pos.currency_target == Currency.CZK
    assert cez_pos.unit_price_original == Decimal("550.00")
    # 550.00 CZK * 1.0 CZK/CZK = 550.00 CZK
    assert cez_pos.unit_price_target == Decimal("550.00")
    # 100 quantity * 550.00 CZK = 55000.00 CZK
    assert cez_pos.total_value_target == Decimal("55000.00")

    # BMW position (EUR -> CZK)
    bmw_pos = next(p for p in valued_portfolio.positions if p.ticker == "BMW")
    assert bmw_pos.currency_original == Currency.EUR
    assert bmw_pos.currency_target == Currency.CZK
    assert bmw_pos.unit_price_original == Decimal("60.00")
    # 60.00 EUR * 25.00 CZK/EUR = 1500.00 CZK
    assert bmw_pos.unit_price_target == Decimal("1500.00")
    # 20 quantity * 1500.00 CZK = 30000.00 CZK
    assert bmw_pos.total_value_target == Decimal("30000.00")

    # Total value check
    expected_total_value = Decimal("33000.00")
    expected_total_value += Decimal("27500.00")
    expected_total_value += Decimal("30000.00")
    expected_total_value += Decimal("55000.00")
    assert valued_portfolio.total_value == expected_total_value

    # Weights check (sum to 1 with reasonable precision)
    total_weights = sum(p.weight for p in valued_portfolio.positions)
    assert total_weights == pytest.approx(Decimal("1.0"))

    # Verify individual weights are correctly calculated
    for pos in valued_portfolio.positions:
        expected_weight = pos.total_value_target / valued_portfolio.total_value
        assert pos.weight == pytest.approx(expected_weight)

    mock_market_data_service.get_current_prices.assert_called_once_with(
        sorted(["MSFT", "GOOG", "BMW", "CEZ"]), None
    )
    assert mock_market_data_service.get_exchange_rate.call_count == 2
    mock_market_data_service.get_exchange_rate.assert_any_call(
        from_currency=Currency.EUR,
        to_currency=Currency.CZK,
    )
    mock_market_data_service.get_exchange_rate.assert_any_call(
        from_currency=Currency.USD,
        to_currency=Currency.CZK,
    )


@pytest.mark.asyncio
async def test_value_portfolio_single_currency(
    valuation_service,
    mock_market_data_service,
):
    """Test valuation when all positions are already in the target currency."""
    portfolio = ImportedPortfolio(
        broker_name="TestBroker",
        imported_at=datetime(2023, 1, 1, tzinfo=UTC),
        positions=[
            StockPosition(
                ticker="CEZ",
                name="CEZ AS",
                quantity=Decimal("100"),
                average_price=Decimal("500.00"),
                currency=Currency.CZK,
            ),
            StockPosition(
                ticker="KOFOLA",
                name="Kofola CS",
                quantity=Decimal("50"),
                average_price=Decimal("300.00"),
                currency=Currency.CZK,
            ),
        ],
    )

    mock_market_data_service.get_current_prices.return_value = {
        "CEZ": Decimal("550.00"),
        "KOFOLA": Decimal("320.00"),
    }

    valued_portfolio = await valuation_service.value_portfolio_async(
        portfolio,
        target_currency=Currency.CZK,
    )

    assert isinstance(valued_portfolio, ValuedPortfolio)
    assert valued_portfolio.target_currency == Currency.CZK
    assert len(valued_portfolio.positions) == 2

    cez_pos = next(p for p in valued_portfolio.positions if p.ticker == "CEZ")
    assert cez_pos.unit_price_original == Decimal("550.00")
    assert cez_pos.currency_original == Currency.CZK
    assert cez_pos.unit_price_target == Decimal("550.00")
    assert cez_pos.currency_target == Currency.CZK
    assert cez_pos.total_value_target == Decimal("55000.00")

    kofola_pos = next(p for p in valued_portfolio.positions if p.ticker == "KOFOLA")
    assert kofola_pos.unit_price_original == Decimal("320.00")
    assert kofola_pos.currency_original == Currency.CZK
    assert kofola_pos.unit_price_target == Decimal("320.00")
    assert kofola_pos.currency_target == Currency.CZK
    assert kofola_pos.total_value_target == Decimal("16000.00")

    expected_total_value = Decimal("55000.00") + Decimal("16000.00")
    assert valued_portfolio.total_value == expected_total_value

    total_weights = sum(p.weight for p in valued_portfolio.positions)
    assert total_weights == pytest.approx(Decimal("1.0"))

    mock_market_data_service.get_current_prices.assert_called_once_with(
        sorted(["CEZ", "KOFOLA"]), None
    )
    mock_market_data_service.get_exchange_rate.assert_not_called()


@pytest.mark.asyncio
async def test_value_portfolio_empty_portfolio(valuation_service):
    """Test valuation of an empty portfolio."""
    empty_portfolio = ImportedPortfolio(
        broker_name="EmptyBroker",
        imported_at=datetime(2023, 1, 1, tzinfo=UTC),
        positions=[],
    )

    valued_portfolio = await valuation_service.value_portfolio_async(empty_portfolio)

    assert isinstance(valued_portfolio, ValuedPortfolio)
    assert valued_portfolio.broker_name == "EmptyBroker"
    assert not valued_portfolio.positions
    assert valued_portfolio.total_value == Decimal("0")
    assert valued_portfolio.target_currency == Currency.CZK


@pytest.mark.asyncio
async def test_value_portfolio_anonymization(
    valuation_service,
    mock_market_data_service,
    sample_imported_portfolio,
):
    """Test the anonymization method of ValuedPortfolio."""
    mock_market_data_service.get_current_prices.return_value = {
        "MSFT": Decimal("150.00"),
        "GOOG": Decimal("250.00"),
        "BMW": Decimal("60.00"),
        "CEZ": Decimal("550.00"),
    }

    rates_dict = {
        Currency.USD: Decimal("22.00"),  # USD to CZK
        Currency.EUR: Decimal("25.00"),  # EUR to CZK
    }

    mock_market_data_service.get_exchange_rate.side_effect = (
        lambda from_currency, to_currency: rates_dict.get(Currency(from_currency))
    )

    valued_portfolio = await valuation_service.value_portfolio_async(
        sample_imported_portfolio,
        target_currency=Currency.CZK,
    )
    anonymized_portfolio = valued_portfolio.to_anonymized()

    assert isinstance(anonymized_portfolio, AnonymizedPortfolio)
    assert anonymized_portfolio.broker_name == valued_portfolio.broker_name
    assert anonymized_portfolio.imported_at == valued_portfolio.imported_at
    assert len(anonymized_portfolio.positions) == len(valued_portfolio.positions)

    for anon_pos, valued_pos in zip(
        anonymized_portfolio.positions, valued_portfolio.positions, strict=False
    ):
        assert anon_pos.ticker == valued_pos.ticker
        assert anon_pos.name == valued_pos.name
        assert anon_pos.weight == valued_pos.weight
        assert anon_pos.currency == valued_pos.currency_original


@pytest.mark.asyncio
async def test_value_portfolio_missing_price_error(
    valuation_service,
    mock_market_data_service,
    sample_imported_portfolio,
):
    """Test error handling for missing ticker prices."""
    mock_market_data_service.get_current_prices.return_value = {
        "MSFT": Decimal("150.00"),
        # GOOG is intentionally missing
        "BMW": Decimal("60.00"),
        "CEZ": Decimal("550.00"),
    }

    with pytest.raises(
        ValuationError, match="Missing or invalid price for ticker: GOOG"
    ):
        await valuation_service.value_portfolio_async(
            sample_imported_portfolio,
            target_currency=Currency.CZK,
        )


@pytest.mark.asyncio
async def test_value_portfolio_negative_price_error(
    valuation_service,
    mock_market_data_service,
    sample_imported_portfolio,
):
    """Test error handling for negative ticker prices."""
    mock_market_data_service.get_current_prices.return_value = {
        "MSFT": Decimal("150.00"),
        "GOOG": Decimal("-250.00"),  # Negative price
        "BMW": Decimal("60.00"),
        "CEZ": Decimal("550.00"),
    }

    with pytest.raises(
        ValuationError, match="Missing or invalid price for ticker: GOOG"
    ):
        await valuation_service.value_portfolio_async(
            sample_imported_portfolio,
            target_currency=Currency.CZK,
        )


@pytest.mark.asyncio
async def test_value_portfolio_market_data_service_price_failure(
    valuation_service,
    mock_market_data_service,
    sample_imported_portfolio,
):
    """Test error handling when market data service fails to fetch prices."""

    mock_market_data_service.get_current_prices.side_effect = Exception("Network error")

    with pytest.raises(ValuationError, match="Failed to fetch market prices"):
        await valuation_service.value_portfolio_async(
            sample_imported_portfolio,
            target_currency=Currency.CZK,
        )


@pytest.mark.asyncio
async def test_value_portfolio_exchange_rate_failure(
    valuation_service,
    mock_market_data_service,
    sample_imported_portfolio,
):
    """Test error handling when market data service fails to fetch exchange rates."""
    mock_market_data_service.get_current_prices.return_value = {
        "MSFT": Decimal("150.00"),
        "GOOG": Decimal("250.00"),
        "BMW": Decimal("60.00"),
        "CEZ": Decimal("550.00"),
    }
    mock_market_data_service.get_exchange_rate.side_effect = (
        lambda from_currency, to_currency: (_ for _ in ()).throw(
            Exception("Exchange rate API down")
        )
    )

    with pytest.raises(
        ValuationError, match="Failed to fetch exchange rate EUR -> CZK"
    ):
        await valuation_service.value_portfolio_async(
            sample_imported_portfolio,
            target_currency=Currency.CZK,
        )
