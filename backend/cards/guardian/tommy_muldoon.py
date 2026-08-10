"""Tommy Muldoon — Guardian Investigator.
能力：[reaction]在你控制的一张支援卡被击败时：获得X资源，X为该支援卡上的伤害和
恐惧的总和。将该支援卡混洗入你的牌堆。
远古印记：+2。你可以将托米·马尔登上的最多2点伤害和/或恐惧移动到你控制的1张
支援卡上，或将你控制的1张支援卡上的最多2点伤害和/或恐惧移动到托米·马尔登上。

实现说明：
- ASSET_DEFEATED 事件发出时被击败的支援实例仍在场（engine/damage.py 在事件后
  才移除），此时结算 X=伤害+恐惧并获得资源，并记录待混洗；随后的
  CARD_LEAVES_PLAY（引擎移除流程末尾发出，此时卡已入弃牌堆）将卡从弃牌堆
  移入牌堆并混洗。两条路径（DamageEngine 与 _shared.defeat_asset）事件顺序一致。
- 远古印记的伤害/恐惧移动为可选玩家选择：优先读取一次性预设
  scenario.vars["tommy_muldoon_transfer"]（{"instance_id", "damage", "horror",
  "to_asset"}，结算后弹出）；无预设时设置 pending_choice
  （kind="tommy_muldoon_transfer"），由 UI 调用公开方法 resolve_transfer() 结算。
- 移动上限合计2点；从托米移出以其当前伤害/恐惧为限，从支援移出以支援上的
  伤害/恐惧为限；支援无对应 health/sanity 数值的部分不能承受（置0）。
  移动导致支援伤害达到生命上限时不触发击败结算——引擎缺口（DamageEngine
  的击败检查为私有通道）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

MAX_TRANSFER = 2


class TommyMuldoon(CardImplementation):
    card_id = "tommy_muldoon"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._pending_shuffle: dict[str, str] = {}  # instance_id -> card_id

    def _get_tommy(self, game_state, investigator_id):
        """Return the investigator state iff it is Tommy Muldoon."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "tommy_muldoon":
            return None
        return inv

    @on_event(GameEvent.ASSET_DEFEATED, priority=TimingPriority.REACTION)
    def on_asset_defeated(self, ctx):
        """你控制的支援被击败时：获得X资源（X=其上伤害+恐惧），记录待混洗。"""
        inst = ctx.game_state.get_card_instance(ctx.target)
        if inst is None:
            return
        inv = self._get_tommy(ctx.game_state, inst.controller_id or inst.owner_id)
        if inv is None:
            return
        x = (inst.damage or 0) + (inst.horror or 0)
        inv.resources += x
        self._pending_shuffle[inst.instance_id] = inst.card_id
        ctx.game_state.log_effect(
            f"🎖️ 托米·马尔登：【{ctx.game_state.card_name(inst.card_id)}】被击败，"
            f"获得{x}资源并将其混洗入牌堆"
        )

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def shuffle_defeated_asset_into_deck(self, ctx):
        """被击败的支援离场后：从弃牌堆移入托米的牌堆并混洗。"""
        card_id = self._pending_shuffle.pop(ctx.target, None)
        if card_id is None:
            return
        inv = self._get_tommy(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        if card_id in inv.discard:
            inv.discard.remove(card_id)
        inv.deck.append(card_id)
        random.shuffle(inv.deck)

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2。可以在托米与你控制的1张支援之间移动最多2点伤害/恐惧。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_tommy(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "tommy_muldoon_elder_sign")

        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None:
            return

        preset = scenario.vars.pop("tommy_muldoon_transfer", None)
        if preset:
            self.resolve_transfer(
                ctx.game_state, ctx.investigator_id,
                preset.get("instance_id"),
                damage=preset.get("damage", 0),
                horror=preset.get("horror", 0),
                to_asset=preset.get("to_asset", True),
            )
            return

        options = [{"id": "decline", "label": "不触发"}]
        for inst_id in inv.play_area:
            inst = ctx.game_state.get_card_instance(inst_id)
            if inst is None:
                continue
            name = ctx.game_state.card_name(inst.card_id)
            if inv.damage > 0 or inv.horror > 0:
                options.append({"id": f"to:{inst_id}",
                                "label": f"将托米身上的伤害/恐惧移到【{name}】上"})
            if inst.damage > 0 or inst.horror > 0:
                options.append({"id": f"from:{inst_id}",
                                "label": f"将【{name}】上的伤害/恐惧移到托米身上"})
        scenario.vars["pending_choice"] = {
            "kind": "tommy_muldoon_transfer",
            "investigator_id": ctx.investigator_id,
            "prompt": "<b>托米·马尔登</b>：远古印记，是否移动最多2点伤害和/或恐惧？",
            "options": options,
        }

    def resolve_transfer(self, game_state, investigator_id, instance_id,
                         damage: int = 0, horror: int = 0,
                         to_asset: bool = True) -> bool:
        """结算远古印记的伤害/恐惧移动（合计≤2）。由 UI 在玩家选择后调用。"""
        inv = self._get_tommy(game_state, investigator_id)
        if inv is None:
            return False

        scenario = getattr(game_state, "scenario", None)
        if scenario is not None:
            pending = scenario.vars.get("pending_choice", {})
            if pending.get("kind") == "tommy_muldoon_transfer":
                scenario.vars.pop("pending_choice", None)

        inst = game_state.get_card_instance(instance_id)
        if inst is None or instance_id not in inv.play_area:
            return False
        damage = max(0, min(damage, MAX_TRANSFER))
        horror = max(0, min(horror, MAX_TRANSFER - damage))
        if damage + horror <= 0:
            return False

        inst_data = game_state.get_card_data(inst.card_id)
        if to_asset:
            # 支援须具备对应数值才能承受伤害/恐惧
            if inst_data is None or inst_data.health is None:
                damage = 0
            if inst_data is None or inst_data.sanity is None:
                horror = 0
            damage = min(damage, inv.damage)
            horror = min(horror, inv.horror)
            if damage + horror <= 0:
                return False
            inv.damage -= damage
            inv.horror -= horror
            inst.damage += damage
            inst.horror += horror
        else:
            damage = min(damage, inst.damage)
            horror = min(horror, inst.horror)
            if damage + horror <= 0:
                return False
            inst.damage -= damage
            inst.horror -= horror
            inv.damage += damage
            inv.horror += horror

        game_state.log_effect(
            f"🎖️ 托米·马尔登：移动{damage}点伤害和{horror}点恐惧"
            f"（{'到支援' if to_asset else '到托米'}）"
        )
        return True
