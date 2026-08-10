"""Bounty Contracts (Level 0) — Neutral Asset, Permanent (Tony Morgan deck only).
使用（6赏金）。
[reaction] 当一个敌人入场后：从悬赏合约上移动1-3个赏金到该敌人上，
至多不超过该敌人的生命值。
强制 - 在你击败1个身上有1个或以上赏金的敌人后：将其上的赏金移动到你的
资源池，作为资源。

简化说明：
- 数据 JSON 的 uses 键为 "bountiess"（数据源笔误），读取时兼容两种键名。
- 敌人入场事件引擎未提供（引擎缺口）：place_bounties() 公开方法由会话层
  在敌人入场时调用；数量自动取 min(3, 敌人剩余生命, 可用赏金)。
- 赏金存放在敌人实例 uses["bounties"]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

MAX_BOUNTIES_PER_ENEMY = 3


def _bounty_count(inst) -> int:
    return inst.uses.get("bounties", inst.uses.get("bountiess", 0))


class BountyContracts(CardImplementation):
    card_id = "bounty_contracts_lv0"

    def place_bounties(self, game_state, enemy_instance_id: str,
                       count: int | None = None) -> int:
        """敌人入场后（会话层调用）：移动1-3个赏金到该敌人上。

        返回实际放置的赏金数。count 为 None 时自动取最大值。
        """
        contracts = game_state.get_card_instance(self.instance_id)
        enemy = game_state.get_card_instance(enemy_instance_id)
        if contracts is None or enemy is None:
            return 0
        enemy_data = game_state.get_card_data(enemy.card_id)
        health = (enemy_data.enemy_health or 0) if enemy_data else 0
        remaining_health = max(0, health - enemy.damage)
        available = _bounty_count(contracts)
        cap = min(MAX_BOUNTIES_PER_ENEMY, remaining_health, available)
        if count is None:
            count = cap
        count = max(0, min(count, cap))
        if count <= 0:
            return 0
        contracts.uses["bounties"] = available - count
        contracts.uses.pop("bountiess", None)
        enemy.uses["bounties"] = enemy.uses.get("bounties", 0) + count
        game_state.log_effect(f"📜 悬赏合约：{count}个赏金放到敌人上")
        return count

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def collect_bounties(self, ctx):
        """你击败有赏金的敌人后：赏金转为你的资源。"""
        enemy = ctx.game_state.get_card_instance(ctx.target)
        # 引擎在事件后才移除敌人，此处实例仍在场
        if enemy is None:
            return
        bounties = enemy.uses.get("bounties", 0)
        if bounties <= 0:
            return
        contracts = ctx.game_state.get_card_instance(self.instance_id)
        if contracts is None:
            return
        # 卡面限定"你击败"：仅合约持有者触发
        if ctx.investigator_id != contracts.owner_id:
            return
        inv = ctx.game_state.get_investigator(contracts.owner_id)
        if inv is None:
            return
        inv.resources += bounties
        enemy.uses["bounties"] = 0
        ctx.extra["bounty_contracts_collected"] = bounties
        ctx.game_state.log_effect(
            f"📜 悬赏合约：收取{bounties}个赏金作为资源")
