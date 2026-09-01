"""Parse the client's fact sheet into numbered facts.

One line is one fact, written as `Label: value`. Lines without a colon are skipped and reported.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fact:
    id: str
    label: str
    value: str


@dataclass
class FactSheet:
    facts: list[Fact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def by_id(self, fact_id: str) -> Fact | None:
        return next((f for f in self.facts if f.id == fact_id), None)


def parse_facts(text: str) -> FactSheet:
    sheet = FactSheet()
    ignored: list[str] = []
    # splitlines handles \r\n from a Windows paste, so a CRLF sheet parses the same as an LF one.
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Split on the first colon only. A value like a URL keeps its own colons intact.
        label, sep, value = line.partition(":")
        if not sep or not label.strip():
            ignored.append(line)
            continue
        sheet.facts.append(Fact(f"F{len(sheet.facts) + 1}", label.strip(), value.strip()))
    if ignored:
        noun = "line" if len(ignored) == 1 else "lines"
        sheet.warnings.append(
            f"{len(ignored)} fact sheet {noun} ignored (no colon): " + "; ".join(ignored)
        )
    return sheet
