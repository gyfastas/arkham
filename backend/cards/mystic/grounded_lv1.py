"""Grounded (Level 1) — Mystic Asset. (03113)
快速。场上限制1张[[沉稳]]。
非直接恐惧必须先分配给情绪稳定，然后才能分配给你的调查员卡。
[fast] 进行[[法术]]卡上的技能检定时，花费1资源：本次检定你+1技能值。

简化说明：
- 恐惧吸收：HORROR_ASSIGNED 时自动先把恐惧放到情绪稳定上（至多其剩余神智）。
  引擎的 HORROR_ASSIGNED 上下文不带 direct 标记——指定目标的直接恐惧在引擎中
  不经过该事件，故实际到达此处的均按非直接处理（引擎缺口见汇报）。
- 吸收导致情绪稳定被击败时，手动移除出场（复刻 DamageEngine 的资产击败流程，
  卡牌代码拿不到事件总线，ASSET_DEFEATED/CARD_LEAVES_PLAY 不补发）。
- 法术检定泵：spend() 武装（可叠加，同 ResourceSkillBoost 惯例）；
  通过检定来源卡（ctx.source）的 spell 特性判定"法术卡上的检定"。
  无来源的法术事件检定（如事件版攻击）识别不到——引擎缺口：检定上下文
  缺少发起卡 id。
- "场上限制1张沉稳"：入场时若已控制另一张沉稳卡，自动弃置新入场的本卡
  （官方为打出时禁止；打出前拦截需会话层支持）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, TimingPriority


class Grounded(CardImplementation):
    card_id = "grounded_lv1"
    activations = [{
        "id": "spell_pump",
        "label": "【快速】法术检定中花1资源：本次检定+1技能值",
        "method": "spend",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = 0

    # ---- 快速泵：法术检定花1资源 +1技能值（可叠加） ----
    def spend(self, game_state, investigator_id: str) -> bool:
        """【快速】花费1资源：本次法术卡技能检定+1技能值（可叠加）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or inv.resources < 1:
            return False
        if self.instance_id not in inv.play_area:
            return False
        inv.resources -= 1
        self._armed += 1
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if not self._is_spell_test(ctx):
            return
        ctx.modify_amount(self._armed, "grounded_spell_boost")
        self._armed = 0

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        # 未消耗的武装状态在检定结束后清除（资源已花不退）
        self._armed = 0

    def _is_spell_test(self, ctx) -> bool:
        """检定来源卡带 spell 特性（如 Shrivelling 发起的攻击）。"""
        if ctx.source is None:
            return False
        ci = ctx.game_state.get_card_instance(ctx.source)
        if ci is None:
            return False
        cd = ctx.game_state.get_card_data(ci.card_id)
        return cd is not None and "spell" in (cd.traits or [])

    # ---- 非直接恐惧必须先分配给本卡 ----
    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_horror(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or ctx.amount <= 0:
            return
        cd = ctx.game_state.get_card_data(inst.card_id)
        sanity = (cd.sanity if cd else None) or 1  # 数据未填时按印刷值1
        remaining = max(0, sanity - inst.horror)
        soak = min(remaining, ctx.amount)
        if soak <= 0:
            return
        inst.horror += soak
        ctx.modify_amount(-soak, "grounded_soak")
        ctx.extra["grounded_soaked"] = soak
        if inst.horror >= sanity:
            self._defeat_self(ctx.game_state, inv)

    def _defeat_self(self, game_state, inv) -> None:
        """吸收满神智后被击败：移出场地入弃牌堆。"""
        vacate_asset_slots(game_state, self.instance_id)
        inst = game_state.get_card_instance(self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        if inst is not None:
            inv.discard.append(inst.card_id)
        game_state.cards_in_play.pop(self.instance_id, None)

    # ---- 场上限制1张沉稳 ----
    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def composure_limit(self, ctx):
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        for iid in inv.play_area:
            if iid == self.instance_id:
                continue
            ci = ctx.game_state.get_card_instance(iid)
            if ci is None:
                continue
            cd = ctx.game_state.get_card_data(ci.card_id)
            if cd is not None and "composure" in (cd.traits or []):
                # 已控制另一张沉稳：弃置新入场的本卡
                self._defeat_self(ctx.game_state, inv)
                ctx.extra["grounded_discarded_limit"] = True
                ctx.game_state.log_effect("🧘 情绪稳定：场上限制1张沉稳，弃置新入场者")
                return
