"""Shrine of the Moirai (Level 3) — Survivor Event. (07310)
叠加到你所在地点。使用(3贡品)。
叠加地点获得："[fast] 抽取遭遇牌堆顶部的卡牌，消耗命运三女神的祭坛，并花费
1贡品：从你的弃牌堆将最多2张等级总计5以下的卡牌返回你的手牌。位于该地点的
所有调查员均可触发此能力。"

简化说明：
- 打出时创建叠加实例（attached_to=所在地点，记入 loc.attachments 与
  scenario.vars["shrine_of_the_moirai"]）；贡品数记在实例 uses["offerings"]
  （源数据键为笔误 "offeringss"，本实现统一用规范键）。
- 地点能力实现为公开方法 activate()（activations 声明；会话层 ACTIVATE_CARD
  目前只认 play_area/threat_area 内的实例，叠加卡走不到该路由——引擎/会话
  缺口，见报告；测试与后续接线可直接调用公开方法）。
- "抽取遭遇牌堆顶部的卡牌"是费用：简化为其显现被取消（直接移入遭遇弃牌堆）。
- 返回卡牌自动选择：按等级从高到低贪心选取至多2张、等级合计≤5 的卡牌
  （官方为玩家自选）。
- 事件实现实例在 ROUND_ENDS 被引擎清理；activate() 经 scenario.vars 找回
  叠加实例，不依赖事件注册，跨轮可用（同 hiding_spot 的口径）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance

_VAR = "shrine_of_the_moirai"
_USES_KEY = "offerings"


class ShrineOfTheMoirai(CardImplementation):
    card_id = "shrine_of_the_moirai_lv3"
    activations = [{
        "id": "offer",
        "label": "抽遭遇牌顶+消耗+1贡品：从弃牌堆回收至多2张（等级合计≤5）",
        "method": "activate",
    }]

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_location(self, ctx):
        """打出时：叠加到你所在地点（3贡品）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None:
            return
        inst_id = ctx.game_state.next_instance_id()
        inst = CardInstance(
            instance_id=inst_id,
            card_id=self.card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            attached_to=loc.location_id,
            uses={_USES_KEY: 3},
        )
        ctx.game_state.cards_in_play[inst_id] = inst
        loc.attachments.append(inst_id)
        ctx.game_state.scenario.vars[_VAR] = inst_id
        ctx.extra["shrine_attached"] = inst_id
        ctx.game_state.log_effect("⛩ 命运三女神的祭坛：叠加到所在地点（3贡品）")

    @staticmethod
    def _attached_instance(game_state):
        inst_id = game_state.scenario.vars.get(_VAR)
        if inst_id:
            return game_state.get_card_instance(inst_id)
        return None

    def activate(self, game_state, investigator_id: str) -> bool:
        """[fast] 抽遭遇牌顶 + 消耗 + 1贡品：弃牌堆回收至多2张（合计≤5级）。

        位于叠加地点的调查员均可触发。
        """
        inv = game_state.get_investigator(investigator_id)
        inst = self._attached_instance(game_state)
        if inv is None or inst is None or inst.exhausted:
            return False
        if inv.location_id != inst.attached_to:
            return False
        if inst.uses.get(_USES_KEY, 0) < 1:
            return False

        # 费用：抽遭遇牌堆顶（简化：显现取消，直接入遭遇弃牌堆）
        drawn = None
        if game_state.scenario.encounter_deck:
            drawn = game_state.scenario.encounter_deck.pop(0)
            game_state.scenario.encounter_discard.append(drawn)
        inst.exhausted = True
        inst.uses[_USES_KEY] -= 1

        # 自动选择：等级从高到低贪心，至多2张、合计≤5级
        picked: list[str] = []
        total = 0

        def _level(cid: str) -> int:
            cd = game_state.get_card_data(cid)
            return (cd.level or 0) if cd is not None else 0

        for cid in sorted(inv.discard, key=_level, reverse=True):
            if len(picked) >= 2:
                break
            lv = _level(cid)
            if total + lv <= 5:
                picked.append(cid)
                total += lv
        for cid in picked:
            inv.discard.remove(cid)
            inv.hand.append(cid)

        names = "、".join(game_state.card_name(c) for c in picked)
        game_state.log_effect(f"⛩ 命运三女神的祭坛：回收【{names}】")
        return True
