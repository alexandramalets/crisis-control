from decimal import Decimal

from app.services.dashboard_service import interpret_score


def test_interpret_score_bands():
    assert interpret_score(Decimal("90")) == "Устойчивое состояние"
    assert interpret_score(Decimal("50")) == "Умеренный риск"
    assert interpret_score(Decimal("45")) == "Повышенный риск"
    assert interpret_score(Decimal("10")) == "Выраженные признаки риска"
