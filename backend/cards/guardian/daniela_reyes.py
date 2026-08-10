"""Daniela Reyes — Guardian Investigator. (08001)
能力：[reaction]在一名敌人攻击你后（除了你引起的趁乱攻击外），即使该攻击被
取消：对该敌人造成1点伤害，或自动躲避它。
远古印记：+1。如果你本轮被敌人攻击过，改为你自动成功。

简化说明：
- 触发挂 ENEMY_ATTACKS（敌方阶段攻击）。趁乱攻击发出的是
  ATTACK_OF_OPPORTUNITY 事件而非 ENEMY_ATTACKS，天然排除，符合卡面。
  "即使该攻击被取消"：ENEMY_ATTACKS 在伤害结算前发出、无论 ctx.cancelled
  与否本实现都触发（同官方"攻击发生后"的反应窗口；引擎时序上前置到伤害
  结算前，结果等价——躲避不会撤销本次伤害，与官方一致）。
- 二选一（1伤害/自动躲避）采用 pending_choice + 公开方法
  resolve_reaction()（参考 wendy_adams 惯例；server 端未接入本 kind，需
  UI/测试直接调用）。多名敌人连续攻击时内部排队，pending_choice 始终展示
  队首。本能力无每轮限次。
- 造成1点伤害走 _shared.deal_damage_to_enemy（含击败结算与
  ENEMY_DEFEATED）；自动躲避=横置+脱离交战并留在丹妮拉所在地点，不发出
  ENEMY_EVADED（同 stray_cat 惯例）。
- 远古印记"自动成功"以 SKILL_VALUE_DETERMINED +999 近似（引擎无自动成功
  通道，同 wendy_adams 惯例）；"被攻击过"按本轮 ENEMY_ATTACKS 记录。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards._shared import deal_damage_to_enemy
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

PENDING_KIND = "daniela_reyes_reaction"


class DanielaReyes(CardImplementation):
    card_id = "daniela_reyes"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._attacked_this_round = False
        self._pending_attacks: list[str] = []  # 待抉择的敌方攻击（enemy_id 队列）
        self._elder_sign_auto_success = False

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def _get_daniela(self, game_state, investigator_id):
        """Return the investigator state iff it is Daniela Reyes."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "daniela_reyes":
            return None
        return inv

    # ------------------------------------------------------------------
    # [reaction] 敌人攻击你后（即使被取消）：1伤害 或 自动躲避
    # ------------------------------------------------------------------

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round(self, ctx):
        self._attacked_this_round = False

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.REACTION)
    def on_enemy_attacks(self, ctx):
        """敌人攻击丹妮拉后：记录被攻击（供远古印记）并入队待抉择。"""
        inv = self._get_daniela(ctx.game_state, ctx.investigator_id)
        if inv is None or not ctx.enemy_id:
            return
        if ctx.game_state.get_card_instance(ctx.enemy_id) is None:
            return

        self._attacked_this_round = True
        self._pending_attacks.append(ctx.enemy_id)
        self._refresh_pending_choice(ctx.game_state, ctx.investigator_id)

    def _refresh_pending_choice(self, game_state, investigator_id) -> None:
        """把队首攻击写入 pending_choice（无待决则清除）。"""
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return
        if not self._pending_attacks:
            pending = scenario.vars.get("pending_choice", {})
            if pending.get("kind") == PENDING_KIND:
                scenario.vars.pop("pending_choice", None)
            return
        enemy_id = self._pending_attacks[0]
        inst = game_state.get_card_instance(enemy_id)
        edata = game_state.get_card_data(inst.card_id) if inst else None
        ename = getattr(edata, "name_cn", None) or getattr(edata, "name", enemy_id)
        scenario.vars["pending_choice"] = {
            "kind": PENDING_KIND,
            "investigator_id": investigator_id,
            "enemy_id": enemy_id,
            "prompt": f"<b>丹妮拉·雷耶丝</b>：【{ename}】攻击了你，是否触发反应能力？",
            "options": [
                {"id": "damage", "label": f"对【{ename}】造成1点伤害"},
                {"id": "evade", "label": f"自动躲避【{ename}】"},
                {"id": "decline", "label": "不触发"},
            ],
        }

    def resolve_reaction(self, game_state, investigator_id, choice: str) -> bool:
        """执行玩家选择："damage" / "evade" / "decline"（作用于队首攻击）。由 UI 调用。"""
        inv = self._get_daniela(game_state, investigator_id)
        if inv is None or not self._pending_attacks:
            return False
        enemy_id = self._pending_attacks[0]
        enemy = game_state.get_card_instance(enemy_id)

        if choice == "damage":
            if enemy is not None:
                deal_damage_to_enemy(
                    game_state, self._bus, enemy_id, 1,
                    defeated_by=investigator_id)
                game_state.log_effect("🔧 丹妮拉·雷耶丝：对攻击者造成1点伤害")
        elif choice == "evade":
            if enemy is not None:
                enemy.exhausted = True
                for other in game_state.investigators.values():
                    if enemy_id in other.threat_area:
                        other.threat_area.remove(enemy_id)
                loc = game_state.get_location(inv.location_id)
                if loc is not None and enemy_id not in loc.enemies:
                    loc.enemies.append(enemy_id)
                game_state.log_effect("🔧 丹妮拉·雷耶丝：自动躲避攻击者")
        elif choice != "decline":
            return False

        self._pending_attacks.pop(0)
        self._refresh_pending_choice(game_state, investigator_id)
        return True

    # ------------------------------------------------------------------
    # 远古印记：+1；本轮被攻击过则改为自动成功
    # ------------------------------------------------------------------

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1；本轮被敌人攻击过则改为自动成功（+999 近似）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_daniela(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        if self._attacked_this_round:
            self._elder_sign_auto_success = True
        else:
            ctx.modify_amount(1, "daniela_reyes_elder_sign")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def elder_sign_auto_success(self, ctx):
        """以 +999 近似"自动成功"。"""
        if not self._elder_sign_auto_success:
            return
        inv = self._get_daniela(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(999, "daniela_reyes_auto_success")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_test_state(self, ctx):
        self._elder_sign_auto_success = False
