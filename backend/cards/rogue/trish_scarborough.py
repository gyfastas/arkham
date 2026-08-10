"""Trish Scarborough — Rogue Investigator. (07003)
能力：[reaction]你在有敌人的地点发现1个或更多线索后：发现该地点的额外1个线索，
或自动躲避该敌人。（每轮限制一次。）
远古印记：+2。如果是调查检定，你可以选择任一已揭示地点；改为如同你正在该地点调查。

简化说明：
- 反应能力为二选一（额外线索/自动躲避），同步事件流中无法等待玩家输入，
  采用 pending_choice + 公开方法 resolve_reaction()（参考 wendy_adams /
  zoey_samaras 惯例；server 端 pending_choice 解析未接入本 kind，需
  UI/测试直接调用）。限次在玩家实际选择非"不触发"选项时消耗。
- "有敌人的地点"判定同 stray_cat：敌人在该地点（未交战）或与当地点任一
  调查员交战。
- 自动躲避=横置+脱离交战并留在该地点，不发出 ENEMY_EVADED（同 stray_cat
  惯例）。
- 远古印记的"选择任一已揭示地点"：检定同步流程中无法等待选择，实现为
  scenario.vars["trish_elder_sign_location"] 预设（公开方法
  choose_elder_sign_location() 设置，校验已揭示）。线索改道的实现：
  engine/actions._investigate 的 on_success 先从当前地点扣线索再发
  CLUE_DISCOVERED，本实现在 WHEN 优先级把线索退回当前地点、改扣目标地点，
  并把 ctx.location_id 改写为目标地点（后续 handler——含本卡反应能力——
  看到的即为"如同在该地点调查"）。
  已知简化：检定难度仍按原地点隐蔽值结算（CHAOS_TOKEN_RESOLVED 的
  difficulty 修改不会回写 result.difficulty——引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

PENDING_KIND = "trish_scarborough_reaction"
PRESET_KEY = "trish_elder_sign_location"


class TrishScarborough(CardImplementation):
    card_id = "trish_scarborough"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_round = False
        self._investigating = False
        self._redirect_location: str | None = None

    def _get_trish(self, game_state, investigator_id):
        """Return the investigator state iff it is Trish Scarborough."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "trish_scarborough":
            return None
        return inv

    def _enemies_at_location(self, game_state, location_id) -> list[str]:
        """该地点的敌人：未交战（地点敌人列表）或与当地点调查员交战。"""
        found: list[str] = []
        loc = game_state.get_location(location_id)
        if loc is not None:
            found.extend(loc.enemies)
        for inv in game_state.investigators.values():
            if inv.location_id != location_id:
                continue
            for eid in inv.threat_area:
                if eid not in found:
                    found.append(eid)
        return [eid for eid in found
                if game_state.get_card_instance(eid) is not None]

    # ------------------------------------------------------------------
    # 反应能力：发现线索的地点有敌人 → 额外线索 或 自动躲避（每轮限1次）
    # ------------------------------------------------------------------

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        self._used_this_round = False

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.REACTION)
    def offer_reaction(self, ctx):
        """在有敌人的地点发现线索后：设置 pending_choice 供玩家二选一。"""
        if self._used_this_round or not ctx.location_id:
            return
        inv = self._get_trish(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None:
            return

        enemies = self._enemies_at_location(ctx.game_state, ctx.location_id)
        if not enemies:
            return

        loc = ctx.game_state.get_location(ctx.location_id)
        options = []
        if loc is not None and loc.clues > 0:
            options.append({"id": "clue", "label": "发现该地点的额外1个线索"})
        for eid in enemies:
            edata = ctx.game_state.get_card_data(
                ctx.game_state.get_card_instance(eid).card_id)
            ename = getattr(edata, "name_cn", None) or getattr(edata, "name", eid)
            options.append({"id": f"evade:{eid}", "label": f"自动躲避【{ename}】"})
        options.append({"id": "decline", "label": "不触发"})

        scenario.vars["pending_choice"] = {
            "kind": PENDING_KIND,
            "investigator_id": ctx.investigator_id,
            "location_id": ctx.location_id,
            "prompt": "<b>特里希·斯卡波罗</b>：你在有敌人的地点发现线索，"
                      "是否触发反应能力？",
            "options": options,
        }

    def resolve_reaction(self, game_state, investigator_id, choice: str) -> bool:
        """执行玩家选择："clue" / "evade:{enemy_id}" / "decline"。由 UI 调用。"""
        scenario = getattr(game_state, "scenario", None)
        pending = scenario.vars.get("pending_choice", {}) if scenario else {}
        if pending.get("kind") != PENDING_KIND:
            return False
        if pending.get("investigator_id") != investigator_id:
            return False
        inv = self._get_trish(game_state, investigator_id)
        if inv is None:
            return False
        location_id = pending.get("location_id")
        loc = game_state.get_location(location_id)

        if choice == "decline":
            scenario.vars.pop("pending_choice", None)
            return True

        if choice == "clue":
            if loc is None or loc.clues <= 0:
                return False
            loc.clues -= 1
            inv.clues += 1
            game_state.log_effect("🕵️ 特里希·斯卡波罗：发现额外1个线索")
        elif choice.startswith("evade:"):
            enemy_id = choice.split(":", 1)[1]
            if enemy_id not in self._enemies_at_location(game_state, location_id):
                return False
            enemy = game_state.get_card_instance(enemy_id)
            enemy.exhausted = True
            for other in game_state.investigators.values():
                if enemy_id in other.threat_area:
                    other.threat_area.remove(enemy_id)
            if loc is not None and enemy_id not in loc.enemies:
                loc.enemies.append(enemy_id)
            game_state.log_effect("🕵️ 特里希·斯卡波罗：自动躲避敌人")
        else:
            return False

        self._used_this_round = True
        scenario.vars.pop("pending_choice", None)
        return True

    # ------------------------------------------------------------------
    # 远古印记：+2；调查检定可改到任一已揭示地点调查
    # ------------------------------------------------------------------

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def track_investigation(self, ctx):
        if self._get_trish(ctx.game_state, ctx.investigator_id) is not None:
            self._investigating = True

    def choose_elder_sign_location(self, game_state, investigator_id,
                                   location_id: str | None) -> bool:
        """预设远古印记改道目标（任一已揭示地点；None 清除预设）。由 UI 调用。"""
        inv = self._get_trish(game_state, investigator_id)
        if inv is None:
            return False
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return False
        if location_id is None:
            scenario.vars.pop(PRESET_KEY, None)
            return True
        loc = game_state.get_location(location_id)
        if loc is None or not loc.revealed:
            return False
        scenario.vars[PRESET_KEY] = location_id
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2；调查检定且预设了已揭示地点时，结算时改道该地点。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_trish(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "trish_scarborough_elder_sign")

        if not self._investigating:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        target_id = scenario.vars.get(PRESET_KEY) if scenario else None
        if not target_id or target_id == inv.location_id:
            return
        loc = ctx.game_state.get_location(target_id)
        if loc is None or not loc.revealed:
            return
        self._redirect_location = target_id

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.WHEN)
    def redirect_clue(self, ctx):
        """远古印记改道：把当前地点刚发现的线索改扣到预设地点。"""
        if self._redirect_location is None:
            return
        inv = self._get_trish(ctx.game_state, ctx.investigator_id)
        if inv is None or ctx.location_id != inv.location_id:
            return
        target_id = self._redirect_location
        self._redirect_location = None

        target = ctx.game_state.get_location(target_id)
        current = ctx.game_state.get_location(ctx.location_id)
        if target is None or target.clues <= 0 or current is None:
            return
        current.clues += 1   # 退回 on_success 已扣的线索
        target.clues -= 1    # 改为从目标地点发现
        ctx.location_id = target_id
        ctx.game_state.log_effect(
            "🕵️ 特里希·斯卡波罗：远古印记，改为如同在目标地点调查")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_test_state(self, ctx):
        self._investigating = False
        self._redirect_location = None
