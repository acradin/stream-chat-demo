from dataclasses import dataclass


@dataclass(frozen=True)
class WindowSource:
    handle: int
    pid: int
    title: str
