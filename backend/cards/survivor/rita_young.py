"""Rita Young — Survivor Investigator.
能力：[reaction]在你躲避一名敌人后：对该敌人造成1点伤害，或者移动到一个连接地点。
（每轮限制1次。）
远古印记：+2。忽略以上[reaction]能力的限制，直到本轮结束。

实现说明：
- ENEMY_EVADED 事件携带 investigator_id 与 enemy_id（见 engine/actions.py 的
  _evade 成功分支），据此判定"你躲避"。
- 躲避后的二选一为玩家选择：触发时设置 scenario.vars["pending_choice"]
  （kind="rita_young_evade"，参考 zoey_samaras 模式，供 UI 展示选项）；实际结算由
  公开方法 resolve_evade_choice() 执行（server 端 pending_choice 解析未接入本
  kind，需 UI/测试直接调用）。
- "造成1点伤害"经 _shared.deal_damage_to_enemy 结算（含击败/胜利牌堆处理），
  事件总线在 register() 时保存（self._bus）；未绑定时退化为直接加减伤害。
- "移动到一个连接地点"直接改 location_id（与引擎 _move 一致；交战中的敌人随
  调查员移动由威胁区归属隐式处理）。destination 缺省时取第一个连接地点。
- 远古印记的"忽略限制"以 _ignore_limit 标记记录，ROUND_ENDS 时清除；限次在
  ROUND_BEGINS 时重置。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class RitaYoung(CardImplementation):
    card_id = "rita_young"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_round = False
        self._ignore_limit = False
        self._pending_enemy: str | None = None
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def _get_rita(self, game_state, investigator_id):
        """Return the investigator state iff it is Rita Young."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "rita_young":
            return None
        return inv

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        """每轮开始时重置限次。"""
        self._used_this_round = False

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def clear_ignore_limit(self, ctx):
        """远古印记的"忽略限制"持续到本轮结束。"""
        self._ignore_limit = False

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.REACTION)
    def offer_evade_reaction(self, ctx):
        """躲避一名敌人后：提供"造成1伤害 / 移动到连接地点"二选一（每轮限1次）。"""
        if self._used_this_round and not self._ignore_limit:
            return
        inv = self._get_rita(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        enemy_id = ctx.enemy_id or ctx.target
        if not enemy_id:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None:
            return

        if not self._ignore_limit:
            self._used_this_round = True
        self._pending_enemy = enemy_id

        enemy = ctx.game_state.get_card_instance(enemy_id)
        enemy_name = enemy_id
        if enemy is not None:
            enemy_name = ctx.game_state.card_name(enemy.card_id)

        options = [{"id": "damage", "label": f"对【{enemy_name}】造成1点伤害"}]
        location = ctx.game_state.get_location(inv.location_id)
        connections = location.connections if location else []
        if connections:
            options.append({"id": "move", "label": "移动到一个连接地点"})
        options.append({"id": "decline", "label": "不触发"})

        scenario.vars["pending_choice"] = {
            "kind": "rita_young_evade",
            "investigator_id": ctx.investigator_id,
            "enemy_id": enemy_id,
            "connections": list(connections),
            "prompt": f"<b>丽塔·杨</b>：你躲避了【{enemy_name}】，选择效果：",
            "options": options,
        }

    def resolve_evade_choice(self, game_state, investigator_id, choice,
                             destination: str | None = None) -> bool:
        """结算躲避后的二选一。由 UI 在玩家选择 pending_choice 中的选项后调用。

        choice: "damage"（对被躲避的敌人造成1伤害）/ "move"（移动到连接地点，
        destination 缺省取第一个连接地点）/ "decline"（不触发）。
        """
        inv = self._get_rita(game_state, investigator_id)
        if inv is None:
            return False
        enemy_id = self._pending_enemy
        scenario = getattr(game_state, "scenario", None)
        if enemy_id is None and scenario is not None:
            pending = scenario.vars.get("pending_choice", {})
            if pending.get("kind") == "rita_young_evade":
                enemy_id = pending.get("enemy_id")
        if enemy_id is None:
            return False

        if scenario is not None:
            pending = scenario.vars.get("pending_choice", {})
            if pending.get("kind") == "rita_young_evade":
                scenario.vars.pop("pending_choice", None)
        self._pending_enemy = None

        if choice == "damage":
            deal_damage_to_enemy(
                game_state, self._bus, enemy_id, 1, defeated_by=investigator_id,
            )
            game_state.log_effect("🏃 丽塔·杨：躲避后对该敌人造成1点伤害")
            return True
        if choice == "move":
            location = game_state.get_location(inv.location_id)
            connections = location.connections if location else []
            if destination is None and connections:
                destination = connections[0]
            if destination not in connections:
                return False
            if game_state.get_location(destination) is None:
                return False
            inv.location_id = destination
            game_state.log_effect(f"🏃 丽塔·杨：躲避后移动到 {destination}")
            return True
        return choice == "decline"

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2。直到本轮结束，忽略[reaction]能力的每轮限次。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_rita(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "rita_young_elder_sign")
        self._ignore_limit = True
