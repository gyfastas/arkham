"""Archive of Conduits (Level 0) — Seeker Asset, Hand slot. (08033)
每牌组限1张。作为打出本支援的额外费用，在4个不同地点上各放置1资源，
作为地线。
[反应]在你成功调查了一个带有地线的地点后，横置本支援：将该地线移动到
本支援上。然后，若本支援上有4条地线，丢弃本支援，将其上的地线作为资源
收入囊中，并在冒险日志中记录"你已查明传送门"。

简化说明：
- 打出时的额外费用在 CARD_ENTERS_PLAY 自动结算：地线自动放置到（按 id
  排序的）前4个地点（官方为玩家自选4个不同地点）；不足4个地点时尽力放置
  （官方为无法打出，从宽处理并记录日志）；
- 地线台账存于 scenario.vars["leylines"]["locations"]（与
  archive_of_conduits_lv4 的"investigators"台账共用同一约定）；
- 反应自动触发（官方为玩家选择是否横置；移动地线为纯收益）；
- 冒险日志记录在 scenario.vars["campaign_log"]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority

CAMPAIGN_LOG_ENTRY = "你已查明传送门"
LEYLINES_VAR = "leylines"
REQUIRED_LEYLINES = 4


def leyline_store(game_state) -> dict:
    """全局地线台账：{"locations": {loc_id: n}, "investigators": {inv_id: n}}。"""
    store = game_state.scenario.vars.setdefault(LEYLINES_VAR, {})
    store.setdefault("locations", {})
    store.setdefault("investigators", {})
    return store


class ArchiveOfConduits(CardImplementation):
    card_id = "archive_of_conduits_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._investigating: tuple[str, str] | None = None  # (inv_id, loc_id)

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def place_leylines(self, ctx):
        """打出的额外费用：在4个不同地点各放置1条地线（自动取前4个地点）。"""
        if ctx.target != self.instance_id:
            return
        store = leyline_store(ctx.game_state)
        placed = 0
        for loc_id in sorted(ctx.game_state.locations):
            if placed >= REQUIRED_LEYLINES:
                break
            locs = store["locations"]
            locs[loc_id] = locs.get(loc_id, 0) + 1
            placed += 1
        ctx.game_state.log_effect(
            f"🌀 导管档案：在{placed}个地点各放置1条地线"
        )

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        self._investigating = (ctx.investigator_id, ctx.location_id)

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def collect_leyline(self, ctx):
        """成功调查带地线的地点后：横置本支援，将该地线移到本支援上。"""
        if self._investigating is None:
            return
        inv_id, loc_id = self._investigating
        if ctx.investigator_id != inv_id or ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        store = leyline_store(ctx.game_state)
        if store["locations"].get(loc_id, 0) <= 0:
            return

        inst.exhausted = True
        store["locations"][loc_id] -= 1
        inst.uses["leylines"] = inst.uses.get("leylines", 0) + 1
        count = inst.uses["leylines"]
        ctx.game_state.log_effect(
            f"🌀 导管档案：横置，将该地点的地线移到本支援上（{count}/4）"
        )
        if count >= REQUIRED_LEYLINES:
            self._identify_gateway(ctx.game_state, inv)

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._investigating = None

    def _identify_gateway(self, game_state, inv) -> None:
        """集齐4条地线：丢弃本支援，地线转为资源，记录冒险日志。"""
        inst = game_state.get_card_instance(self.instance_id)
        taken = inst.uses.get("leylines", 0) if inst else REQUIRED_LEYLINES
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)
        inv.resources += taken
        log = game_state.scenario.vars.setdefault("campaign_log", [])
        if CAMPAIGN_LOG_ENTRY not in log:
            log.append(CAMPAIGN_LOG_ENTRY)
        game_state.log_effect(
            f"🌀 导管档案：集齐4条地线！丢弃本支援，获得{taken}资源，"
            "记录冒险日志"
        )
