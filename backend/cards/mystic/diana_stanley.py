"""Diana Stanley — Mystic Investigator.
能力：黛安娜·史丹利底下每有1张卡牌，获得+1[willpower]。
[reaction]在你拥有的一张卡牌取消或忽略一个卡牌效果或游戏效果后，如果黛安娜·
史丹利底下的卡牌张数少于5：将该卡牌正面朝下放在她底下。抽取1张卡牌并获得
1资源。(每阶段限制1次。)
远古印记：+2。你可以选择黛安娜·史丹利底下的一张卡牌加入手牌。
额外设置：每场游戏开始时，你的起始手牌中额外有1张黑暗洞察。

简化说明：
- "黛安娜底下的卡牌"存放在 scenario.vars["beneath_{investigator_id}"]
  （与 sefina_rousseau / stars_of_hyades 共用的既定约定）。
- 取消/忽略侦测（双通道）：
  a) 自动侦测：本仓库取消类卡牌普遍在事件 ctx.extra 留 "{card}_cancelled" /
     "{card}_ignored_damage|horror" 标记；本实现以 REACTION 优先级监听
     ENCOUNTER_CARD_DRAWN / CARD_DRAWN / CHAOS_TOKEN_RESOLVED，解析标记对应
     的卡 id（精确或 "{prefix}_lv{N}" 匹配卡库），并以"该卡在黛安娜手牌或
     弃牌堆"判定归属（官方为"你拥有的卡牌"，手牌/弃牌堆是可靠代理）。
  b) 公开方法 notify_cancellation()：对调用 ctx.cancel() 的取消卡（如
     黑暗洞察、否决存在——事件总线在 cancelled 后中断后续处理器，REACTION
     无法再收到，引擎缺口）由会话层显式通报。
  通用的 "cancel_auto_fail" 标记不带卡牌身份，不在自动侦测范围。
- 置于她底下时该卡从手牌/弃牌堆移除（若在其中）；抽牌直接移动牌库顶到手牌，
  不发 CARD_DRAWN（避免递归触发，同 mark_harrigan）。
- 远古印记"选择一张加入手牌"：scenario.vars["diana_stanley_beneath_choice"]
  可预设，缺省取她底下的第一张（官方为玩家选择且可放弃）。
- 额外设置：引擎 setup 抽牌流程固定抽5张且不可拦截，在第5次 setup 阶段
  CARD_DRAWN 时把黑暗洞察直接加入手牌（官方为起始手牌的额外卡牌，不占
  牌库；若牌库非法含黑暗洞察可能重复——牌组构建规则约束，不校验）。
- 马泰奥神父将自动失败转为远古印记时（father_mateo_converted 标记），本卡
  同样按远古印记结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Phase, Skill, TimingPriority,
)

BENEATH_LIMIT = 5
DARK_INSIGHT_ID = "dark_insight_lv0"
OPENING_HAND_DRAW = 5

_CANCEL_EVENTS = (
    GameEvent.ENCOUNTER_CARD_DRAWN,
    GameEvent.CARD_DRAWN,
    GameEvent.CHAOS_TOKEN_RESOLVED,
)


def beneath_key(investigator_id: str) -> str:
    return f"beneath_{investigator_id}"


class DianaStanley(CardImplementation):
    card_id = "diana_stanley"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_phase = False
        self._setup_draws = 0
        self._dark_insight_added = False

    def _get_diana(self, game_state, investigator_id):
        """Return the investigator state iff it is Diana Stanley."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "diana_stanley":
            return None
        return inv

    def _beneath(self, game_state, investigator_id) -> list:
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return []
        return scenario.vars.setdefault(beneath_key(investigator_id), [])

    # ------------------------------------------------------------------
    # 被动：底下每有1张卡牌 +1意志
    # ------------------------------------------------------------------

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def willpower_bonus(self, ctx):
        """底下每有1张卡牌，+1意志。"""
        if ctx.skill_type != Skill.WILLPOWER:
            return
        inv = self._get_diana(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        count = len(self._beneath(ctx.game_state, ctx.investigator_id))
        if count:
            ctx.modify_amount(count, "diana_stanley_ability")

    # ------------------------------------------------------------------
    # [reaction] 你拥有的卡牌取消/忽略效果后：置于她底下（每阶段限1次）
    # ------------------------------------------------------------------

    @on_event(GameEvent.MYTHOS_PHASE_BEGINS, priority=TimingPriority.WHEN)
    @on_event(GameEvent.INVESTIGATION_PHASE_BEGINS, priority=TimingPriority.WHEN)
    @on_event(GameEvent.ENEMY_PHASE_BEGINS, priority=TimingPriority.WHEN)
    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.WHEN)
    def reset_phase_limit(self, ctx):
        """每个阶段开始时重置限次。"""
        self._used_this_phase = False

    def _resolve_card_id(self, game_state, prefix):
        db = game_state.card_database
        if prefix in db:
            return prefix
        for lvl in range(6):
            candidate = f"{prefix}_lv{lvl}"
            if candidate in db:
                return candidate
        return None

    def _detect_cancelled_card(self, ctx):
        """从事件 extra 标记解析取消/忽略效果的卡牌 id。"""
        for key in ctx.extra:
            if key.endswith("_cancelled"):
                card_id = self._resolve_card_id(
                    ctx.game_state, key[:-len("_cancelled")])
                if card_id:
                    return card_id
        for key in ctx.extra:
            for suffix in ("_ignored_damage", "_ignored_horror"):
                if key.endswith(suffix):
                    card_id = self._resolve_card_id(
                        ctx.game_state, key[:-len(suffix)])
                    if card_id:
                        return card_id
        return None

    def _owns_card(self, diana, card_id) -> bool:
        """归属判定：该卡在黛安娜的手牌或弃牌堆中。"""
        return card_id in diana.hand or card_id in diana.discard

    def _place_beneath(self, game_state, diana, card_id) -> bool:
        beneath = self._beneath(game_state, diana.investigator_id)
        if self._used_this_phase or len(beneath) >= BENEATH_LIMIT:
            return False
        if card_id in diana.hand:
            diana.hand.remove(card_id)
        if card_id in diana.discard:
            diana.discard.remove(card_id)
        beneath.append(card_id)
        self._used_this_phase = True
        if diana.deck:
            diana.hand.append(diana.deck.pop(0))
        diana.resources += 1
        game_state.log_effect(
            f"🌑 黛安娜·史丹利：【{game_state.card_name(card_id)}】置于她底下，"
            f"抽1张牌并获得1资源"
        )
        return True

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.REACTION)
    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.REACTION)
    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.REACTION)
    def detect_cancellation(self, ctx):
        """自动侦测带 extra 标记的取消/忽略（不含 ctx.cancel() 类）。"""
        if self._used_this_phase:
            return
        card_id = self._detect_cancelled_card(ctx)
        if card_id is None:
            return
        for inv in ctx.game_state.investigators.values():
            card_data = getattr(inv, "card_data", None)
            if card_data is not None and card_data.id == "diana_stanley" \
                    and self._owns_card(inv, card_id):
                self._place_beneath(ctx.game_state, inv, card_id)
                return

    def notify_cancellation(self, game_state, card_id,
                            owner_id=None) -> bool:
        """取消/忽略结算的显式通报通道（ctx.cancel() 类取消卡专用）。

        由会话层在取消效果结算后调用；owner_id 缺省时以手牌/弃牌堆判定归属。
        """
        diana = None
        for inv in game_state.investigators.values():
            card_data = getattr(inv, "card_data", None)
            if card_data is not None and card_data.id == "diana_stanley":
                diana = inv
                break
        if diana is None:
            return False
        if owner_id is not None and owner_id != diana.investigator_id:
            return False
        if owner_id is None and not self._owns_card(diana, card_id):
            return False
        return self._place_beneath(game_state, diana, card_id)

    # ------------------------------------------------------------------
    # 额外设置：起始手牌额外有1张黑暗洞察
    # ------------------------------------------------------------------

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def add_dark_insight_on_setup(self, ctx):
        """setup 抽完5张起始手牌后：额外加入1张黑暗洞察。"""
        if self._dark_insight_added:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None or scenario.current_phase != Phase.SETUP:
            return
        inv = self._get_diana(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        self._setup_draws += 1
        if self._setup_draws < OPENING_HAND_DRAW:
            return
        self._dark_insight_added = True
        inv.hand.append(DARK_INSIGHT_ID)
        ctx.game_state.log_effect(
            "🌑 黛安娜·史丹利：起始手牌额外加入【黑暗洞察】"
        )

    # ------------------------------------------------------------------
    # 远古印记
    # ------------------------------------------------------------------

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2。可选择她底下的一张卡牌加入手牌。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN \
                and not ctx.extra.get("father_mateo_converted"):
            return
        inv = self._get_diana(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "diana_stanley_elder_sign")

        beneath = self._beneath(ctx.game_state, ctx.investigator_id)
        if not beneath:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        preset = scenario.vars.get("diana_stanley_beneath_choice") \
            if scenario is not None else None
        chosen = preset if preset in beneath else beneath[0]
        beneath.remove(chosen)
        inv.hand.append(chosen)
        ctx.game_state.log_effect(
            f"🌑 黛安娜·史丹利：远古印记，【{ctx.game_state.card_name(chosen)}】"
            f"加入手牌"
        )
