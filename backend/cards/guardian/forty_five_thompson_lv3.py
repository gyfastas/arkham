""".45 Thompson (Level 3) — Guardian Asset, Hand x2. (05186)
使用(5弹药)。从.45汤普森花费的弹药作为资源放入你的资源池。
[行动]花费1弹药：攻击。本次攻击你获得+2战斗、造成+1伤害。

实现说明：
- 继承 lv0 的攻击流程；花费弹药时经 _on_ammo_spent 钩子将弹药转为等量资源。
"""

from backend.cards.guardian.forty_five_thompson_lv0 import FortyFiveThompsonLv0


class FortyFiveThompsonLv3(FortyFiveThompsonLv0):
    card_id = "45_thompson_lv3"

    def _on_ammo_spent(self, ctx, amount: int) -> None:
        """花费的弹药作为资源放入持有者的资源池。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inv.resources += amount
        ctx.extra["45_thompson_lv3_resources"] = amount
        ctx.game_state.log_effect(f"🔫 .45汤姆逊冲锋枪(3)：花费的弹药转为{amount}资源")
