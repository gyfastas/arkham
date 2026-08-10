"""Gené Beauregard (Level 3) — Seeker Asset, Ally slot. (08099)
你获得+1智力和+1敏捷。
[反应]在你的回合中，在你移动到一个地点后，消耗吉恩·波尔格：将一个线索
或一名非[[精英]]敌人从连接地点移动到你所在地点，或从你所在地点移动到
连接地点。

简化说明：
- "+1智力/+1敏捷"为常驻加值（SKILL_VALUE_DETERMINED，与 dr_milan 一致）；
- "你移动后"以 ACTION_PERFORMED(MOVE) 判定（引擎的 MOVE_ACTION_INITIATED
  在移动生效前发出，故不可用）；
- 反应自动触发（官方为玩家可选）：仅执行"把连接地点的线索移到你所在
  地点"这一种最常用方向——连接地点无线索时不动（避免自动移敌造成意外）；
  其余方向由公开方法 relocate() 显式调用（供会话层/测试传参）；
- "在你的回合中"经 INVESTIGATOR_TURN_BEGINS/ENDS 跟踪。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import Action, GameEvent, Skill, TimingPriority


class GeneBeauregard(CardImplementation):
    card_id = "gené_beauregard_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._my_turn: str | None = None

    # ------------------------------------------------ 常驻技能加值
    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        if ctx.skill_type not in (Skill.INTELLECT, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "gene_beauregard_bonus")

    # ------------------------------------------------ 回合跟踪
    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def track_turn_begin(self, ctx):
        self._my_turn = ctx.investigator_id

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def track_turn_end(self, ctx):
        if self._my_turn == ctx.investigator_id:
            self._my_turn = None

    # ------------------------------------------------ 移动后反应
    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.REACTION)
    def after_move_reaction(self, ctx):
        """你移动到一个地点后：自动执行"线索移到你所在地点"（若有）。"""
        if ctx.action != Action.MOVE:
            return
        if self._my_turn != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        if self._clue_sources(ctx.game_state, inv):
            self.relocate(ctx.game_state, ctx.investigator_id, kind="clue_to_me")
            ctx.extra["gene_beauregard_triggered"] = True

    def relocate(self, game_state, investigator_id: str, kind: str = "clue_to_me",
                 location_id: str | None = None,
                 enemy_instance_id: str | None = None) -> bool:
        """消耗本卡：在连接地点与你所在地点之间移动线索/非精英敌人。

        kind: "clue_to_me"（连接→你）/ "clue_away"（你→连接）/
              "enemy_to_me"（连接→你）/ "enemy_away"（你→连接）。
        """
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        here = game_state.get_location(inv.location_id)
        if here is None:
            return False

        done = False
        if kind.startswith("clue"):
            done = self._move_clue(game_state, here, kind == "clue_to_me", location_id)
        else:
            done = self._move_enemy(game_state, here, kind == "enemy_to_me",
                                    location_id, enemy_instance_id)
        if not done:
            return False
        inst.exhausted = True
        return True

    # ------------------------------------------------ 内部
    def _clue_sources(self, game_state, inv) -> list[str]:
        here = game_state.get_location(inv.location_id)
        if here is None:
            return []
        return [
            cid for cid in (here.connections or [])
            if (loc := game_state.get_location(cid)) is not None and loc.clues > 0
        ]

    def _move_clue(self, game_state, here, to_me: bool, location_id) -> bool:
        if to_me:
            sources = [
                cid for cid in (here.connections or [])
                if (loc := game_state.get_location(cid)) is not None and loc.clues > 0
            ]
            if location_id is not None:
                if location_id not in sources:
                    return False
                src_id = location_id
            elif sources:
                src_id = sources[0]
            else:
                return False
            src = game_state.get_location(src_id)
            src.clues -= 1
            here.clues += 1
            game_state.log_effect("🧭 吉恩·波尔格：将连接地点的1个线索移到你所在地点")
            return True
        # clue_away：你所在地点 → 连接地点
        if here.clues <= 0:
            return False
        dest = None
        if location_id is not None:
            if location_id not in (here.connections or []):
                return False
            dest = game_state.get_location(location_id)
        else:
            for cid in (here.connections or []):
                dest = game_state.get_location(cid)
                if dest is not None:
                    break
        if dest is None:
            return False
        here.clues -= 1
        dest.clues += 1
        game_state.log_effect("🧭 吉恩·波尔格：将你所在地点的1个线索移到连接地点")
        return True

    def _move_enemy(self, game_state, here, to_me: bool, location_id,
                    enemy_instance_id) -> bool:
        if to_me:
            candidates: list[tuple[str, str]] = []  # (loc_id, enemy_iid)
            for cid in (here.connections or []):
                loc = game_state.get_location(cid)
                if loc is None:
                    continue
                for eid in loc.enemies:
                    if self._is_non_elite_enemy(game_state, eid):
                        candidates.append((cid, eid))
            if enemy_instance_id is not None:
                candidates = [c for c in candidates if c[1] == enemy_instance_id]
            if location_id is not None:
                candidates = [c for c in candidates if c[0] == location_id]
            if not candidates:
                return False
            src_id, eid = candidates[0]
            src = game_state.get_location(src_id)
            src.enemies.remove(eid)
            here.enemies.append(eid)
            game_state.log_effect("🧭 吉恩·波尔格：将连接地点的敌人移到你所在地点")
            return True
        # enemy_away：你所在地点（含与你交战者）→ 连接地点
        inv = next((i for i in game_state.investigators.values()
                    if self.instance_id in i.play_area), None)
        engaged = list(inv.threat_area) if inv is not None else []
        pool = [(eid, "engaged") for eid in engaged
                if self._is_non_elite_enemy(game_state, eid)]
        pool += [(eid, "location") for eid in here.enemies
                 if self._is_non_elite_enemy(game_state, eid)]
        if enemy_instance_id is not None:
            pool = [p for p in pool if p[0] == enemy_instance_id]
        if not pool:
            return False
        eid, where = pool[0]
        dest = None
        if location_id is not None:
            if location_id not in (here.connections or []):
                return False
            dest = game_state.get_location(location_id)
        else:
            for cid in (here.connections or []):
                dest = game_state.get_location(cid)
                if dest is not None:
                    break
        if dest is None:
            return False
        if where == "engaged":
            inv.threat_area.remove(eid)
        else:
            here.enemies.remove(eid)
        dest.enemies.append(eid)
        game_state.log_effect("🧭 吉恩·波尔格：将你所在地点的敌人移到连接地点")
        return True

    @staticmethod
    def _is_non_elite_enemy(game_state, enemy_instance_id: str) -> bool:
        inst = game_state.get_card_instance(enemy_instance_id)
        if inst is None:
            return False
        cd = game_state.get_card_data(inst.card_id)
        if cd is None:
            return False
        return "elite" not in (cd.keywords or [])
