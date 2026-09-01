"""The one claim shape shared by the numeric layer, the model layer, and the API response."""

from dataclasses import dataclass

STATES = ("supported", "rounded_up", "contradicted", "unsupported")


@dataclass
class Claim:
    text: str
    start: int
    end: int
    state: str
    reason: str
    fact_id: str | None = None
    source: str = "numeric"

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "state": self.state,
            "fact_id": self.fact_id,
            "reason": self.reason,
        }
