from __future__ import annotations

from typing import Protocol


class AirtestAdapter(Protocol):
    def is_available(self) -> bool:
        ...

    def status(self) -> str:
        ...

    def click_enhance(self) -> None:
        ...


class NullAirtestAdapter:
    """Disabled v1 adapter; keeps GUI wiring explicit without importing Airtest."""

    def is_available(self) -> bool:
        return False

    def status(self) -> str:
        return "Airtest adapter disabled in v1"

    def click_enhance(self) -> None:
        raise NotImplementedError("Airtest automation is not connected in v1")
