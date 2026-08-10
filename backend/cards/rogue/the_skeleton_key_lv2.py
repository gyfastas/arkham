"""The Skeleton Key (Level 2) — Rogue Asset. (04270)
卓越。快速。
[action]：如果骷髅钥匙在你的游戏区域，将其叠加到你所在地点。如果已经叠加
到你所在地点，改为将其解除叠加并放回你的游戏区域。
将被叠加的地点的隐藏值设为1。

简化说明：
- 叠加/取回经 activations 公开方法实现（会话层 ACTIVATE_CARD 路由，
  1行动，官方卡面为[action]能力；"快速"指打出本卡不花行动，由数据
  fast 标记处理）。
- "隐藏值设为1"不改动地点共享数据，而是在该地点的智力检定（调查）开始时
  将难度设为1（SKILL_TEST_BEGINS 引擎支持改写难度，同 flashlight 通道）；
  其他引用隐藏值的效果不受影响（简化注明）。
- 叠加关系记录在 LocationState.attachments / CardInstance.attached_to
  （与上锁的门等地点叠加卡一致）。
- "卓越"为牌组构建规则，引擎无校验通道（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class TheSkeletonKey(CardImplementation):
    card_id = "the_skeleton_key_lv2"
    activations = [{
        "id": "toggle_attach",
        "label": "叠加到所在地点 / 取回装备区",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str) -> bool:
        """[action] 在"叠加到所在地点"与"取回装备区"之间切换。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False

        if inst.attached_to:
            # 取回：解除叠加，放回游戏区域
            loc = game_state.get_location(inst.attached_to)
            if loc is not None and self.instance_id in loc.attachments:
                loc.attachments.remove(self.instance_id)
            inst.attached_to = None
            if self.instance_id not in inv.play_area:
                inv.play_area.append(self.instance_id)
            game_state.log_effect("🗝️ 骷髅钥匙：解除叠加，放回游戏区域")
            return True

        if self.instance_id not in inv.play_area:
            return False
        loc = game_state.get_location(inv.location_id)
        if loc is None:
            return False
        inv.play_area.remove(self.instance_id)
        inst.attached_to = loc.location_id
        if self.instance_id not in loc.attachments:
            loc.attachments.append(self.instance_id)
        game_state.log_effect(
            f"🗝️ 骷髅钥匙：叠加到【{game_state.card_name(loc.card_data.id)}】，其隐藏值设为1")
        return True

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def set_shroud_to_one(self, ctx):
        """被叠加地点的调查（智力检定）难度设为1。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or not inst.attached_to:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inv.location_id != inst.attached_to:
            return
        ctx.difficulty = 1
        ctx.extra["skeleton_key_shroud_set"] = True
