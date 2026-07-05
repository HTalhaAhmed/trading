from trading_bot.risk_sizing import position_size_from_risk


def test_position_size_from_risk_basic() -> None:
    size = position_size_from_risk(
        equity=10000,
        risk_pct=0.01,
        entry=2000,
        stop=1995,
        contract_value_per_point=1,
    )
    assert size == 20.0


def test_position_size_returns_zero_on_invalid_stop() -> None:
    size = position_size_from_risk(
        equity=10000,
        risk_pct=0.01,
        entry=2000,
        stop=2000,
    )
    assert size == 0.0
