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
        """Ready unengaged hunter enemies move toward nearest investigator."""
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

                # Find nearest investigator (simple: check connected locations)
                target_inv = self._find_nearest_investigator(loc.location_id)
                if target_inv is None:
                    continue

                target_loc = target_inv.location_id
                if target_loc == loc.location_id:
                    # Same location: engage
                    loc.enemies.remove(enemy_iid)
                    target_inv.threat_area.append(enemy_iid)
                    self._emit(
                        GameEvent.ENEMY_ENGAGED,
                        investigator_id=target_inv.investigator_id,
                        enemy_id=enemy_iid,
                    )
                elif target_loc in loc.connections:
                    # Move to connected location
                    loc.enemies.remove(enemy_iid)
                    dest = self.game_state.get_location(target_loc)
                    if dest:
                        # Check if investigator is there, engage
                        investigators_at_dest = self.game_state.get_investigators_at_location(target_loc)
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

    def _find_nearest_investigator(self, from_location_id: str):
        """Simple BFS to find nearest investigator."""
        # Check current location first
        at_loc = self.game_state.get_investigators_at_location(from_location_id)
        if at_loc:
            return at_loc[0]

        # BFS through connections
        visited = {from_location_id}
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
                investigators = self.game_state.get_investigators_at_location(conn_id)
                if investigators:
                    return investigators[0]
                queue.append(conn_id)
        return None

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

                self._emit(
                    GameEvent.ENEMY_ATTACKS,
                    investigator_id=inv_id,
                    enemy_id=enemy_iid,
                )

                dmg = enemy_data.enemy_damage or 0
                hor = enemy_data.enemy_horror or 0
                self.damage.deal_damage(
                    inv_id, damage=dmg, horror=hor,
                    source=enemy_iid,
                )

                # Enemy exhausts after attack
                enemy.exhausted = True

    def _emit(self, event: GameEvent, **kwargs) -> None:
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=event,
            **kwargs,
        )
        self.bus.emit(ctx)
