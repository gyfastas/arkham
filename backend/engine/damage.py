"""Damage and horror system — assign, trigger abilities, apply."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.models.enums import GameEvent

if TYPE_CHECKING:
    from backend.engine.event_bus import EventBus, EventContext
    from backend.models.state import CardInstance, GameState, InvestigatorState


class DamageEngine:
    def __init__(self, game_state: GameState, event_bus: EventBus) -> None:
        self.game_state = game_state
        self.bus = event_bus

    def deal_damage(
        self,
        investigator_id: str,
        damage: int = 0,
        horror: int = 0,
        source: str | None = None,
        direct: bool = False,
        target_instance_id: str | None = None,
    ) -> None:
        """Deal damage and/or horror to an investigator.

        Args:
            investigator_id: Target investigator.
            damage: Amount of damage to deal.
            horror: Amount of horror to deal.
            source: Source card instance_id.
            direct: If True, bypass asset assignment (direct damage/horror).
            target_instance_id: If direct, specific target card instance.
        """
        inv = self.game_state.get_investigator(investigator_id)
        if inv is None:
            return

        if direct and target_instance_id:
            self._apply_direct(target_instance_id, damage, horror)
        else:
            # Step 1: Assignment (for now, auto-assign to investigator)
            # In a full implementation, the player would choose assignment
            assigned_damage = self._assign_to_investigator(inv, damage, horror)

            # Step 2: Emit events for abilities to react
            if damage > 0:
                from backend.engine.event_bus import EventContext
                ctx = EventContext(
                    game_state=self.game_state,
                    event=GameEvent.DAMAGE_ASSIGNED,
                    investigator_id=investigator_id,
                    amount=damage,
                    source=source,
                )
                self.bus.emit(ctx)

            if horror > 0:
                from backend.engine.event_bus import EventContext
                ctx = EventContext(
                    game_state=self.game_state,
                    event=GameEvent.HORROR_ASSIGNED,
                    investigator_id=investigator_id,
                    amount=horror,
                    source=source,
                )
                self.bus.emit(ctx)

            # Step 3: Apply
            self._apply_to_investigator(inv, damage, horror)

        # Check defeat
        self._check_defeat(investigator_id)

    def deal_damage_to_enemy(
        self,
        enemy_instance_id: str,
        damage: int,
        source: str | None = None,
        investigator_id: str | None = None,
    ) -> bool:
        """Deal damage to an enemy. Returns True if enemy defeated."""
        enemy = self.game_state.get_card_instance(enemy_instance_id)
        if enemy is None:
            return False

        enemy_data = self.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return False

        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.DAMAGE_DEALT,
            target=enemy_instance_id,
            amount=damage,
            source=source,
            investigator_id=investigator_id,
        )
        self.bus.emit(ctx)

        enemy.damage += ctx.amount

        if enemy_data.enemy_health and enemy.damage >= enemy_data.enemy_health:
            self._defeat_enemy(enemy_instance_id)
            return True
        return False

    def _assign_to_investigator(self, inv: InvestigatorState, damage: int, horror: int) -> dict:
        """Auto-assign damage/horror. Assets with health/sanity can absorb."""
        # Simple implementation: assign all to investigator
        # A full implementation would let player choose asset assignment
        return {"investigator_damage": damage, "investigator_horror": horror}

    def _apply_to_investigator(self, inv: InvestigatorState, damage: int, horror: int) -> None:
        inv.damage += damage
        inv.horror += horror

    def _apply_direct(self, instance_id: str, damage: int, horror: int) -> None:
        card = self.game_state.get_card_instance(instance_id)
        if card:
            card.damage += damage
            card.horror += horror
            self._check_asset_defeat(instance_id)

    def _check_defeat(self, investigator_id: str) -> None:
        inv = self.game_state.get_investigator(investigator_id)
        if inv and inv.is_defeated:
            from backend.engine.event_bus import EventContext
            ctx = EventContext(
                game_state=self.game_state,
                event=GameEvent.INVESTIGATOR_DEFEATED,
                investigator_id=investigator_id,
            )
            self.bus.emit(ctx)

    def _check_asset_defeat(self, instance_id: str) -> None:
        card = self.game_state.get_card_instance(instance_id)
        if card is None:
            return
        card_data = self.game_state.get_card_data(card.card_id)
        if card_data is None:
            return

        defeated = False
        if card_data.health is not None and card.damage >= card_data.health:
            defeated = True
        if card_data.sanity is not None and card.horror >= card_data.sanity:
            defeated = True

        if defeated:
            from backend.engine.event_bus import EventContext
            ctx = EventContext(
                game_state=self.game_state,
                event=GameEvent.ASSET_DEFEATED,
                target=instance_id,
            )
            self.bus.emit(ctx)
            self._remove_card_from_play(instance_id)

    def _defeat_enemy(self, instance_id: str) -> None:
        from backend.engine.event_bus import EventContext
        enemy = self.game_state.get_card_instance(instance_id)
        if enemy is None:
            return

        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.ENEMY_DEFEATED,
            target=instance_id,
        )
        self.bus.emit(ctx)
        self._remove_enemy_from_play(instance_id)

    def _remove_card_from_play(self, instance_id: str) -> None:
        card = self.game_state.cards_in_play.pop(instance_id, None)
        if card is None:
            return
        inv = self.game_state.get_investigator(card.owner_id)
        if inv and instance_id in inv.play_area:
            inv.play_area.remove(instance_id)
            inv.discard.append(card.card_id)

    def _remove_enemy_from_play(self, instance_id: str) -> None:
        enemy = self.game_state.cards_in_play.pop(instance_id, None)
        if enemy is None:
            return
        # Remove from investigator threat areas
        for inv in self.game_state.investigators.values():
            if instance_id in inv.threat_area:
                inv.threat_area.remove(instance_id)
        # Remove from locations
        for loc in self.game_state.locations.values():
            if instance_id in loc.enemies:
                loc.enemies.remove(instance_id)
        # Add to encounter discard
        self.game_state.scenario.encounter_discard.append(enemy.card_id)

    def heal(
        self,
        target_instance_id: str | None = None,
        investigator_id: str | None = None,
        damage: int = 0,
        horror: int = 0,
    ) -> None:
        """Heal damage and/or horror from a target."""
        if investigator_id:
            inv = self.game_state.get_investigator(investigator_id)
            if inv:
                inv.damage = max(0, inv.damage - damage)
                inv.horror = max(0, inv.horror - horror)
        if target_instance_id:
            card = self.game_state.get_card_instance(target_instance_id)
            if card:
                card.damage = max(0, card.damage - damage)
                card.horror = max(0, card.horror - horror)
