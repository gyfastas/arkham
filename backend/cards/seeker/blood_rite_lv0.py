"""Blood-Rite (Level 0) — Seeker Event. (05317)
绑定(神秘词典)。抽2张牌。从你的手牌中丢弃至多2张牌。每因此丢弃1张牌，
你可以获得1资源，或花费1资源对你所在地点的一名敌人造成1点伤害。
本行动不引起趁乱攻击。

简化说明：
- 绑定机制：本卡开局随绑定卡场外存放（scenario.vars["set_aside"]），由
  神秘词典洗入牌库（occult_lexicon 不在本批次）；对局内从手牌正常打出；
- "丢弃至多2张"及每张的"资源/伤害"抉择为玩家选择：缺省自动丢弃手牌前2张
  并各获得1资源（保守，不造成伤害）；完整选择可经 CARD_PLAYED 的
  ctx.extra["blood_rite_choices"] 传入：
  [{"card_id": ..., "mode": "resource"|"damage", "enemy": instance_id}]；
- 造成伤害经 _shared.deal_damage_to_enemy（含击败结算）；
- "不引起趁乱攻击"：事件打出在本引擎不走 PLAY 行动的 AoO 检查之外的额外
  路径，天然满足。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards._shared import deal_damage_to_enemy
from backend.models.enums import GameEvent, TimingPriority

MAX_DISCARDS = 2


class BloodRite(CardImplementation):
    card_id = "blood_rite_lv0"

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 抽2张牌
        for _ in range(2):
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))

        choices = ctx.extra.get("blood_rite_choices")
        if choices is None:
            # 自动简化：丢弃手牌前2张，每张获得1资源
            choices = [
                {"card_id": cid, "mode": "resource"}
                for cid in list(inv.hand[:MAX_DISCARDS])
            ]

        gained = 0
        dealt = 0
        for choice in choices[:MAX_DISCARDS]:
            cid = choice.get("card_id")
            if cid not in inv.hand:
                continue
            inv.hand.remove(cid)
            inv.discard.append(cid)
            if choice.get("mode") == "damage":
                enemy_id = choice.get("enemy") or self._first_enemy_at_location(
                    ctx.game_state, inv)
                if enemy_id is not None and inv.resources >= 1:
                    inv.resources -= 1
                    if deal_damage_to_enemy(
                            ctx.game_state, self._bus, enemy_id, 1,
                            defeated_by=inv.investigator_id):
                        pass
                    dealt += 1
                else:
                    inv.resources += 1  # 无法造成伤害：回退为获得1资源
                    gained += 1
            else:
                inv.resources += 1
                gained += 1

        ctx.extra["blood_rite_gained"] = gained
        ctx.extra["blood_rite_dealt"] = dealt
        ctx.game_state.log_effect(
            f"🩸 血祭：抽2张牌，弃牌换得{gained}资源"
            + (f"，造成{dealt}点伤害" if dealt else "")
        )

    @staticmethod
    def _first_enemy_at_location(game_state, inv):
        loc = game_state.get_location(inv.location_id)
        if loc is not None and loc.enemies:
            return loc.enemies[0]
        for other in game_state.get_investigators_at_location(inv.location_id):
            if other.threat_area:
                return other.threat_area[0]
        return None
