"""Ashcan Pete — Survivor Investigator.
能力：开始游戏时，将杜克放置入场。
[fast]丢弃一张手牌：准备1张你控制的支援卡。（每轮限制1次。）
远古印记：+2。准备杜克。

简化说明：
- "游戏开始时杜克入场"：game.setup() 激活本实现后不发出任何事件，因此实现为
  公开方法 setup_duke()（供 UI 在 setup 后直接调用）+ ROUND_BEGINS 懒触发兜底
  （第一轮开始时若杜克未入场则自动入场，不修改已有文件的前提下等效于开局入场）。
- fast 自由能力实现为公开方法 activate_ready_asset()（参考 the_necronomicon 的
  activate 模式），由 UI 在玩家选择发动时调用；准备时不额外发出 CARD_READIED 事件。
- 杜克不占用盟友槽位的规则未与 SlotManager 联动（槽位管理在引擎激活流程之外）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority
from backend.models.state import CardInstance

DUKE_CARD_ID = "duke_lv0"


class AshcanPete(CardImplementation):
    card_id = "ashcan_pete"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_round = False

    def _get_pete(self, game_state, investigator_id):
        """Return the investigator state iff it is Ashcan Pete."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "ashcan_pete":
            return None
        return inv

    def _find_duke(self, game_state, inv) -> CardInstance | None:
        for inst_id in inv.play_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == DUKE_CARD_ID:
                return inst
        return None

    def _place_duke(self, game_state, investigator_id) -> str | None:
        """将杜克放入 Pete 的场上（幂等），返回 instance_id。"""
        inv = self._get_pete(game_state, investigator_id)
        if inv is None:
            return None
        existing = self._find_duke(game_state, inv)
        if existing is not None:
            return existing.instance_id

        inst_id = game_state.next_instance_id()
        duke = CardInstance(
            instance_id=inst_id,
            card_id=DUKE_CARD_ID,
            owner_id=investigator_id,
            controller_id=investigator_id,
        )
        game_state.cards_in_play[inst_id] = duke
        inv.play_area.append(inst_id)
        return inst_id

    def setup_duke(self, game_state, investigator_id) -> str | None:
        """游戏开始时将杜克放置入场。由 UI 在 setup 后调用（幂等）。"""
        return self._place_duke(game_state, investigator_id)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def on_round_begins(self, ctx):
        """每轮开始时重置限次；第一轮开始时兜底让杜克入场。"""
        self._used_this_round = False
        for inv_id, inv in ctx.game_state.investigators.items():
            card_data = getattr(inv, "card_data", None)
            if card_data is not None and card_data.id == "ashcan_pete":
                self._place_duke(ctx.game_state, inv_id)

    def activate_ready_asset(self, game_state, investigator_id,
                             hand_card_id, asset_instance_id) -> bool:
        """[fast]丢弃一张手牌：准备1张你控制的支援卡（每轮限1次）。由 UI 调用。"""
        inv = self._get_pete(game_state, investigator_id)
        if inv is None:
            return False
        if self._used_this_round:
            return False
        if hand_card_id not in inv.hand:
            return False
        if asset_instance_id not in inv.play_area:
            return False

        asset = game_state.get_card_instance(asset_instance_id)
        if asset is None or not asset.exhausted:
            return False
        # 若卡牌数据库中有数据，确认是支援卡
        asset_data = game_state.get_card_data(asset.card_id)
        if asset_data is not None:
            from backend.models.enums import CardType
            if asset_data.type != CardType.ASSET:
                return False

        inv.hand.remove(hand_card_id)
        inv.discard.append(hand_card_id)
        asset.exhausted = False
        self._used_this_round = True
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2。准备杜克。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_pete(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "ashcan_pete_elder_sign")
        duke = self._find_duke(ctx.game_state, inv)
        if duke is not None:
            duke.exhausted = False
