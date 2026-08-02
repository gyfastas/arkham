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
        # Set when a PLAY action fails because of slot limits; consumed by
        # the session layer to build a user-facing slot-conflict response.
        self.last_slot_conflict: dict | None = None

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
        # Auto-detect fast for PLAY action based on card data
        if not is_fast and action == Action.PLAY:
            card_id = kwargs.get("card_id")
            if card_id:
                cd = self.game_state.get_card_data(card_id)
                if cd and cd.fast:
                    is_fast = True
        # TOME_ACTIVATE uses tome_actions_remaining, not regular actions
        if action == Action.TOME_ACTIVATE:
            is_fast = True  # Don't deduct regular actions; _tome_activate handles tome actions
        if not is_fast and inv.actions_remaining <= 0:
            return False

        # Dispatch to specific action handler
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
            # Handler validates (costs, legality) but does NOT deduct actions
            success = handler(investigator_id, **kwargs)
            if not success:
                return False

        # Action validated — now spend the action and trigger AoO
        if not is_fast:
            inv.actions_remaining -= 1

        if not is_fast and action not in AOO_EXEMPT_ACTIONS:
            self._resolve_attacks_of_opportunity(investigator_id)

        # Emit action performed
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.ACTION_PERFORMED,
            investigator_id=investigator_id,
            action=action,
        )
        self.bus.emit(ctx)

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
            effect_card_ids=kwargs.get("effect_card_ids"),
            on_success=on_success,
        )
        return True

    def _move(self, investigator_id: str, **kwargs) -> bool:
        inv = self.game_state.get_investigator(investigator_id)
        destination = kwargs.get("destination") or kwargs.get("location_id")
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

            from backend.engine.draw_hooks import emit_card_drawn
            emit_card_drawn(self.game_state, self.bus, self.card_registry, inv, card_id)
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
        # Target must actually be an enemy (weakness cards attached in the
        # threat area are not valid fight targets).
        from backend.models.enums import CardType
        if enemy_data.type != CardType.ENEMY:
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
            bonus_damage = int(result.extra.get("bonus_damage", 0) or 0)
            self.damage.deal_damage_to_enemy(
                enemy_instance_id, base_damage + bonus_damage, source=weapon_instance_id,
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
            effect_card_ids=kwargs.get("effect_card_ids"),
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
            effect_card_ids=kwargs.get("effect_card_ids"),
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

        # Slot enforcement (assets only) — checked BEFORE paying cost so a
        # failed play changes nothing. Trait-aware (tome-only restricted
        # slots). Two UI flows coexist:
        # - replace_instance_ids: assets chosen to discard for slots upfront
        # - slot_discards / slots_full conflict: server reports the conflict
        #   and the client retries with discards (SlotDiscardModal)
        self.last_slot_conflict = None
        slot_mgr = self.slot_managers.get(investigator_id)

        replacement_ids = list(dict.fromkeys(kwargs.get("replace_instance_ids") or []))
        replacement_instances = []
        if replacement_ids:
            if card_data.type != CardType.ASSET or not card_data.slots:
                return False
            if slot_mgr is None:
                return False

            replacement_instances = []
            for instance_id in replacement_ids:
                if instance_id not in inv.play_area:
                    return False
                instance = self.game_state.get_card_instance(instance_id)
                if instance is None or instance.owner_id != investigator_id:
                    return False
                replacement_instances.append(instance)

            # Simulate freeing the replacements, then run the trait-aware check
            saved_traits = {
                inst.instance_id: slot_mgr.slot_traits.get(inst.instance_id, frozenset())
                for inst in replacement_instances
            }
            for inst in replacement_instances:
                slot_mgr.vacate(inst.instance_id)
            if not slot_mgr.can_play_card(card_data.slots, card_data.traits):
                for inst in replacement_instances:
                    slot_mgr.occupy(inst.instance_id, inst.slot_used, saved_traits[inst.instance_id])
                return False

        if not replacement_ids and (
            card_data.type == CardType.ASSET
            and card_data.slots
            and slot_mgr is not None
            and not slot_mgr.can_play_card(card_data.slots, card_data.traits)
        ):
            discards = kwargs.get("slot_discards") or []
            if not self._try_free_slots(inv, slot_mgr, card_data, discards):
                self.last_slot_conflict = self._build_slot_conflict(
                    inv, slot_mgr, card_data
                )
                return False

        # Pay cost (check BEFORE spending — fail early if can't afford)
        cost = card_data.cost or 0
        if inv.resources < cost:
            return False

        # Remove selected assets only after all validation, including cost,
        # succeeds.
        for instance in replacement_instances:
            from backend.engine.event_bus import EventContext
            self.bus.emit(EventContext(
                game_state=self.game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=investigator_id,
                target=instance.instance_id,
            ))
            if self.card_registry:
                self.card_registry.deactivate_card(instance.instance_id, self.bus)
            slot_mgr.vacate(instance.instance_id)
            if instance.instance_id in inv.play_area:
                inv.play_area.remove(instance.instance_id)
            inv.discard.append(instance.card_id)
            self.game_state.cards_in_play.pop(instance.instance_id, None)

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
            slot_mgr.occupy(instance_id, card_data.slots, card_data.traits)

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

    # ------------------------------------------------------------------
    # Slot helpers
    # ------------------------------------------------------------------
    def _try_free_slots(self, inv, slot_mgr, card_data, discards) -> bool:
        """Discard chosen assets to make room; True if card now fits.

        Safety: if the number of discards cannot possibly satisfy the
        deficit, nothing is discarded (avoids partial irreversible state).
        """
        if slot_mgr.can_play_card(card_data.slots, card_data.traits):
            return True
        if not discards:
            return False
        needed = slot_mgr.slots_to_free_for_card(card_data.slots, card_data.traits)
        if len(discards) < sum(needed.values()):
            return False
        for iid in discards:
            if iid not in inv.play_area:
                return False
        for iid in discards:
            self._discard_asset_for_slots(inv, iid)
        return slot_mgr.can_play_card(card_data.slots, card_data.traits)

    def _discard_asset_for_slots(self, inv, instance_id: str) -> None:
        """Discard an in-play asset: vacate slots, unregister abilities."""
        from backend.engine.event_bus import EventContext

        ci = self.game_state.cards_in_play.pop(instance_id, None)
        if ci is None:
            return
        if instance_id in inv.play_area:
            inv.play_area.remove(instance_id)
        inv.discard.append(ci.card_id)
        slot_mgr = self.slot_managers.get(inv.investigator_id)
        if slot_mgr:
            slot_mgr.vacate(instance_id)
        if self.card_registry:
            self.card_registry.deactivate_card(instance_id, self.bus)
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id=inv.investigator_id,
            target=instance_id,
            extra={"card_id": ci.card_id},
        )
        self.bus.emit(ctx)

    def _build_slot_conflict(self, inv, slot_mgr, card_data) -> dict:
        """Describe the slot shortage and which in-play assets can go."""
        needed = slot_mgr.slots_to_free_for_card(
            card_data.slots, card_data.traits
        )
        candidates = []
        for iid in inv.play_area:
            ci = self.game_state.get_card_instance(iid)
            if ci is None or not ci.slot_used:
                continue
            cd = self.game_state.get_card_data(ci.card_id)
            if cd is None or cd.type != CardType.ASSET:
                continue
            candidates.append({
                "instance_id": iid,
                "id": ci.card_id,
                "name": cd.name,
                "name_cn": cd.name_cn,
                "slots": [s.value for s in ci.slot_used],
            })
        return {
            "card_id": card_data.id,
            "card_name": card_data.name_cn or card_data.name,
            "needed": {st.value: n for st, n in needed.items()},
            "candidates": candidates,
        }

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
        """Extra action: activate a Tome asset using tome_actions_remaining."""
        inv = self.game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        # Must have tome action available
        if inv.tome_actions_remaining <= 0:
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
