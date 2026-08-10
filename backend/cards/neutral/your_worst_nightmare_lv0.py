"""Your Worst Nightmare (Level 0) — Neutral Enemy, Basic Weakness.
多人游戏专用。猎手。
猎物 - 仅对承受者。
最可怕的噩梦的承受者不能对其攻击、造成伤害或将其击败。

官方数值（arkhamdb 06038，玩家卡 JSON 通道不含 enemy_* 字段，需会话/数据
层接线；测试以 make_enemy_data 注入）：战斗2 / 生命3 / 躲避2 / 伤害0 / 恐惧2。

简化说明：
- 抽到（CARD_DRAWN）时生成并与承受者交战（猎物-仅承受者；官方生成位置
  由剧本/生成通道决定，弱点惯例按承受者处理）。
- "承受者不能攻击它"：承受者以它为目标发起战斗时取消该行动
  （FIGHT_ACTION_INITIATED 可取消，引擎不扣行动，视为选择非法目标）。
- "承受者不能对其造成伤害"：DAMAGE_DEALT 来源为承受者时伤害归零
  （覆盖炸药爆破等非攻击伤害通道）。
- "不能将其击败"由伤害归零覆盖主要通道；直接击败类效果（如放逐）无通用
  拦截钩子，引擎缺口。承受者以 owner_id 记录。
- 猎手关键词依赖敌人 AI 通道，引擎缺口。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance


class YourWorstNightmare(CardImplementation):
    card_id = "your_worst_nightmare_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def spawn_on_draw(self, ctx):
        """抽到：生成并与承受者交战。"""
        if ctx.extra.get("card_id") != "your_worst_nightmare_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "your_worst_nightmare_lv0" in inv.hand:
            inv.hand.remove("your_worst_nightmare_lv0")

        inst_id = ctx.game_state.next_instance_id()
        enemy = CardInstance(
            instance_id=inst_id,
            card_id="your_worst_nightmare_lv0",
            owner_id=inv.investigator_id,  # 承受者
            controller_id="scenario",
        )
        ctx.game_state.cards_in_play[inst_id] = enemy
        inv.threat_area.append(inst_id)
        ctx.game_state.log_effect("😱 最可怕的噩梦：生成并与承受者交战")
        ctx.extra["your_worst_nightmare_spawned"] = inst_id

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def bearer_cannot_attack(self, ctx):
        """承受者不能攻击它：取消该战斗行动（不扣行动）。"""
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        if enemy is None or enemy.card_id != "your_worst_nightmare_lv0":
            return
        if enemy.owner_id != ctx.investigator_id:
            return
        ctx.cancel()
        ctx.game_state.log_effect("😱 最可怕的噩梦：承受者不能攻击它")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bearer_cannot_damage(self, ctx):
        """承受者不能对其造成伤害：来源为承受者时伤害归零。"""
        enemy = ctx.game_state.get_card_instance(ctx.target)
        if enemy is None or enemy.card_id != "your_worst_nightmare_lv0":
            return
        if ctx.investigator_id is None or enemy.owner_id != ctx.investigator_id:
            return
        if ctx.amount > 0:
            ctx.modify_amount(-ctx.amount, "your_worst_nightmare_immune")
            ctx.game_state.log_effect("😱 最可怕的噩梦：承受者不能对其造成伤害")
