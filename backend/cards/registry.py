"""Card registry for auto-discovering and managing card implementations."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

from backend.cards.base import CardImplementation

if TYPE_CHECKING:
    from backend.engine.event_bus import EventBus


class CardRegistry:
    def __init__(self) -> None:
        self._implementations: dict[str, type[CardImplementation]] = {}
        self._active_cards: dict[str, CardImplementation] = {}  # instance_id -> impl

    def register_class(self, impl_class: type[CardImplementation]) -> None:
        if impl_class.card_id:
            self._implementations[impl_class.card_id] = impl_class

    def get_implementation(self, card_id: str) -> type[CardImplementation] | None:
        return self._implementations.get(card_id)

    def activate_card(self, card_id: str, instance_id: str, bus: EventBus) -> CardImplementation | None:
        impl_class = self._implementations.get(card_id)
        if impl_class is None:
            return None
        impl = impl_class(instance_id)
        impl.register(bus, instance_id)
        self._active_cards[instance_id] = impl
        return impl

    def deactivate_card(self, instance_id: str, bus: EventBus) -> None:
        impl = self._active_cards.pop(instance_id, None)
        if impl:
            impl.unregister(bus)

    def discover_cards(self, package_path: str = "backend.cards") -> None:
        """Auto-discover CardImplementation subclasses in sub-packages."""
        try:
            package = importlib.import_module(package_path)
        except ImportError:
            return

        package_dir = getattr(package, '__path__', None)
        if package_dir is None:
            return

        for importer, modname, ispkg in pkgutil.walk_packages(
            package_dir, prefix=package_path + "."
        ):
            try:
                module = importlib.import_module(modname)
                for attr_name in dir(module):
                    obj = getattr(module, attr_name)
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, CardImplementation)
                        and obj is not CardImplementation
                        and getattr(obj, 'card_id', '')
                    ):
                        self.register_class(obj)
            except Exception:
                continue

    @property
    def registered_cards(self) -> list[str]:
        return list(self._implementations.keys())

    @property
    def active_instances(self) -> dict[str, CardImplementation]:
        return dict(self._active_cards)
