"""Henry Wan (Level 0) — Rogue Asset, Ally slot. (05155)
[行动]消耗亨利·万：逐枚从混沌袋揭示随机标记，直到你选择停止，或直到揭示
[skull]/[cultist]/[tablet]/[elder_thing]/[auto_fail]符号为止。
- 若你选择停止：每揭示1枚标记，你可以抽1张牌或获得1资源。
- 若你揭示了上述符号：无事发生。

简化说明：
- "选择停止"需玩家逐枚决策：activate(stop_after=N) 预设停止点，默认
  揭示至多3枚安全标记后停止（固定策略简化）。
- 每枚的"抽1牌或获得1资源"由 reward 参数预设（"card" 默认 / "resource"）；
  抽牌时牌堆为空则改为获得1资源。
- 揭示的标记按规则放回袋中：引擎 ChaosBag.draw() 为非破坏性抽取，天然满足。
- 混沌袋经 bind_chaos_bag() 注入；未绑定时 activate 返回 False。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_BAD_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ChaosTokenType.AUTO_FAIL,
}

_DEFAULT_STOP_AFTER = 3


class HenryWan(CardImplementation):
    card_id = "henry_wan_lv0"
    activations = [{
        "id": "reveal",
        "label": "消耗：逐枚揭示混沌标记换取抽牌/资源",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    def activate(self, game_state, investigator_id: str,
                 stop_after: int = _DEFAULT_STOP_AFTER,
                 reward: str = "card") -> bool:
        """消耗：逐枚揭示标记，直到停止（stop_after 枚）或揭示坏符号。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        if self._chaos_bag is None:
            return False
        inst.exhausted = True

        revealed: list[ChaosTokenType] = []
        bad: ChaosTokenType | None = None
        for _ in range(max(1, stop_after)):
            token = self._chaos_bag.draw()
            if token in _BAD_TOKENS:
                bad = token
                break
            revealed.append(token)

        if bad is not None:
            game_state.log_effect(
                f"🎲 亨利·万：揭示了[{bad.value}]，无事发生")
            return True

        drawn = 0
        gained = 0
        for _ in revealed:
            if reward == "resource" or not inv.deck:
                inv.resources += 1
                gained += 1
            else:
                inv.hand.append(inv.deck.pop(0))
                drawn += 1
        game_state.log_effect(
            f"🎲 亨利·万：揭示{len(revealed)}枚标记，"
            f"抽{drawn}张牌、获得{gained}资源")
        return True
