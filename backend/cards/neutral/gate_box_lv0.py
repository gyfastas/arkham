"""Gate Box (Level 0) — Neutral Asset. Luke Robinson 专属。
使用（3充能）。
[fast] 横置门盒并花费1充能：脱离所有与你交战的敌人，从你的绑定卡中
搜寻梦境之门（奇妙旅程），将其放入战场并移动到该处。

简化说明：
- 引擎无"绑定卡"存储：会话层可将绑定卡 id 放入
  scenario.vars["bonded"][investigator_id]（列表）。本卡在其中搜寻
  "dream_gate"（前缀匹配，含 wondrous journey 版本）；找到且对应地点已在
  场上时直接移动，否则仅记录日志（放入战场由会话层负责，引擎缺口）。
- 数据 JSON 中 uses 键为 "chargess"（上游笔误），读取时兼容两种键名。
- 脱离交战：敌人移回当前地点的未交战列表（保持横置状态不变）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class GateBox(CardImplementation):
    card_id = "gate_box_lv0"
    activations = [{
        "id": "activate",
        "label": "【快速】横置+1充能：脱离交战，搜寻梦境之门并移动",
        "method": "activate",
    }]

    def _charges_key(self, inst) -> str | None:
        for key in ("charges", "chargess"):  # 数据笔误兼容
            if key in inst.uses:
                return key
        return None

    def activate(self, game_state, investigator_id) -> bool:
        inst = game_state.get_card_instance(self.instance_id)
        inv = game_state.get_investigator(investigator_id)
        if inst is None or inv is None or inst.exhausted:
            return False
        key = self._charges_key(inst)
        if key is None or inst.uses.get(key, 0) <= 0:
            return False

        inst.exhausted = True
        inst.uses[key] -= 1

        # 脱离所有与你交战的敌人
        location = game_state.get_location(inv.location_id)
        for enemy_iid in list(inv.threat_area):
            inv.threat_area.remove(enemy_iid)
            if location is not None and enemy_iid not in location.enemies:
                location.enemies.append(enemy_iid)
        game_state.log_effect("🚪 门盒：脱离所有交战的敌人")

        # 搜寻绑定的梦境之门（引擎无绑定卡通道，经 scenario.vars 由会话层提供）
        bonded = game_state.scenario.vars.get("bonded", {}).get(investigator_id, [])
        dream_gate = next(
            (cid for cid in bonded if str(cid).startswith("dream_gate")), None
        )
        if dream_gate is not None:
            if dream_gate in game_state.locations:
                inv.location_id = dream_gate
                game_state.log_effect(f"🚪 门盒：移动到梦境之门（{dream_gate}）")
            else:
                game_state.log_effect(
                    "🚪 门盒：找到绑定的梦境之门，但放入战场需会话层处理"
                )
        else:
            game_state.log_effect("🚪 门盒：未找到绑定的梦境之门")
        return True
