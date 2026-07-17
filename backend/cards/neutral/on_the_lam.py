"""亡命天涯（On the Lam）— "倒霉蛋"奥图尔专属事件卡。快速。
在你回合开始后打出。直到本轮结束，非精英敌人不能攻击你。

简化说明：
- "在回合开始后打出"为打出时机条件，由会话层/UI 校验，此处不强制。
- 引擎的敌人阶段攻击流程不检查事件取消（phase_enemy 忽略 cancelled），
  因此在敌人阶段开始时，将与生效调查员交战的未横置非精英敌人横置，
  使其跳过攻击（ upkeep 阶段照常重整）；对阶段中通过猎手等新交战的
  非精英敌人，也在 ENEMY_ENGAGED 时横置。精英敌人不受影响。
  副作用：被横置的敌人本轮不会因猎手移动，且多人局中也不会攻击其他
  调查员，特此注明。
- 借机攻击（ATTACK_OF_OPPORTUNITY）走标准取消路径，可正常被取消。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

EFFECT_KEY = "on_the_lam"


def _get_effects(inv) -> dict:
    effects = getattr(inv, "active_effects", None)
    if effects is None:
        effects = {}
        inv.active_effects = effects
    return effects


class OnTheLam(CardImplementation):
    card_id = "on_the_lam"

    # ------------------------------------------------------------------
    # 打出与过期
    # ------------------------------------------------------------------

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def activate_effect(self, ctx):
        """When played, non-Elite enemies cannot attack you until end of round."""
        if ctx.extra.get("card_id") != "on_the_lam":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        _get_effects(inv)[EFFECT_KEY] = True

    @on_event(
        GameEvent.ROUND_ENDS,
        priority=TimingPriority.AFTER,
    )
    def expire_effect(self, ctx):
        """At end of round, remove the effect from all investigators."""
        for inv in ctx.game_state.investigators.values():
            effects = getattr(inv, "active_effects", None)
            if effects:
                effects.pop(EFFECT_KEY, None)

    # ------------------------------------------------------------------
    # 阻止非精英敌人攻击
    # ------------------------------------------------------------------

    def _is_protected(self, ctx, investigator_id: str) -> bool:
        inv = ctx.game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        return bool(getattr(inv, "active_effects", {}).get(EFFECT_KEY))

    def _is_non_elite(self, ctx, enemy_instance_id: str) -> bool:
        enemy = ctx.game_state.get_card_instance(enemy_instance_id)
        if enemy is None:
            return False
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return False
        return "elite" not in (enemy_data.keywords or [])

    def _exhaust_engaged_non_elite(self, ctx, investigator_id: str) -> None:
        inv = ctx.game_state.get_investigator(investigator_id)
        if inv is None:
            return
        for enemy_iid in list(inv.threat_area):
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is None or enemy.exhausted:
                continue
            if self._is_non_elite(ctx, enemy_iid):
                enemy.exhausted = True

    @on_event(
        GameEvent.ENEMY_PHASE_BEGINS,
        priority=TimingPriority.WHEN,
    )
    def prevent_attacks_in_enemy_phase(self, ctx):
        """Exhaust ready non-Elite enemies engaged with protected investigators
        so the enemy phase attack loop skips them."""
        for inv_id in ctx.game_state.player_order:
            if self._is_protected(ctx, inv_id):
                self._exhaust_engaged_non_elite(ctx, inv_id)

    @on_event(
        GameEvent.ENEMY_ENGAGED,
        priority=TimingPriority.WHEN,
    )
    def prevent_newly_engaged(self, ctx):
        """Non-Elite enemies that engage a protected investigator mid-round
        are exhausted so they cannot attack this round."""
        if not self._is_protected(ctx, ctx.investigator_id):
            return
        if ctx.enemy_id and self._is_non_elite(ctx, ctx.enemy_id):
            enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
            if enemy is not None:
                enemy.exhausted = True

    @on_event(
        GameEvent.ATTACK_OF_OPPORTUNITY,
        priority=TimingPriority.WHEN,
    )
    def cancel_attack_of_opportunity(self, ctx):
        """Non-Elite enemies cannot make attacks of opportunity against you."""
        if not self._is_protected(ctx, ctx.investigator_id):
            return
        if ctx.enemy_id and self._is_non_elite(ctx, ctx.enemy_id):
            ctx.cancel()

    @on_event(
        GameEvent.ENEMY_ATTACKS,
        priority=TimingPriority.WHEN,
    )
    def cancel_enemy_attack(self, ctx):
        """Cancel attack events from non-Elite enemies (defense-in-depth;
        the enemy phase itself is handled by exhaustion above)."""
        if not self._is_protected(ctx, ctx.investigator_id):
            return
        if ctx.enemy_id and self._is_non_elite(ctx, ctx.enemy_id):
            ctx.cancel()
