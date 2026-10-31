import time
from contextlib import contextmanager
from typing import Iterator


def now_ms() -> int:
    return int(time.perf_counter() * 1000)


@contextmanager
def elapsed(name: str, sink: list[dict]) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = int((time.perf_counter() - t0) * 1000)
        sink.append({"name": name, "ms": ms})

