"""Interrogate (Level 0) — Guardian Event. (05020)
谈判。选择你所在地点的一个[[类人生物]]敌人并检定[战斗](3)。
本次检定难度+X，X为所选敌人的伤害值。如果你成功，在你所在地点发现1条线索，
并在任意其他一个地点发现1条线索。

简化说明：
- 事件卡实现拿不到 SkillTestEngine（引擎仅经 actions/会话层持有），
  打出时的战斗检定由会话层发起：本卡在 CARD_PLAYED 时自动选择目标
  （同地点第一个类人生物敌人，可经 ctx.extra["enemy_instance_id"] 指定），
  把难度记入 scenario.vars["interrogate_test"]，会话层随后跑战斗检定
  （SkillTestEngine.run_test）并调用 on_test_result() 结算成功效果。
- "任意其他地点"自动选择：第一个有线索的其他地点（可经
  on_test_result(other_location_id=...) 指定）。
- 引擎的 Action.PARLEY 未实现（perform_action 无该分支），谈判行动的
  行动消耗/趁乱攻击豁免由会话层负责（注明）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

VAR = "interrogate_test"


class Interrogate(CardImplementation):
    card_id = "interrogate_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def setup_test(self, ctx):
        """打出时：选择类人生物敌人，记录谈判检定参数（会话层跑检定）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        enemy_iid = ctx.extra.get("enemy_instance_id")
        enemy_data = None
        if enemy_iid is not None:
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy_data is None or "humanoid" not in (enemy_data.traits or []):
            # 自动选择：同地点（交战优先）第一个类人生物敌人
            enemy_iid, enemy_data = None, None
            loc = ctx.game_state.get_location(inv.location_id)
            candidates = list(inv.threat_area) + list(loc.enemies if loc else [])
            for iid in candidates:
                enemy = ctx.game_state.get_card_instance(iid)
                data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
                if data is not None and "humanoid" in (data.traits or []):
                    enemy_iid, enemy_data = iid, data
                    break
        if enemy_iid is None:
            ctx.extra["interrogate_fizzle"] = True
            ctx.game_state.log_effect("🗣️ 审讯：同地点没有类人生物敌人，效果不结算")
            return

        difficulty = 3 + (enemy_data.enemy_damage or 0)
        ctx.game_state.scenario.vars[VAR] = {
            "investigator_id": inv.investigator_id,
            "enemy_instance_id": enemy_iid,
            "difficulty": difficulty,
        }
        ctx.extra["interrogate_difficulty"] = difficulty
        ctx.game_state.log_effect(
            f"🗣️ 审讯：对【{ctx.game_state.card_name(enemy_data.id)}】"
            f"进行战斗({difficulty})谈判检定")

    def on_test_result(self, game_state, success: bool,
                       other_location_id: str | None = None) -> bool:
        """(会话层调用) 谈判检定结算后：成功则发现2条线索。"""
        pending = game_state.scenario.vars.pop(VAR, None)
        if pending is None or not success:
            return False
        inv = game_state.get_investigator(pending["investigator_id"])
        if inv is None:
            return False

        # 你所在地点1条
        loc = game_state.get_location(inv.location_id)
        if loc is not None and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1

        # 任意其他地点1条（自动选第一个有线索的，可指定）
        other = None
        if other_location_id is not None:
            candidate = game_state.get_location(other_location_id)
            if candidate is not None and candidate.location_id != inv.location_id \
                    and candidate.clues > 0:
                other = candidate
        if other is None:
            for candidate in game_state.locations.values():
                if candidate.location_id != inv.location_id and candidate.clues > 0:
                    other = candidate
                    break
        if other is not None:
            other.clues -= 1
            inv.clues += 1

        game_state.log_effect("🗣️ 审讯成功：所在地点与另一地点各发现1条线索")
        return True
