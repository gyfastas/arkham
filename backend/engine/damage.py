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
        damage_assignment: dict[str, int] | None = None,
        horror_assignment: dict[str, int] | None = None,
    ) -> None:
        """Deal damage and/or horror to an investigator.

        Args:
            investigator_id: Target investigator.
            damage: Amount of damage to deal.
            horror: Amount of horror to deal.
            source: Source card instance_id.
            direct: If True, bypass asset assignment (direct damage/horror).
            target_instance_id: If direct, specific target card instance.
            damage_assignment: Optional dict mapping instance_id -> damage to assign
                to allies. Remaining damage goes to investigator.
                e.g. {"inst_milan": 1} assigns 1 damage to Dr. Milan.
            horror_assignment: Same as damage_assignment but for horror.
        """
        inv = self.game_state.get_investigator(investigator_id)
        if inv is None:
            return

        if direct and target_instance_id:
            self._apply_direct(target_instance_id, damage, horror)
        else:
            # Step 1: Assign damage/horror (can go to allies or investigator)
            inv_damage, inv_horror = self._assign_damage(
                inv, damage, horror, damage_assignment, horror_assignment,
            )

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

            # Step 3: Apply remaining to investigator
            self._apply_to_investigator(inv, inv_damage, inv_horror)

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

    def _assign_damage(
        self,
        inv: InvestigatorState,
        damage: int,
        horror: int,
        damage_assignment: dict[str, int] | None = None,
        horror_assignment: dict[str, int] | None = None,
    ) -> tuple[int, int]:
        """Assign damage/horror to allies and investigator.

        If damage_assignment/horror_assignment is provided, apply specified
        amounts to ally assets (must have health/sanity). Remaining goes to
        the investigator.

        Returns (investigator_damage, investigator_horror) after ally soaking.
        """
        inv_damage = damage
        inv_horror = horror

        if damage_assignment:
            for inst_id, amount in damage_assignment.items():
                if amount <= 0 or inv_damage <= 0:
                    continue
                ci = self.game_state.get_card_instance(inst_id)
                if ci is None:
                    continue
                cd = self.game_state.get_card_data(ci.card_id)
                if cd is None or cd.health is None:
                    continue
                # Only soak up to remaining health on the ally
                remaining_hp = cd.health - ci.damage
                actual = min(amount, remaining_hp, inv_damage)
                if actual > 0:
                    ci.damage += actual
                    inv_damage -= actual
                    self._check_asset_defeat(inst_id)

        if horror_assignment:
            for inst_id, amount in horror_assignment.items():
                if amount <= 0 or inv_horror <= 0:
                    continue
                ci = self.game_state.get_card_instance(inst_id)
                if ci is None:
                    continue
                cd = self.game_state.get_card_data(ci.card_id)
                if cd is None or cd.sanity is None:
                    continue
                # Only soak up to remaining sanity on the ally
                remaining_san = cd.sanity - ci.horror
                actual = min(amount, remaining_san, inv_horror)
                if actual > 0:
                    ci.horror += actual
                    inv_horror -= actual
                    self._check_asset_defeat(inst_id)

        return inv_damage, inv_horror

    def get_ally_soak_targets(self, investigator_id: str) -> list[dict]:
        """Return list of allies that can soak damage or horror.

        Each entry: {instance_id, card_id, name, remaining_health, remaining_sanity}
        """
        inv = self.game_state.get_investigator(investigator_id)
        if inv is None:
            return []
        targets = []
        for inst_id in inv.play_area:
            ci = self.game_state.get_card_instance(inst_id)
            if ci is None:
                continue
            cd = self.game_state.get_card_data(ci.card_id)
            if cd is None:
                continue
            if cd.health is None and cd.sanity is None:
                continue
            # Must be an ally (has ally slot or ally trait)
            from backend.models.enums import SlotType
            is_ally = (SlotType.ALLY in (cd.slots or [])
                       or "ally" in (cd.traits or []))
            if not is_ally:
                continue
            remaining_hp = (cd.health - ci.damage) if cd.health is not None else None
            remaining_san = (cd.sanity - ci.horror) if cd.sanity is not None else None
            if (remaining_hp is not None and remaining_hp > 0) or \
               (remaining_san is not None and remaining_san > 0):
                targets.append({
                    "instance_id": inst_id,
                    "card_id": ci.card_id,
                    "name": cd.name,
                    "name_cn": cd.name_cn,
                    "remaining_health": remaining_hp,
                    "remaining_sanity": remaining_san,
                    "health": cd.health,
                    "sanity": cd.sanity,
                    "damage": ci.damage,
                    "horror": ci.horror,
                })
        return targets

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
