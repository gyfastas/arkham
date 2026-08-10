"""Enemy Phase: hunter movement and enemy attacks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.models.enums import GameEvent, Phase

if TYPE_CHECKING:
    from backend.engine.damage import DamageEngine
    from backend.engine.event_bus import EventBus, EventContext
    from backend.models.state import GameState


class EnemyPhase:
    def __init__(
        self,
        game_state: GameState,
        event_bus: EventBus,
        damage_engine: DamageEngine,
    ) -> None:
        self.game_state = game_state
        self.bus = event_bus
        self.damage = damage_engine

    def resolve(self) -> None:
        """Execute the Enemy phase (3.1-3.4)."""
        self.game_state.scenario.current_phase = Phase.ENEMY

        # 3.1: Phase begins
        self._emit(GameEvent.ENEMY_PHASE_BEGINS)

        # 3.2: Hunter enemies move
        self._resolve_hunter_movement()

        # 3.3: Enemy attacks (each investigator in player order)
        self._resolve_enemy_attacks()

        # 3.4: Phase ends
        self._emit(GameEvent.ENEMY_PHASE_ENDS)

    def _resolve_hunter_movement(self) -> None:
        """Ready unengaged hunter enemies move toward nearest investigator.

        Official rule (framework step 3.2): each ready, unengaged enemy with
        the hunter keyword moves to a connecting location, along the shortest
        path towards the nearest investigator — one location per enemy phase.
        Enemies at a location with one or more investigators do not move.
        """
        for loc in self.game_state.locations.values():
            for enemy_iid in list(loc.enemies):
                enemy = self.game_state.get_card_instance(enemy_iid)
                if enemy is None or enemy.exhausted:
                    continue
                enemy_data = self.game_state.get_card_data(enemy.card_id)
                if enemy_data is None:
                    continue
                if "hunter" not in (enemy_data.keywords or []):
                    continue
                # Mind Wipe: blanked enemies lose their text (incl. hunter) this phase
                if self.game_state.scenario.vars.get("mind_wiped", {}).get(enemy_iid):
                    continue

                target_inv, first_hop = self._hunter_first_step(loc.location_id)
                if target_inv is None:
                    continue

                if first_hop is None:
                    # Same location as an investigator: do not move, engage
                    loc.enemies.remove(enemy_iid)
                    target_inv.threat_area.append(enemy_iid)
                    self._emit(
                        GameEvent.ENEMY_ENGAGED,
                        investigator_id=target_inv.investigator_id,
                        enemy_id=enemy_iid,
                    )
                    continue

                # Move one location along the shortest path
                dest = self.game_state.get_location(first_hop)
                if dest is None:
                    continue
                # Barricade: non-Elite enemies cannot move into a barricaded
                # location (they stay put).
                if first_hop in self.game_state.scenario.vars.get("barricaded_locations", []) \
                        and "elite" not in (enemy_data.keywords or []):
                    self._emit(
                        GameEvent.ENEMY_MOVE_BLOCKED,
                        enemy_id=enemy_iid,
                        location_id=first_hop,
                    )
                    continue
                loc.enemies.remove(enemy_iid)
                investigators_at_dest = self.game_state.get_investigators_at_location(first_hop)
                if investigators_at_dest:
                    inv = investigators_at_dest[0]
                    inv.threat_area.append(enemy_iid)
                    self._emit(
                        GameEvent.ENEMY_ENGAGED,
                        investigator_id=inv.investigator_id,
                        enemy_id=enemy_iid,
                    )
                else:
                    dest.enemies.append(enemy_iid)

    def _hunter_first_step(self, from_location_id: str):
        """BFS shortest path to the nearest investigator.

        Returns ``(investigator, first_hop)`` where ``first_hop`` is the
        connecting location the enemy should move to, or ``None`` when the
        nearest investigator is already at ``from_location_id``. Returns
        ``(None, None)`` when no investigator is reachable.
        """
        at_loc = self.game_state.get_investigators_at_location(from_location_id)
        if at_loc:
            return at_loc[0], None

        visited = {from_location_id}
        parent: dict[str, str] = {}
        queue = [from_location_id]
        while queue:
            current = queue.pop(0)
            loc = self.game_state.get_location(current)
            if loc is None:
                continue
            for conn_id in loc.connections:
                if conn_id in visited:
                    continue
                visited.add(conn_id)
                parent[conn_id] = current
                investigators = self.game_state.get_investigators_at_location(conn_id)
                if investigators:
                    # Backtrack to the first hop from the enemy's location
                    node = conn_id
                    while parent.get(node) != from_location_id:
                        node = parent[node]
                    return investigators[0], node
                queue.append(conn_id)
        return None, None

    def _resolve_enemy_attacks(self) -> None:
        for inv_id in self.game_state.player_order:
            inv = self.game_state.get_investigator(inv_id)
            if inv is None:
                continue

            for enemy_iid in list(inv.threat_area):
                enemy = self.game_state.get_card_instance(enemy_iid)
                if enemy is None or enemy.exhausted:
                    continue
                enemy_data = self.game_state.get_card_data(enemy.card_id)
                if enemy_data is None:
                    continue

                ctx = self._emit(
                    GameEvent.ENEMY_ATTACKS,
                    investigator_id=inv_id,
                    enemy_id=enemy_iid,
                )

                # Dodge / On the Lam etc. may cancel the attack entirely
                if not getattr(ctx, "cancelled", False):
                    dmg = enemy_data.enemy_damage or 0
                    hor = enemy_data.enemy_horror or 0
                    self.damage.deal_damage(
                        inv_id, damage=dmg, horror=hor,
                        source=enemy_iid,
                    )

                # Enemy exhausts after attack
                enemy.exhausted = True

    def _emit(self, event: GameEvent, **kwargs):
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=event,
            **kwargs,
        )
        self.bus.emit(ctx)
        return ctx
