"""Ancient Stone (Level 4) — Seeker Asset, Hand slot. (04231)
已研究。使用(X秘密)，X为"你已查明远古之石"后括号中的数字。
[反应]当你抽取任意数量的卡牌时，花费等量秘密：治疗你所在地点一张卡牌上
等量的恐惧。

简化说明：
- X 在入场时从 scenario.vars["identified_stone_difficulty"] 读取（由
  远古之石(1)记录）；未记录时 X=0（"已研究"的战役日志门槛由构筑层校验）；
- 抽牌触发按"每张被抽的牌各触发一次"简化（官方为一批抽牌结算一次反应、
  花费至多等量秘密）：每张 CARD_DRAWN 自动花费1秘密治疗1点恐惧，总效果相同；
- 自动花费（官方为玩家选择是否花费）：仅当你所在地点有可治疗恐惧的卡牌时
  才花费；治疗目标自动选择——优先你本人，其次你所在地点任一调查员装备的
  带有恐惧的支援（官方可自选任一张牌）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

DIFFICULTY_VAR = "identified_stone_difficulty"  # 与 ancient_stone_lv1 共用


class AncientStoneLv4(CardImplementation):
    card_id = "ancient_stone_lv4"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def set_secrets(self, ctx):
        """入场：按冒险日志括号中的数字放置秘密。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        x = ctx.game_state.scenario.vars.get(DIFFICULTY_VAR, 0) or 0
        inst.uses["secrets"] = int(x)

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def heal_on_draw(self, ctx):
        """你每抽1张牌：花费1秘密，治疗你所在地点一张卡牌上的1点恐惧。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("secrets", 0) <= 0:
            return
        target = self._find_heal_target(ctx.game_state, inv)
        if target is None:
            return

        inst.uses["secrets"] -= 1
        if target is inv:
            inv.horror = max(0, inv.horror - 1)
        else:
            target.horror = max(0, target.horror - 1)
        ctx.extra["ancient_stone_lv4_healed"] = True
        ctx.game_state.log_effect("🪨 远古之石(4)：花费1秘密，治疗1点恐惧")

    @staticmethod
    def _find_heal_target(game_state, inv):
        """治疗目标：优先你本人，其次同地点调查员装备区带恐惧的支援。"""
        if inv.horror > 0:
            return inv
        for other in game_state.get_investigators_at_location(inv.location_id):
            for iid in other.play_area:
                ci = game_state.get_card_instance(iid)
                if ci is not None and ci.horror > 0:
                    return ci
        return None
