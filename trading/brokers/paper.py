from __future__ import annotations

from .base import Broker
from ..models import ExecutionResult, OrderRequest


class PaperBroker(Broker):
    def __init__(self) -> None:
        self._counter = 0

    def submit_order(self, order: OrderRequest) -> ExecutionResult:
        self._counter += 1
        return ExecutionResult(
            accepted=True,
            reason="paper_fill",
            broker_order_id=f"paper-{self._counter}",
        )
