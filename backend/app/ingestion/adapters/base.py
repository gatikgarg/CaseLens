from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol


@dataclass
class Batch:
    table: str
    source_file: str
    records: list[dict]


class TicketSourceAdapter(Protocol):
    name: str

    def extract(self, root: Path) -> Iterator[Batch]: ...

