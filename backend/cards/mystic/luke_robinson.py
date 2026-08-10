"""Luke Robinson — Mystic Investigator.
能力：你以门之匣在场开始游戏。
你每回合可以视为你位于一个连接地点并与该地点的每名敌人交战下，打出一张事件卡。
远古印记：+1。在门之匣上放置1充能。

简化说明：
- "开始游戏时门之匣入场"：game.setup() 激活本实现后不发出任何事件，因此实现为
  公开方法 setup_gate_box()（供 UI 在 setup 后直接调用）+ ROUND_BEGINS 懒触发
  兜底（第一轮开始时若门之匣未入场则自动入场），与 mark_harrigan 的索菲、
  ashcan_pete 的杜克同一惯例。入场时从卡牌数据复制 uses（数据 JSON 键名有
  "chargess" 笔误，兼容保留）。
  引擎缺口：以本途径入场的门之匣其 CardImplementation 未注册到事件总线
  （卡实现拿不到 registry），其 [fast] 能力需会话层拿到 impl 后调用（同杜克）。
- "视为位于连接地点打出事件"未实现——引擎缺口：打出事件的流程
  （engine/actions.py 的 _play/_play_event）无虚拟地点/虚拟交战钩子，
  不修改引擎或其他卡文件的前提下无法生效。
- 远古印记：自动在门之匣上放置1充能（uses 键名兼容 "charges"/"chargess"）；
  门之匣不在场时跳过并记录日志。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority
from backend.models.state import CardInstance

GATE_BOX_CARD_ID = "gate_box_lv0"


class LukeRobinson(CardImplementation):
    card_id = "luke_robinson"

    def _get_luke(self, game_state, investigator_id):
        """Return the investigator state iff it is Luke Robinson."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "luke_robinson":
            return None
        return inv

    def _find_gate_box(self, game_state, inv):
        for inst_id in inv.play_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == GATE_BOX_CARD_ID:
                return inst
        return None

    def _place_gate_box(self, game_state, investigator_id) -> str | None:
        """将门之匣放入卢克的场上（幂等），返回 instance_id。"""
        inv = self._get_luke(game_state, investigator_id)
        if inv is None:
            return None
        existing = self._find_gate_box(game_state, inv)
        if existing is not None:
            return existing.instance_id

        inst_id = game_state.next_instance_id()
        gate_box = CardInstance(
            instance_id=inst_id,
            card_id=GATE_BOX_CARD_ID,
            owner_id=investigator_id,
            controller_id=investigator_id,
        )
        card_data = game_state.get_card_data(GATE_BOX_CARD_ID)
        if card_data is not None and card_data.uses:
            gate_box.uses = dict(card_data.uses)
        game_state.cards_in_play[inst_id] = gate_box
        inv.play_area.append(inst_id)
        return inst_id

    def setup_gate_box(self, game_state, investigator_id) -> str | None:
        """游戏开始时将门之匣放置入场。由 UI 在 setup 后调用（幂等）。"""
        return self._place_gate_box(game_state, investigator_id)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def on_round_begins(self, ctx):
        """第一轮开始时兜底让门之匣入场。"""
        for inv_id, inv in ctx.game_state.investigators.items():
            card_data = getattr(inv, "card_data", None)
            if card_data is not None and card_data.id == "luke_robinson":
                self._place_gate_box(ctx.game_state, inv_id)

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1。在门之匣上放置1充能。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_luke(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(1, "luke_robinson_elder_sign")

        gate_box = self._find_gate_box(ctx.game_state, inv)
        if gate_box is None:
            ctx.game_state.log_effect("🚪 卢克·罗宾逊：门之匣不在场，无法放置充能")
            return
        key = next(
            (k for k in ("charges", "chargess") if k in gate_box.uses),
            "charges",
        )
        gate_box.uses[key] = gate_box.uses.get(key, 0) + 1
        ctx.game_state.log_effect("🚪 卢克·罗宾逊：远古印记，在门之匣上放置1充能")
