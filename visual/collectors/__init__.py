"""Collettori read-only, uno per fonte. Nessuno apre un file in scrittura."""
from visual.collectors.base import Collector, Reading
from visual.collectors.coordinamento import CoordinamentoCollector
from visual.collectors.cost_alert import CostAlertCollector
from visual.collectors.events import EventStoreCollector
from visual.collectors.kanban import SprintCollector
from visual.collectors.tokens import TokenLedgerCollector

ALL_COLLECTORS = (EventStoreCollector, SprintCollector, CoordinamentoCollector,
                  TokenLedgerCollector, CostAlertCollector)

__all__ = ["Collector", "Reading", "EventStoreCollector", "SprintCollector",
           "TokenLedgerCollector", "CoordinamentoCollector", "CostAlertCollector",
           "ALL_COLLECTORS"]
