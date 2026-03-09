"""Skill test engine implementing ST.1 through ST.8."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, Skill, TimingPriority,
)

if TYPE_CHECKING:
    from backend.engine.event_bus import EventBus, EventContext
    from backend.models.chaos import ChaosBag
    from backend.models.state import GameState


@dataclass
class SkillTestResult:
    investigator_id: str
    skill_type: Skill
    difficulty: int
    base_skill: int
    committed_icons: int
    token: ChaosTokenType | None = None
    token_modifier: int = 0
    modified_skill: int = 0
    success: bool = False
    auto_fail: bool = False
    auto_success: bool = False
    source_instance_id: str | None = None


class SkillTestEngine:
    def __init__(self, game_state: GameState, event_bus: EventBus, chaos_bag: ChaosBag) -> None:
        self.game_state = game_state
        self.bus = event_bus
        self.chaos_bag = chaos_bag
        self._current_test: SkillTestResult | None = None

    @property
    def current_test(self) -> SkillTestResult | None:
        return self._current_test

    def run_test(
        self,
        investigator_id: str,
        skill_type: Skill,
        difficulty: int,
        source_instance_id: str | None = None,
        on_success: callable = None,
        on_failure: callable = None,
        committed_card_ids: list[str] | None = None,
    ) -> SkillTestResult:
        """Execute a complete skill test (ST.1 through ST.8)."""
        inv = self.game_state.get_investigator(investigator_id)
        if inv is None:
            raise ValueError(f"Unknown investigator: {investigator_id}")

        base_skill = inv.get_skill(skill_type)
        result = SkillTestResult(
            investigator_id=investigator_id,
            skill_type=skill_type,
            difficulty=difficulty,
            base_skill=base_skill,
            committed_icons=0,
            source_instance_id=source_instance_id,
        )
        self._current_test = result
        self._committed_card_ids = committed_card_ids

        try:
            # ST.1: Determine skill type and begin
            self._st1_begin(result)

            # ST.2: Commit cards
            self._st2_commit(result, committed_card_ids or [])

            # ST.3: Reveal chaos token
            self._st3_reveal(result)

            # ST.4: Resolve chaos token effects
            self._st4_resolve_token(result)

            # ST.5: Determine modified skill value
            self._st5_determine_value(result)

            # ST.6: Determine success/failure
            self._st6_determine_result(result)

            # ST.7: Apply results
            self._st7_apply(result, on_success, on_failure)

            # ST.8: End test
            self._st8_end(result, committed_card_ids or [])

        finally:
            self._current_test = None

        return result

    def _st1_begin(self, result: SkillTestResult) -> None:
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id=result.investigator_id,
            skill_type=result.skill_type,
            difficulty=result.difficulty,
            source=result.source_instance_id,
        )
        self.bus.emit(ctx)

    def _st2_commit(self, result: SkillTestResult, committed_card_ids: list[str]) -> None:
        from backend.engine.event_bus import EventContext
        total_icons = 0
        for card_id in committed_card_ids:
            card_data = self.game_state.get_card_data(card_id)
            if card_data and card_data.skill_icons:
                skill_key = result.skill_type.value
                total_icons += card_data.skill_icons.get(skill_key, 0)
                total_icons += card_data.skill_icons.get("wild", 0)

        result.committed_icons = total_icons

        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id=result.investigator_id,
            skill_type=result.skill_type,
            committed_cards=committed_card_ids,
            amount=total_icons,
        )
        self.bus.emit(ctx)
        # Update in case handlers modified
        result.committed_icons = ctx.amount

    def _st3_reveal(self, result: SkillTestResult) -> None:
        from backend.engine.event_bus import EventContext
        token = self.chaos_bag.draw()
        result.token = token

        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.CHAOS_TOKEN_REVEALED,
            investigator_id=result.investigator_id,
            chaos_token=token,
            source=result.source_instance_id,
        )
        self.bus.emit(ctx)

    def _st4_resolve_token(self, result: SkillTestResult) -> None:
        from backend.engine.event_bus import EventContext
        token = result.token
        if token == ChaosTokenType.AUTO_FAIL:
            result.auto_fail = True
            result.token_modifier = 0
        elif token in (ChaosTokenType.BLESS,):
            result.token_modifier = CHAOS_TOKEN_VALUES.get(token, 0) or 0
        elif token in (ChaosTokenType.CURSE,):
            result.token_modifier = CHAOS_TOKEN_VALUES.get(token, 0) or 0
        else:
            result.token_modifier = CHAOS_TOKEN_VALUES.get(token, 0) or 0

        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id=result.investigator_id,
            chaos_token=token,
            amount=result.token_modifier,
            source=result.source_instance_id,
        )
        self.bus.emit(ctx)
        result.token_modifier = ctx.amount

    def _st5_determine_value(self, result: SkillTestResult) -> None:
        from backend.engine.event_bus import EventContext
        if result.auto_fail:
            result.modified_skill = 0
        else:
            result.modified_skill = max(
                0,
                result.base_skill + result.committed_icons + result.token_modifier
            )

        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id=result.investigator_id,
            skill_type=result.skill_type,
            modified_skill=result.modified_skill,
            difficulty=result.difficulty,
            amount=result.modified_skill,
            source=result.source_instance_id,
        )
        self.bus.emit(ctx)
        result.modified_skill = max(0, ctx.amount)

    def _st6_determine_result(self, result: SkillTestResult) -> None:
        from backend.engine.event_bus import EventContext
        if result.auto_fail:
            result.success = False
        elif result.difficulty == 0:
            result.success = True
            result.auto_success = True
        else:
            result.success = result.modified_skill >= result.difficulty

        event = GameEvent.SKILL_TEST_SUCCESSFUL if result.success else GameEvent.SKILL_TEST_FAILED
        ctx = EventContext(
            game_state=self.game_state,
            event=event,
            investigator_id=result.investigator_id,
            skill_type=result.skill_type,
            success=result.success,
            modified_skill=result.modified_skill,
            difficulty=result.difficulty,
            source=result.source_instance_id,
            committed_cards=list(self._committed_card_ids or []),
        )
        self.bus.emit(ctx)

    def _st7_apply(self, result: SkillTestResult, on_success, on_failure) -> None:
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.SKILL_TEST_APPLY_RESULTS,
            investigator_id=result.investigator_id,
            success=result.success,
            source=result.source_instance_id,
        )
        self.bus.emit(ctx)

        if result.success and on_success:
            on_success(result)
        elif not result.success and on_failure:
            on_failure(result)

    def _st8_end(self, result: SkillTestResult, committed_card_ids: list[str]) -> None:
        from backend.engine.event_bus import EventContext
        # Discard committed cards
        inv = self.game_state.get_investigator(result.investigator_id)
        if inv:
            for card_id in committed_card_ids:
                if card_id in inv.hand:
                    inv.hand.remove(card_id)
                    inv.discard.append(card_id)

        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.SKILL_TEST_ENDS,
            investigator_id=result.investigator_id,
            success=result.success,
            source=result.source_instance_id,
        )
        self.bus.emit(ctx)
