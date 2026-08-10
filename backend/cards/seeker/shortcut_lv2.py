"""Shortcut (Level 2) — Seeker Event, Fast.
快速。只能在你回合中打出。附加到你所在地点。被附加地点获得：
"[快速]横置捷径：移动（至1个连接地点）。本地点的任意调查员可触发此能力。"

简化说明：
- 附加关系记录在 scenario.vars["shortcut_lv2_attached"]
  （{location_id: {"exhausted": bool}}，与 Barricade 同模式）；
- 移动目的地沿用 lv0 的 pending_choice(kind="shortcut_move") 流程，
  由会话层 _resolve_choice 完成移动；
- 横置状态在 UPKEEP_PHASE_ENDS 重置；
- 已知限制（同 Barricade）：事件实现实例在 ROUND_ENDS 被引擎清理，
  跨轮后 activate() 不再可用，需要引擎/场景侧钩子支持持久附加。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_VAR = "shortcut_lv2_attached"


class ShortcutLv2(CardImplementation):
    card_id = "shortcut_lv2"
    activations = [{
        "id": "move",
        "label": "【快速】横置捷径：移动至1个连接地点",
        "method": "activate",
    }]

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_location(self, ctx):
        """打出时：附加到你所在地点。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        attached = ctx.game_state.scenario.vars.setdefault(_VAR, {})
        attached[inv.location_id] = {"exhausted": False}
        ctx.extra["shortcut_lv2_attached"] = inv.location_id
        ctx.game_state.log_effect("🛣️ 捷径：附加到当前地点")

    def activate(self, game_state, investigator_id: str) -> bool:
        """【快速】横置捷径：本地点任意调查员移动至1个连接地点。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        attached = game_state.scenario.vars.get(_VAR, {})
        entry = attached.get(inv.location_id)
        if entry is None or entry.get("exhausted"):
            return False
        location = game_state.get_location(inv.location_id)
        connections = list(getattr(location, "connections", []) or []) \
            if location is not None else []
        if not connections:
            return False

        entry["exhausted"] = True

        def _label(loc_id: str) -> str:
            loc = game_state.get_location(loc_id)
            if loc is not None and loc.card_data is not None:
                return loc.card_data.name_cn or loc.card_data.name
            return loc_id

        game_state.scenario.vars["pending_choice"] = {
            "kind": "shortcut_move",
            "investigator_id": investigator_id,
            "from_location": inv.location_id,
            "prompt": "<b>捷径</b>：选择一个连接地点，将该调查员移动过去",
            "options": [
                {"id": loc_id, "label": _label(loc_id)} for loc_id in connections
            ],
        }
        game_state.log_effect("🛣️ 捷径：横置，选择连接地点移动")
        return True

    @on_event(GameEvent.UPKEEP_PHASE_ENDS, priority=TimingPriority.AFTER)
    def ready_in_upkeep(self, ctx):
        """upkeep 重置横置状态（本轮内打出时生效）。"""
        for entry in ctx.game_state.scenario.vars.get(_VAR, {}).values():
            entry["exhausted"] = False
