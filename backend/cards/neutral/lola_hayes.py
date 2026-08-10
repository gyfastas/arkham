"""Lola Hayes — Neutral Investigator.
能力：强制 - 你抽取起始手牌后：选择一个角色([survivor]、[guardian]、[seeker]、
[rogue]、[mystic]或中立)。
你打出、投入或触发能力的卡牌只限于中立卡和你所选角色的卡牌。
[fast]：切换你的角色。(每轮限制1次。)
远古印记：+2。你可以切换角色。

简化说明：
- "角色"没有引擎级状态，按阵营字符串存放在
  scenario.vars["role_{investigator_id}"]（缺省 "neutral"），与
  crisis_of_identity_lv0 / improvisation_lv0 共用的既定约定。
- 初始角色：Game.setup() 的抽牌流程不可拦截，实现为 setup 阶段第5次
  CARD_DRAWN 后设置 pending_choice（kind="lola_hayes_initial_role"，6个角色
  选项），由会话层/UI 解析后调用 resolve_role_choice()；解析前角色保持缺省
  "neutral"（简化：官方为强制立即选择）。也可不经 pending_choice 直接预设
  scenario.vars["role_{investigator_id}"]。
- 出牌/投入/触发限制：引擎的打出与提交通道（actions._play、skill_test 投入）
  不查询角色限制——引擎缺口，由 can_play_card() 表达该规则，待会话层接线。
- [fast] 切换角色实现为公开方法 switch_role()（参考 ashcan_pete 的
  activate_ready_asset 模式），由 UI 在玩家选择发动时调用；每轮限1次。
- 远古印记的"你可以切换角色"：同步检定流程中无法等待玩家选择，实现为设置
  pending_choice（kind="lola_hayes_elder_sign_role"，含"不切换"选项），
  由会话层/UI 解析后调用 resolve_role_choice()；该切换不占每轮限次。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Phase, TimingPriority,
)

ROLES = ("survivor", "guardian", "seeker", "rogue", "mystic", "neutral")
OPENING_HAND_DRAW = 5

_ROLE_LABELS = {
    "survivor": "求生者",
    "guardian": "守卫者",
    "seeker": "探求者",
    "rogue": "流浪者",
    "mystic": "潜修者",
    "neutral": "中立",
}


def role_key(investigator_id: str) -> str:
    return f"role_{investigator_id}"


class LolaHayes(CardImplementation):
    card_id = "lola_hayes"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._setup_draws = 0
        self._initial_role_offered = False
        self._switch_used_this_round = False

    def _get_lola(self, game_state, investigator_id):
        """Return the investigator state iff it is Lola Hayes."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "lola_hayes":
            return None
        return inv

    @staticmethod
    def get_role(game_state, investigator_id) -> str:
        """当前角色（缺省 "neutral"）。"""
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return "neutral"
        return scenario.vars.get(role_key(investigator_id), "neutral")

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def offer_initial_role(self, ctx):
        """强制 - 抽取起始手牌后：设置初始角色的 pending_choice。"""
        if self._initial_role_offered:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None or scenario.current_phase != Phase.SETUP:
            return
        inv = self._get_lola(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        self._setup_draws += 1
        if self._setup_draws < OPENING_HAND_DRAW:
            return
        self._initial_role_offered = True

        scenario.vars["pending_choice"] = {
            "kind": "lola_hayes_initial_role",
            "investigator_id": ctx.investigator_id,
            "prompt": "<b>萝拉·海耶斯</b>：选择你的初始角色。",
            "options": [
                {"id": role, "label": _ROLE_LABELS[role]} for role in ROLES
            ],
        }

    def resolve_role_choice(self, game_state, investigator_id, role) -> bool:
        """解析角色选择（初始/远古印记）：写入角色并清除对应 pending_choice。"""
        inv = self._get_lola(game_state, investigator_id)
        if inv is None or role not in ROLES:
            return False
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return False

        pending = scenario.vars.get("pending_choice", {})
        if pending.get("kind") in (
            "lola_hayes_initial_role", "lola_hayes_elder_sign_role"
        ) and pending.get("investigator_id") == investigator_id:
            scenario.vars.pop("pending_choice", None)

        scenario.vars[role_key(investigator_id)] = role
        game_state.log_effect(
            f"🎭 萝拉·海耶斯：角色切换为【{_ROLE_LABELS[role]}】"
        )
        return True

    def decline_role_choice(self, game_state, investigator_id) -> bool:
        """放弃远古印记的角色切换（仅清除 pending_choice）。"""
        inv = self._get_lola(game_state, investigator_id)
        scenario = getattr(game_state, "scenario", None)
        if inv is None or scenario is None:
            return False
        pending = scenario.vars.get("pending_choice", {})
        if pending.get("kind") == "lola_hayes_elder_sign_role" and \
                pending.get("investigator_id") == investigator_id:
            scenario.vars.pop("pending_choice", None)
            return True
        return False

    def switch_role(self, game_state, investigator_id, new_role) -> bool:
        """[fast]：切换你的角色（每轮限1次）。由 UI 调用。"""
        inv = self._get_lola(game_state, investigator_id)
        if inv is None or new_role not in ROLES:
            return False
        if self._switch_used_this_round:
            return False
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return False
        self._switch_used_this_round = True
        scenario.vars[role_key(investigator_id)] = new_role
        game_state.log_effect(
            f"🎭 萝拉·海耶斯：[fast]角色切换为【{_ROLE_LABELS[new_role]}】"
        )
        return True

    def can_play_card(self, game_state, investigator_id, card_id) -> bool:
        """角色限制：只能打出/投入/触发中立卡或当前角色卡（会话层接线用）。"""
        if self._get_lola(game_state, investigator_id) is None:
            return True  # 非萝拉不受限制
        cd = game_state.get_card_data(card_id)
        if cd is None:
            return False
        card_class = getattr(cd.card_class, "value", cd.card_class)
        return card_class in ("neutral", self.get_role(game_state, investigator_id))

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        """每轮开始时重置切换角色的限次。"""
        self._switch_used_this_round = False

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2。你可以切换角色（pending_choice 由会话层解析）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_lola(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "lola_hayes_elder_sign")

        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None:
            return
        scenario.vars["pending_choice"] = {
            "kind": "lola_hayes_elder_sign_role",
            "investigator_id": ctx.investigator_id,
            "prompt": "<b>萝拉·海耶斯</b>：远古印记，你可以切换角色。",
            "options": [
                *({"id": role, "label": _ROLE_LABELS[role]} for role in ROLES),
                {"id": "decline", "label": "不切换"},
            ],
        }
