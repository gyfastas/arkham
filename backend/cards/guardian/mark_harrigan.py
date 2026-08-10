"""Mark Harrigan — Guardian Investigator.
能力：你开始游戏时把索菲(深切的思念)放置到场上。
[reaction]有伤害放置到你控制的卡牌上后：抽取1张卡牌。(每个阶段限制一次。)
远古印记：马克·哈里根身上每有1点伤害，+1。

简化说明：
- "开始游戏时索菲入场"：game.setup() 激活本实现后不发出任何事件，因此实现为
  公开方法 setup_sophie()（供 UI 在 setup 后直接调用）+ ROUND_BEGINS 懒触发兜底
  （第一轮开始时若索菲未入场则自动入场），与 ashcan_pete 的杜克同一惯例。
  索菲实例的 CardImplementation 注册需要 registry 引用（卡实现拿不到），
  引擎缺口：以本途径入场的索菲其 on_event 能力（翻面检查等）不生效，
  索菲的 spend() 仍可经会话层拿到 impl 后调用（同杜克）。
- "伤害放置到你控制的卡牌上"：DamageEngine 在 DAMAGE_ASSIGNED 事件发出前已完成
  盟友吸收结算，事件对马克本人与盟友吸收两种情况都会发出（amount 为原始伤害量），
  本实现按 amount≥1 触发。直接伤害（direct=True / 索菲 spend 等不经事件总线的
  直接加减）不发出事件，无法触发——引擎缺口，无更精确钩子。
- 抽牌直接移动牌库顶到手牌，不发出 CARD_DRAWN（避免递归触发抽牌显现类效果）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority
from backend.models.state import CardInstance

SOPHIE_CARD_ID = "sophie_lv0"


class MarkHarrigan(CardImplementation):
    card_id = "mark_harrigan"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_phase = False

    def _get_mark(self, game_state, investigator_id):
        """Return the investigator state iff it is Mark Harrigan."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "mark_harrigan":
            return None
        return inv

    def _place_sophie(self, game_state, investigator_id) -> str | None:
        """将索菲放入马克的场上（幂等），返回 instance_id。"""
        inv = self._get_mark(game_state, investigator_id)
        if inv is None:
            return None
        for inst_id in inv.play_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == SOPHIE_CARD_ID:
                return inst.instance_id

        inst_id = game_state.next_instance_id()
        sophie = CardInstance(
            instance_id=inst_id,
            card_id=SOPHIE_CARD_ID,
            owner_id=investigator_id,
            controller_id=investigator_id,
        )
        game_state.cards_in_play[inst_id] = sophie
        inv.play_area.append(inst_id)
        return inst_id

    def setup_sophie(self, game_state, investigator_id) -> str | None:
        """游戏开始时将索菲放置入场。由 UI 在 setup 后调用（幂等）。"""
        return self._place_sophie(game_state, investigator_id)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def on_round_begins(self, ctx):
        """第一轮开始时兜底让索菲入场。"""
        for inv_id, inv in ctx.game_state.investigators.items():
            card_data = getattr(inv, "card_data", None)
            if card_data is not None and card_data.id == "mark_harrigan":
                self._place_sophie(ctx.game_state, inv_id)

    @on_event(GameEvent.MYTHOS_PHASE_BEGINS, priority=TimingPriority.WHEN)
    @on_event(GameEvent.INVESTIGATION_PHASE_BEGINS, priority=TimingPriority.WHEN)
    @on_event(GameEvent.ENEMY_PHASE_BEGINS, priority=TimingPriority.WHEN)
    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.WHEN)
    def reset_phase_limit(self, ctx):
        """每个阶段开始时重置限次。"""
        self._used_this_phase = False

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.AFTER)
    def draw_on_damage(self, ctx):
        """有伤害放置到你控制的卡牌上后：抽1张牌（每阶段限1次）。"""
        if self._used_this_phase or (ctx.amount or 0) < 1:
            return
        inv = self._get_mark(ctx.game_state, ctx.investigator_id)
        if inv is None or not inv.deck:
            return
        self._used_this_phase = True
        card_id = inv.deck.pop(0)
        inv.hand.append(card_id)
        ctx.game_state.log_effect(
            f"🎖️ 马克·哈里根：伤害放置到你控制的卡牌上，抽到"
            f"【{ctx.game_state.card_name(card_id)}】"
        )

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：马克·哈里根身上每有1点伤害，+1。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_mark(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        if inv.damage > 0:
            ctx.modify_amount(inv.damage, "mark_harrigan_elder_sign")
