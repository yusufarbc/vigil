"""Abstract enricher interface. Each enricher adds one type of context to an incident."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import EnrichedIncident, Incident


class Enricher(ABC):
    """A single enrichment step in the pipeline."""

    @abstractmethod
    async def enrich(self, incident: Incident, partial: EnrichedIncident) -> EnrichedIncident:
        """Add enrichment data to partial and return the updated result."""
        ...
