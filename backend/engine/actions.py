"""Action system — 9 basic actions + attack of opportunity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.models.enums import (
    AOO_EXEMPT_ACTIONS, Action, CardType, GameEvent, Skill,
)

if TYPE_CHECKING:
    from backend.cards.registry import CardRegistry
    from backend.engine.damage import DamageEngine
    from backend.engine.event_bus import EventBus, EventContext
    from backend.engine.skill_test import SkillTestEngine
    from backend.engine.slots import SlotManager
    from backend.models.chaos import ChaosBag
    from backend.models.state import CardInstance, GameState, InvestigatorState


class ActionResolver:
    def __init__(
        self,
        game_state: GameState,
        event_bus: EventBus,
        skill_test_engine: SkillTestEngine,
        damage_engine: DamageEngine,
        slot_managers: dict[str, SlotManager],
        card_registry: CardRegistry | None = None,
    ) -> None:
        self.game_state = game_state
        self.bus = event_bus
        self.skill_test = skill_test_engine
        self.damage = damage_engine
        self.slot_managers = slot_managers
        self.card_registry = card_registry

    def perform_action(
        self,
        investigator_id: str,
        action: Action,
        **kwargs,
    ) -> bool:
        """Perform an action, handling AoO and action cost. Returns success."""
        inv = self.game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        
        # Fast actions (e.g. playing a Fast card) do not cost an action
        is_fast = kwargs.get("fast", False)
        if not is_fast and inv.actions_remaining <= 0:
            return False

        # Check attack of opportunity (only for non-fast actions)
        if not is_fast and action not in AOO_EXEMPT_ACTIONS:
            self._resolve_attacks_of_opportunity(investigator_id)

        # Spend action (only if not fast)
        if not is_fast:
            inv.actions_remaining -= 1

        # Emit action performed
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.ACTION_PERFORMED,
            investigator_id=investigator_id,
            action=action,
        )
        self.bus.emit(ctx)

        # Dispatch to specific action
        handlers = {
            Action.INVESTIGATE: self._investigate,
            Action.MOVE: self._move,
            Action.DRAW: self._draw,
            Action.RESOURCE: self._resource,
            Action.FIGHT: self._fight,
            Action.ENGAGE: self._engage,
            Action.EVADE: self._evade,
            Action.PLAY: self._play,
            Action.TOME_ACTIVATE: self._tome_activate,
        }

        handler = handlers.get(action)
        if handler:
            return handler(investigator_id, **kwargs)
        return True

    def _resolve_attacks_of_opportunity(self, investigator_id: str) -> None:
        enemies = self.game_state.get_ready_engaged_enemies(investigator_id)
        for enemy in enemies:
            enemy_data = self.game_state.get_card_data(enemy.card_id)
            if enemy_data is None:
                continue

            from backend.engine.event_bus import EventContext
            ctx = EventContext(
                game_state=self.game_state,
                event=GameEvent.ATTACK_OF_OPPORTUNITY,
                investigator_id=investigator_id,
                enemy_id=enemy.instance_id,
            )
            self.bus.emit(ctx)
            if ctx.cancelled:
                continue

            dmg = enemy_data.enemy_damage or 0
            hor = enemy_data.enemy_horror or 0
            self.damage.deal_damage(
                investigator_id, damage=dmg, horror=hor,
                source=enemy.instance_id,
            )
            # AoO does NOT exhaust enemy

    def _investigate(self, investigator_id: str, **kwargs) -> bool:
        inv = self.game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        location = self.game_state.get_location(inv.location_id)
        if location is None:
            return False

        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.INVESTIGATE_ACTION_INITIATED,
            investigator_id=investigator_id,
            location_id=inv.location_id,
        )
        self.bus.emit(ctx)

        committed = kwargs.get("committed_cards", [])

        def on_success(result):
            if location.clues > 0:
                location.clues -= 1
                inv.clues += 1
                success_ctx = EventContext(
                    game_state=self.game_state,
                    event=GameEvent.CLUE_DISCOVERED,
                    investigator_id=investigator_id,
                    location_id=inv.location_id,
                    amount=1,
                )
                self.bus.emit(success_ctx)

        self.skill_test.run_test(
            investigator_id=investigator_id,
            skill_type=Skill.INTELLECT,
            difficulty=location.shroud,
            committed_card_ids=committed,
            on_success=on_success,
        )
        return True

    def _move(self, investigator_id: str, **kwargs) -> bool:
        inv = self.game_state.get_investigator(investigator_id)
        destination = kwargs.get("destination")
        if inv is None or destination is None:
            return False

        current_loc = self.game_state.get_location(inv.location_id)
        if current_loc is None or destination not in current_loc.connections:
            return False

        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.MOVE_ACTION_INITIATED,
            investigator_id=investigator_id,
            location_id=destination,
        )
        self.bus.emit(ctx)

        # Move engaged enemies with investigator
        inv.location_id = destination
        return True

    def _draw(self, investigator_id: str, **kwargs) -> bool:
        inv = self.game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        if inv.deck:
            card_id = inv.deck.pop(0)
            inv.hand.append(card_id)

            from backend.engine.event_bus import EventContext
            ctx = EventContext(
                game_state=self.game_state,
                event=GameEvent.CARD_DRAWN,
                investigator_id=investigator_id,
                extra={"card_id": card_id},
            )
            self.bus.emit(ctx)
        elif inv.discard:
            # Shuffle discard into deck, draw, take 1 horror
            inv.deck = list(inv.discard)
            inv.discard.clear()
            import random
            random.shuffle(inv.deck)
            card_id = inv.deck.pop(0)
            inv.hand.append(card_id)
            self.damage.deal_damage(investigator_id, horror=1)
        return True

    def _resource(self, investigator_id: str, **kwargs) -> bool:
        inv = self.game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inv.resources += 1

        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.RESOURCES_GAINED,
            investigator_id=investigator_id,
            amount=1,
        )
        self.bus.emit(ctx)
        return True

    def _fight(self, investigator_id: str, **kwargs) -> bool:
        inv = self.game_state.get_investigator(investigator_id)
        enemy_instance_id = kwargs.get("enemy_instance_id")
        weapon_instance_id = kwargs.get("weapon_instance_id")
        if inv is None or enemy_instance_id is None:
            return False

        enemy = self.game_state.get_card_instance(enemy_instance_id)
        enemy_data = self.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or enemy_data is None:
            return False

        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id=investigator_id,
            enemy_id=enemy_instance_id,
            source=weapon_instance_id,
        )
        self.bus.emit(ctx)

        difficulty = enemy_data.enemy_fight or 0
        base_damage = 1  # Default bare-hand damage
        committed = kwargs.get("committed_cards", [])

        def on_success(result):
            self.damage.deal_damage_to_enemy(
                enemy_instance_id, base_damage, source=weapon_instance_id,
                investigator_id=investigator_id,
            )

        def on_failure(result):
            # Check retaliate
            if "retaliate" in (enemy_data.keywords or []):
                dmg = enemy_data.enemy_damage or 0
                hor = enemy_data.enemy_horror or 0
                self.damage.deal_damage(
                    investigator_id, damage=dmg, horror=hor,
                    source=enemy_instance_id,
                )

        self.skill_test.run_test(
            investigator_id=investigator_id,
            skill_type=Skill.COMBAT,
            difficulty=difficulty,
            source_instance_id=weapon_instance_id,
            committed_card_ids=committed,
            on_success=on_success,
            on_failure=on_failure,
        )
        return True

    def _engage(self, investigator_id: str, **kwargs) -> bool:
        inv = self.game_state.get_investigator(investigator_id)
        enemy_instance_id = kwargs.get("enemy_instance_id")
        if inv is None or enemy_instance_id is None:
            return False

        enemy = self.game_state.get_card_instance(enemy_instance_id)
        if enemy is None:
            return False

        # Remove from current location's unengaged list
        for loc in self.game_state.locations.values():
            if enemy_instance_id in loc.enemies:
                loc.enemies.remove(enemy_instance_id)

        # Remove from other investigator's threat area
        for other_inv in self.game_state.investigators.values():
            if enemy_instance_id in other_inv.threat_area:
                other_inv.threat_area.remove(enemy_instance_id)

        # Add to this investigator's threat area
        inv.threat_area.append(enemy_instance_id)

        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.ENEMY_ENGAGED,
            investigator_id=investigator_id,
            enemy_id=enemy_instance_id,
        )
        self.bus.emit(ctx)
        return True

    def _evade(self, investigator_id: str, **kwargs) -> bool:
        inv = self.game_state.get_investigator(investigator_id)
        enemy_instance_id = kwargs.get("enemy_instance_id")
        if inv is None or enemy_instance_id is None:
            return False

        enemy = self.game_state.get_card_instance(enemy_instance_id)
        enemy_data = self.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or enemy_data is None:
            return False

        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.EVADE_ACTION_INITIATED,
            investigator_id=investigator_id,
            enemy_id=enemy_instance_id,
        )
        self.bus.emit(ctx)

        difficulty = enemy_data.enemy_evade or 0
        committed = kwargs.get("committed_cards", [])

        def on_success(result):
            enemy.exhausted = True
            if enemy_instance_id in inv.threat_area:
                inv.threat_area.remove(enemy_instance_id)
            # Place at location unengaged
            location = self.game_state.get_location(inv.location_id)
            if location and enemy_instance_id not in location.enemies:
                location.enemies.append(enemy_instance_id)

            evade_ctx = EventContext(
                game_state=self.game_state,
                event=GameEvent.ENEMY_EVADED,
                investigator_id=investigator_id,
                enemy_id=enemy_instance_id,
            )
            self.bus.emit(evade_ctx)

        def on_failure(result):
            if "alert" in (enemy_data.keywords or []):
                dmg = enemy_data.enemy_damage or 0
                hor = enemy_data.enemy_horror or 0
                self.damage.deal_damage(
                    investigator_id, damage=dmg, horror=hor,
                    source=enemy_instance_id,
                )

        self.skill_test.run_test(
            investigator_id=investigator_id,
            skill_type=Skill.AGILITY,
            difficulty=difficulty,
            committed_card_ids=committed,
            on_success=on_success,
            on_failure=on_failure,
        )
        return True

    def _play(self, investigator_id: str, **kwargs) -> bool:
        inv = self.game_state.get_investigator(investigator_id)
        card_id = kwargs.get("card_id")
        if inv is None or card_id is None:
            return False
        if card_id not in inv.hand:
            return False

        card_data = self.game_state.get_card_data(card_id)
        if card_data is None:
            return False

        # Check fast: fast cards don't cost an action
        is_fast = card_data.fast

        # For non-fast cards, check we have actions remaining
        if not is_fast and inv.actions_remaining <= 0:
            return False

        # Pay cost (check BEFORE spending)
        cost = card_data.cost or 0
        if inv.resources < cost:
            return False
        inv.resources -= cost

        from backend.engine.event_bus import EventContext

        # Remove from hand
        inv.hand.remove(card_id)

        # Spend resources event
        if cost > 0:
            ctx = EventContext(
                game_state=self.game_state,
                event=GameEvent.RESOURCES_SPENT,
                investigator_id=investigator_id,
                amount=cost,
            )
            self.bus.emit(ctx)

        # Spend action (only for non-fast cards)
        if not is_fast:
            inv.actions_remaining -= 1

        if card_data.type == CardType.ASSET:
            return self._play_asset(inv, card_id, card_data)
        elif card_data.type == CardType.EVENT:
            return self._play_event(inv, card_id, card_data)
        return False

    def _play_asset(self, inv, card_id, card_data) -> bool:
        instance_id = self.game_state.next_instance_id()
        card_instance = __import__('backend.models.state', fromlist=['CardInstance']).CardInstance(
            instance_id=instance_id,
            card_id=card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=list(card_data.slots),
        )

        # Initialize uses
        if card_data.uses:
            card_instance.uses = dict(card_data.uses)

        # Handle slots
        slot_mgr = self.slot_managers.get(inv.investigator_id)
        if slot_mgr and card_data.slots:
            slot_mgr.occupy(instance_id, card_data.slots)

        self.game_state.cards_in_play[instance_id] = card_instance
        inv.play_area.append(instance_id)

        # Register card abilities
        if self.card_registry:
            self.card_registry.activate_card(card_id, instance_id, self.bus)

        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id=inv.investigator_id,
            target=instance_id,
            extra={"card_id": card_id},
        )
        self.bus.emit(ctx)
        return True

    def _play_event(self, inv, card_id, card_data) -> bool:
        """Play an event card.

        Important: event/skill card implementations are not "in play", so we
        activate a temporary CardImplementation instance here so its
        `@on_event(GameEvent.CARD_PLAYED, ...)` handlers can run.

        We keep the instance registered until `ROUND_ENDS` to support events
        that create temporary lasting effects (e.g. Mind over Matter).
        """
        from backend.engine.event_bus import EventContext
        from backend.models.enums import TimingPriority

        # Activate a temporary implementation instance (if available)
        temp_instance_id = self.game_state.next_instance_id()
        cleanup_entry = None
        if self.card_registry:
            self.card_registry.activate_card(card_id, temp_instance_id, self.bus)

            # Auto-cleanup at end of round to avoid leaking handlers
            def _cleanup(ctx):
                # Deactivate the event instance
                self.card_registry.deactivate_card(temp_instance_id, self.bus)
                # Unregister this cleanup handler
                if cleanup_entry is not None:
                    self.bus.unregister(cleanup_entry)

            cleanup_entry = self.bus.register(
                event=GameEvent.ROUND_ENDS,
                handler=_cleanup,
                priority=TimingPriority.AFTER,
                card_instance_id=temp_instance_id,
            )

        # Emit card played
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.CARD_PLAYED,
            investigator_id=inv.investigator_id,
            source=temp_instance_id,
            extra={"card_id": card_id},
        )
        self.bus.emit(ctx)

        # Event goes to discard after resolution
        inv.discard.append(card_id)
        return True

    def _tome_activate(self, investigator_id: str, **kwargs) -> bool:
        """Daisy Walker extra action: activate a Tome asset."""
        inv = self.game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        # Must be Daisy and have tome action available
        if inv.card_data.id != "daisy_walker" or inv.tome_actions_remaining <= 0:
            return False
        instance_id = kwargs.get("instance_id")
        if not instance_id:
            return False
        ci = self.game_state.get_card_instance(instance_id)
        if ci is None or ci.controller_id != investigator_id:
            return False
        cd = self.game_state.get_card_data(ci.card_id)
        if cd is None or "tome" not in cd.traits:
            return False
        if ci.exhausted:
            return False
        # Consume tome action
        inv.tome_actions_remaining -= 1
        # Exhaust and trigger
        ci.exhausted = True
        # Dispatch to normal asset activation logic
        return self._activate_asset_impl(investigator_id, instance_id, ci, cd)

    def _activate_asset_impl(self, investigator_id: str, instance_id: str, ci: 'CardInstance', cd: 'CardData') -> bool:
        """Shared logic for activating an asset (normal or tome action)."""
        # Emit activation event
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.ASSET_ACTIVATED,
            investigator_id=investigator_id,
            source=instance_id,
            extra={"card_id": cd.id},
        )
        self.bus.emit(ctx)
        # Card-specific activation handled by card implementation via event bus
        return True
