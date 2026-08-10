"""Cyclopean Hammer (Level 5) — Guardian Asset, Hand x2. (08093)
[行动]：攻击。本次攻击你将意志加到技能值上，且造成+1伤害。
如果成功且敌人为非精英，你可以将其移动到你的一处相连地点以外的一处地点。
（如果你成功超出3点或更多，改为造成+2伤害，且可以将敌人移动至多两个地点。）

简化说明：
- 意志加值/+伤害为武器被动（经 weapon_instance_id 识别）；成功超出≥3时
  +2伤害替代+1（非叠加）。
- "移动敌人"为可选效果：攻击成功后置位推送池（1或2步），由公开方法
  move_enemy_away() 逐步结算（会话层/UI 调用）；自动选择目的地时可经
  destination 参数指定，否则取敌人当前地点的第一个非你所在地点的相连地点。
  敌人被移出所有威胁区（解除交战）。
- 回合结束时未使用的推送步数作废。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


def _is_elite(card_data) -> bool:
    traits = getattr(card_data, "traits", None) or []
    keywords = getattr(card_data, "keywords", None) or []
    return "elite" in keywords or "精英" in traits


class CyclopeanHammer(CardImplementation):
    card_id = "cyclopean_hammer_lv5"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._target = None          # 本次攻击目标 instance_id
        self._push = None            # {"enemy": iid, "steps": int}

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def record_target(self, ctx):
        if ctx.source == self.instance_id:
            self._target = ctx.enemy_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_willpower(self, ctx):
        """以本锤攻击：将意志加到技能值上。"""
        if ctx.skill_type != Skill.COMBAT or ctx.source != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        willpower = inv.get_skill(Skill.WILLPOWER)
        if willpower:
            ctx.modify_amount(willpower, "cyclopean_hammer_willpower")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage_and_push(self, ctx):
        """成功：+1伤害（超出≥3改为+2）；非精英敌人开放推送窗口。"""
        if ctx.skill_type != Skill.COMBAT or ctx.source != self.instance_id:
            return
        succeed_by = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        big = succeed_by >= 3
        ctx.extra["bonus_damage"] = int(
            ctx.extra.get("bonus_damage", 0) or 0) + (2 if big else 1)

        enemy_iid = self._target
        enemy = ctx.game_state.get_card_instance(enemy_iid) if enemy_iid else None
        enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is not None and enemy_data is not None and not _is_elite(enemy_data):
            self._push = {"enemy": enemy_iid, "steps": 2 if big else 1}
            ctx.extra["cyclopean_hammer_push"] = self._push["steps"]

    # ------------------------------------------------------------------
    # 公开方法：将敌人移离一步（攻击成功后由会话层调用，可调用至 steps 次）
    # ------------------------------------------------------------------
    def move_enemy_away(self, game_state, investigator_id: str,
                        destination: str | None = None) -> bool:
        """将被攻击的非精英敌人向远离你的方向移动一个地点。"""
        if not self._push or self._push.get("steps", 0) <= 0:
            return False
        inv = game_state.get_investigator(investigator_id)
        enemy_iid = self._push["enemy"]
        enemy = game_state.get_card_instance(enemy_iid)
        if inv is None or enemy is None:
            return False

        current_loc_id = self._enemy_location(game_state, enemy_iid, inv)
        current_loc = game_state.get_location(current_loc_id) if current_loc_id else None
        if current_loc is None:
            return False
        dest = destination
        if dest is None:
            dest = next(
                (c for c in current_loc.connections if c != inv.location_id), None)
        if dest is None or dest not in current_loc.connections \
                or dest == inv.location_id:
            return False

        # 解除交战并移动
        for other in game_state.investigators.values():
            if enemy_iid in other.threat_area:
                other.threat_area.remove(enemy_iid)
        if enemy_iid in current_loc.enemies:
            current_loc.enemies.remove(enemy_iid)
        dest_loc = game_state.get_location(dest)
        if dest_loc is None:
            return False
        dest_loc.enemies.append(enemy_iid)
        self._push["steps"] -= 1
        if self._push["steps"] <= 0:
            self._push = None
        game_state.log_effect(
            f"🔨 巨石锤：【{game_state.card_name(enemy.card_id)}】被击退到 {dest}")
        return True

    @staticmethod
    def _enemy_location(game_state, enemy_iid: str, inv) -> str | None:
        """敌人当前地点：交战时取其交战对象所在地点，否则取所在地点列表。"""
        for other in game_state.investigators.values():
            if enemy_iid in other.threat_area:
                return other.location_id
        for loc in game_state.locations.values():
            if enemy_iid in loc.enemies:
                return loc.location_id
        return None

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_target(self, ctx):
        if ctx.source == self.instance_id:
            self._target = None

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def clear_push(self, ctx):
        self._push = None
