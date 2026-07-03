from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ExecutionResult, OrderRequest


class Broker(ABC):
    @abstractmethod
    def submit_order(self, order: OrderRequest) -> ExecutionResult:
        raise NotImplementedError
