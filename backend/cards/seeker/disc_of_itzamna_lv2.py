"""Disc of Itzamna (Level 2) — Seeker Asset, Accessory slot.
当一个非精英敌人在你的地点生成时，弃置此卡将该敌人弃置。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DiscOfItzamna(CardImplementation):
    card_id = "disc_of_itzamna_lv2"

    # When a non-Elite enemy would spawn at your location, you may
    # discard Disc of Itzamna to discard that enemy instead.
    # This is a complex triggered ability that requires:
    # 1. Enemy spawn event detection
    # 2. Elite trait check
    # 3. Location matching
    # 4. Self-discard mechanic
    #
    # Skeleton — needs ENEMY_ENGAGED or a dedicated ENEMY_SPAWNED event.

    @on_event(
        GameEvent.ENEMY_ENGAGED,
        priority=TimingPriority.WHEN,
    )
    def intercept_spawn(self, ctx):
        """When a non-Elite enemy spawns at your location, discard it.

        Placeholder — full implementation needs:
        - ENEMY_SPAWNED event (not yet in GameEvent enum)
        - Elite trait check on the enemy
        - Self-discard to pay the cost
        - Cancel/discard the spawning enemy
        """
        # TODO: implement when ENEMY_SPAWNED event is available
        pass
