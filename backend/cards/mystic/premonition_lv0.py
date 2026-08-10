"""Premonition (Level 0) — Mystic Event. (Augury)
快速。在任意[fast]玩家窗口打出。
将预感放置入场，从混乱袋随机揭示1个标记并封印在预感上。
强制 - 当将从混乱袋揭示1个标记时：改为结算此处封印的标记（视为刚从袋中
揭示）。然后弃掉预感。

简化说明：
- 打出时创建无槽位入场实例并封印1个随机标记（bind_chaos_bag 注入游戏袋）。
- 替换结算挂 CHAOS_TOKEN_RESOLVED（同 grotesque_statue 通道：引擎在 _st3 已抽
  袋，无法阻止抽袋，以改写标记+修正等效结算）；场景相关的符号标记按0估值。
- 弃掉预感时封印标记释放回袋中。
- 事件临时实现注册至 ROUND_ENDS（引擎 _play_event 惯例）：跨轮未触发的预感
  在下一轮失去注册——引擎缺口（事件入场无持久注册通道）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.chaos import STANDARD_BAG
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)
from backend.models.state import CardInstance


class Premonition(CardImplementation):
    card_id = "premonition_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._rng = random.Random()
        self._sealed_token = None
        self._play_instance_id = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def enter_play_and_seal(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 放置入场（无槽位）
        inst = CardInstance(
            instance_id=ctx.game_state.next_instance_id(),
            card_id=self.card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
        )
        ctx.game_state.cards_in_play[inst.instance_id] = inst
        inv.play_area.append(inst.instance_id)
        self._play_instance_id = inst.instance_id

        # 随机揭示1个标记并封印
        if self._chaos_bag is not None:
            token = self._chaos_bag.draw()
            self._chaos_bag.seal_token(token)
        else:
            token = self._rng.choice(list(STANDARD_BAG))
        self._sealed_token = token
        ctx.extra["premonition_sealed"] = token.value

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def resolve_sealed_instead(self, ctx):
        """强制：改为结算封印标记，然后弃掉预感。"""
        if self._sealed_token is None or self._play_instance_id is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self._play_instance_id not in inv.play_area:
            return

        token = self._sealed_token
        new_value = CHAOS_TOKEN_VALUES.get(token) or 0
        ctx.chaos_token = token
        ctx.modify_amount(new_value - ctx.amount, "premonition_sealed")
        if token == ChaosTokenType.AUTO_FAIL:
            ctx.extra["force_auto_fail"] = True
        else:
            ctx.extra["cancel_auto_fail"] = True
        ctx.extra["premonition_resolved"] = token.value

        # 弃掉预感：封印标记释放回袋
        if self._chaos_bag is not None:
            self._chaos_bag.release_token(token)
        inv.play_area.remove(self._play_instance_id)
        ctx.game_state.cards_in_play.pop(self._play_instance_id, None)
        inv.discard.append(self.card_id)
        self._sealed_token = None
        self._play_instance_id = None
