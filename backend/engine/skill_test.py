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
    extra: dict = field(default_factory=dict)


class SkillTestEngine:
    def __init__(self, game_state: GameState, event_bus: EventBus, chaos_bag: ChaosBag,
                 card_registry=None) -> None:
        self.game_state = game_state
        self.bus = event_bus
        self.chaos_bag = chaos_bag
        self.card_registry = card_registry
        self._current_test: SkillTestResult | None = None
        self._last_result: SkillTestResult | None = None
        self._committed_temp_ids: list[str] = []
        self._effect_card_ids: list[str] = []
        self._explicit_effect_selection = False

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
        effect_card_ids: list[str] | None = None,
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
        self._committed_card_ids = list(committed_card_ids or [])
        self._explicit_effect_selection = effect_card_ids is not None
        self._effect_card_ids = self._prepare_effect_cards(
            inv,
            self._committed_card_ids,
            effect_card_ids,
        )

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
            self._last_result = result
            self._current_test = None
            self._effect_card_ids = []
            self._explicit_effect_selection = False

        return result

    def _prepare_effect_cards(
        self,
        inv,
        committed_card_ids: list[str],
        requested_effect_card_ids: list[str] | None,
    ) -> list[str]:
        """Validate optional effects and pay their costs.

        ``None`` preserves legacy direct engine calls where every committed
        card implementation is active. The client sends an explicit list,
        including an empty list, so a normal commit cannot trigger an effect
        accidentally.
        """
        if requested_effect_card_ids is None:
            return list(committed_card_ids)

        remaining: dict[str, int] = {}
        for card_id in committed_card_ids:
            remaining[card_id] = remaining.get(card_id, 0) + 1

        selected: list[str] = []
        for card_id in requested_effect_card_ids:
            if remaining.get(card_id, 0) <= 0 or not self.card_registry:
                continue
            impl_cls = self.card_registry.get_implementation(card_id)
            if impl_cls is None:
                continue
            cost = max(0, int(getattr(impl_cls, "commit_effect_cost", 0) or 0))
            if inv.resources < cost:
                continue
            inv.resources -= cost
            selected.append(card_id)
            remaining[card_id] -= 1
        return selected

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
        # Allow handlers (e.g. Flashlight lowering shroud) to modify difficulty.
        if ctx.difficulty is not None and ctx.difficulty != result.difficulty:
            result.difficulty = max(0, ctx.difficulty)

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

        # Temporarily activate committed cards' implementations so their
        # effects (Guts draw, Perception, Opportunist, ...) fire during the test.
        if self.card_registry:
            for card_id in self._effect_card_ids:
                if self.card_registry.get_implementation(card_id):
                    temp_id = self.game_state.next_instance_id()
                    self.card_registry.activate_card(card_id, temp_id, self.bus, chaos_bag=self.chaos_bag)
                    self._committed_temp_ids.append(temp_id)

        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id=result.investigator_id,
            skill_type=result.skill_type,
            difficulty=result.difficulty,
            committed_cards=committed_card_ids,
            amount=total_icons,
        )
        self.bus.emit(ctx)
        # Update in case handlers modified
        result.committed_icons = ctx.amount
        # Allow committed-card effects (e.g. Double or Nothing) to modify the
        # test difficulty during the commit step.
        if ctx.difficulty is not None and ctx.difficulty != result.difficulty:
            result.difficulty = max(0, ctx.difficulty)

    def _st3_reveal(self, result: SkillTestResult) -> None:
        from backend.engine.event_bus import EventContext
        token = self.chaos_bag.draw()
        result.token = token

        ctx = EventContext(
            game_state=self.game_state,
            event=GameEvent.CHAOS_TOKEN_REVEALED,
            investigator_id=result.investigator_id,
            chaos_token=token,
            skill_type=result.skill_type,
            difficulty=result.difficulty,
            source=result.source_instance_id,
            extra={
                # The client uses this snapshot to animate the reveal without
                # changing the authoritative result calculated by the engine.
                "possible_tokens": [
                    getattr(item, "value", str(item))
                    for item in self.chaos_bag.tokens
                ],
                "base_skill": result.base_skill,
                "committed_icons": result.committed_icons,
            },
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
            skill_type=result.skill_type,
            difficulty=result.difficulty,
            source=result.source_instance_id,
        )
        self.bus.emit(ctx)
        result.token_modifier = ctx.amount
        # Scenario token effects (e.g. Hard/Expert reference card) may force
        # the test to auto-fail regardless of the final skill value.
        if ctx.extra.get("force_auto_fail"):
            result.auto_fail = True
        # Symmetric escape hatch: card effects (e.g. Eucatastrophe) may cancel
        # an auto-fail token after it was revealed.
        if result.auto_fail and ctx.extra.get("cancel_auto_fail"):
            result.auto_fail = False

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
            extra={
                "base_skill": result.base_skill,
                "committed_icons": result.committed_icons,
                "token_modifier": result.token_modifier,
            },
        )
        self.bus.emit(ctx)
        result.modified_skill = max(0, ctx.amount)
        # Asset/ally/effect bonuses folded in by the event bus, so the UI can
        # display the full calculation (base + icons + token + bonuses).
        pre_event_value = (
            0
            if result.auto_fail
            else max(0, result.base_skill + result.committed_icons + result.token_modifier)
        )
        result.extra["asset_bonus"] = result.modified_skill - pre_event_value
        result.extra["skill_bonus_sources"] = [
            {"reason": reason, "delta": delta}
            for reason, delta in getattr(ctx, "_modifications", [])
        ]

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
            amount=result.token_modifier,
            committed_cards=list(self._committed_card_ids or []),
            extra={
                "base_skill": result.base_skill,
                "committed_icons": result.committed_icons,
                "token_modifier": result.token_modifier,
                "auto_fail": result.auto_fail,
                "auto_success": result.auto_success,
                "asset_bonus": result.extra.get("asset_bonus", 0),
                "skill_bonus_sources": result.extra.get("skill_bonus_sources", []),
                "enabled_effect_cards": list(self._effect_card_ids),
                "explicit_effect_selection": self._explicit_effect_selection,
            },
        )
        self.bus.emit(ctx)
        result.extra = dict(ctx.extra)
        # Allow handlers (e.g. Rex's Curse) to flip the outcome by mutating
        # ctx.success. Handlers leave it untouched in the normal case.
        if ctx.success is not None and ctx.success != result.success:
            result.success = ctx.success

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

        # Deactivate committed cards' temporary implementations
        if self.card_registry:
            for temp_id in self._committed_temp_ids:
                self.card_registry.deactivate_card(temp_id, self.bus)
            self._committed_temp_ids.clear()
