"""Agnes Baker — Mystic Investigator.
能力：在阿格尼丝·贝克被放置1点或以上恐惧后：对你所在地点的一名敌人造成1点伤害。
（每阶段限制1次。）
远古印记：+1（阿格尼丝·贝克身上每有1点恐惧，+1）。

简化说明：
- 触发条件按"实际有恐惧落到阿格尼丝身上"判定：DamageEngine 在 HORROR_ASSIGNED
  事件发出前已完成盟友吸收结算（见 engine/damage.py 的 deal_damage 顺序），
  实现通过对比盟友吸收前后恐惧差值推算落到阿格尼丝身上的恐惧量；全部经盟友
  吸收时不触发。盟友恐惧若因事件外的其他途径变化（如直接治愈/直接伤害资产），
  推算可能有偏差（遗留简化，无更精确引擎钩子）。
- 所在地点有多名可选敌人时，默认选择第一个（优先交战中的敌人）；可在触发前设置
  scenario.vars["agnes_baker_target"] = enemy_instance_id 指定目标。
  未实现交互式 pending_choice（需要 server 端解析支持，且不允许修改已有文件）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class AgnesBaker(CardImplementation):
    card_id = "agnes_baker"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_phase = False
        # 盟友恐惧快照：用于推算本次分配中被盟友吸收、而未落到阿格尼丝身上的恐惧
        self._ally_horror: dict[str, int] = {}

    def _get_agnes(self, ctx):
        """Return the investigator state iff ctx investigator is Agnes Baker."""
        if ctx.investigator_id is None:
            return None
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "agnes_baker":
            return None
        return inv

    @on_event(GameEvent.MYTHOS_PHASE_BEGINS, priority=TimingPriority.WHEN)
    @on_event(GameEvent.INVESTIGATION_PHASE_BEGINS, priority=TimingPriority.WHEN)
    @on_event(GameEvent.ENEMY_PHASE_BEGINS, priority=TimingPriority.WHEN)
    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.WHEN)
    def reset_phase_limit(self, ctx):
        """每个阶段开始时重置限次。"""
        self._used_this_phase = False

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.AFTER)
    def deal_damage_on_horror(self, ctx):
        """被放置1点或以上恐惧后：对所在地点的一名敌人造成1点伤害（每阶段限1次）。"""
        inv = self._get_agnes(ctx)
        if inv is None:
            return
        # 实际落到阿格尼丝身上的恐惧 = 原始恐惧量 - 盟友已吸收量
        # （盟友吸收在 HORROR_ASSIGNED 发出前已结算，按快照差值推算）
        absorbed = 0
        for inst_id in inv.play_area:
            inst = ctx.game_state.get_card_instance(inst_id)
            if inst is None:
                continue
            prev = self._ally_horror.get(inst_id)
            if prev is not None and inst.horror > prev:
                absorbed += inst.horror - prev
            self._ally_horror[inst_id] = inst.horror
        landed = max(0, ctx.amount - absorbed)
        if self._used_this_phase or landed < 1:
            return

        # 候选敌人：交战中的敌人 + 所在地点未交战的敌人
        candidates: list[str] = []
        for inst_id in inv.threat_area:
            if ctx.game_state.get_card_instance(inst_id) is not None:
                candidates.append(inst_id)
        location = ctx.game_state.get_location(inv.location_id)
        if location is not None:
            for inst_id in location.enemies:
                if inst_id not in candidates and \
                        ctx.game_state.get_card_instance(inst_id) is not None:
                    candidates.append(inst_id)
        if not candidates:
            return

        scenario = getattr(ctx.game_state, "scenario", None)
        override = scenario.vars.pop("agnes_baker_target", None) if scenario else None
        target_id = override if override in candidates else candidates[0]

        enemy = ctx.game_state.get_card_instance(target_id)
        if enemy is None:
            return
        enemy.damage += 1
        self._used_this_phase = True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1（阿格尼丝·贝克身上每有1点恐惧，+1）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_agnes(ctx)
        if inv is None:
            return
        if inv.horror > 0:
            ctx.modify_amount(inv.horror, "agnes_baker_elder_sign")
