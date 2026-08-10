"""Handcuffs (Level 0) — Guardian Asset. (04265)
[行动]如果手铐未叠加到敌人上：躲避。只能对[[类人生物]]敌人使用。
本次躲避尝试使用[战斗]代替[敏捷]。如果成功，将手铐叠加到刚被躲避的敌人上。
如果被叠加的敌人是非精英，它不能就绪，且毁灭不能放置在它上面。

简化说明：
- [行动]实现为 activate_evade(game, ...)（参照 hypnotic_therapy：由会话层
  调用，接收 Game 以访问 skill_test_engine）；战斗检定对敌人的躲避值，
  成功时镜像 _evade 的结算（横置、脱离交战、放回地点未交战列表）并叠加。
- "不能就绪"：整备阶段引擎先统一就绪再发 CARD_READIED；本卡在该事件中
  把被叠加的非精英敌人重新横置（观察效果等同"不能就绪"）。
- "毁灭不能放置在它上面"：引擎的 DOOM_PLACED 不带目标字段（引擎缺口），
  实现为防御性拦截：ctx.target 命中被叠加敌人时取消；常规路径不触发（注明）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

VAR = "handcuffs_attached"  # scenario.vars: {handcuffs_instance_id: enemy_instance_id}


class Handcuffs(CardImplementation):
    card_id = "handcuffs_lv0"
    activations = [{
        "id": "evade",
        "label": "[行动] 用战斗躲避类人生物敌人，成功则叠加手铐",
        "method": "activate_evade",
        "actions": 1,
        "target": "enemy",
    }]

    def _attached_enemy(self, game_state) -> str | None:
        return game_state.scenario.vars.get(VAR, {}).get(self.instance_id)

    def activate_evade(self, game, investigator_id: str,
                       enemy_instance_id: str | None = None) -> bool:
        """[行动] 战斗躲避类人生物敌人；成功则叠加手铐到该敌人。"""
        game_state = game.state if hasattr(game, "state") else game
        test_engine = getattr(game, "skill_test_engine", None)
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or test_engine is None:
            return False
        if self.instance_id not in inv.play_area:
            return False
        if self._attached_enemy(game_state) is not None:
            return False  # 已叠加

        # 目标：指定的或威胁区/同地点第一个类人生物敌人
        candidates = []
        if enemy_instance_id is not None:
            candidates.append(enemy_instance_id)
        else:
            candidates.extend(inv.threat_area)
            loc = game_state.get_location(inv.location_id)
            if loc is not None:
                candidates.extend(loc.enemies)
        enemy_iid = None
        enemy_data = None
        for iid in candidates:
            enemy = game_state.get_card_instance(iid)
            data = game_state.get_card_data(enemy.card_id) if enemy else None
            if data is not None and "humanoid" in (data.traits or []):
                enemy_iid, enemy_data = iid, data
                break
        if enemy_iid is None:
            return False

        bus = getattr(game, "event_bus", None)
        difficulty = enemy_data.enemy_evade or 0

        def on_success(result):
            enemy = game_state.get_card_instance(enemy_iid)
            if enemy is None:
                return
            enemy.exhausted = True
            if enemy_iid in inv.threat_area:
                inv.threat_area.remove(enemy_iid)
            location = game_state.get_location(inv.location_id)
            if location is not None and enemy_iid not in location.enemies:
                location.enemies.append(enemy_iid)
            game_state.scenario.vars.setdefault(VAR, {})[self.instance_id] = enemy_iid
            inst.attached_to = enemy_iid
            game_state.log_effect(
                f"⛓️ 手铐：叠加到【{game_state.card_name(enemy.card_id)}】")
            if bus is not None:
                from backend.engine.event_bus import EventContext
                bus.emit(EventContext(
                    game_state=game_state,
                    event=GameEvent.ENEMY_EVADED,
                    investigator_id=investigator_id,
                    enemy_id=enemy_iid,
                ))

        test_engine.run_test(
            investigator_id=investigator_id,
            skill_type=Skill.COMBAT,  # 以战斗代替敏捷
            difficulty=difficulty,
            source_instance_id=self.instance_id,
            on_success=on_success,
        )
        return True

    @on_event(GameEvent.CARD_READIED, priority=TimingPriority.AFTER)
    def keep_exhausted(self, ctx):
        """被叠加的非精英敌人不能就绪（整备后重新横置）。"""
        enemy_iid = self._attached_enemy(ctx.game_state)
        if enemy_iid is None or ctx.target != enemy_iid:
            return
        enemy = ctx.game_state.get_card_instance(enemy_iid)
        enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or enemy_data is None:
            return
        if "elite" in (enemy_data.keywords or []):
            return
        enemy.exhausted = True
        ctx.game_state.log_effect(
            f"⛓️ 手铐：【{ctx.game_state.card_name(enemy.card_id)}】不能就绪")

    @on_event(GameEvent.DOOM_PLACED, priority=TimingPriority.WHEN)
    def block_doom(self, ctx):
        """毁灭不能放置在被叠加的敌人上（引擎 DOOM_PLACED 通常无目标，注明）。"""
        enemy_iid = self._attached_enemy(ctx.game_state)
        if enemy_iid is not None and getattr(ctx, "target", None) == enemy_iid:
            ctx.cancel()

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def cleanup_attachment(self, ctx):
        """手铐离场：清除叠加记录。"""
        if ctx.target == self.instance_id:
            ctx.game_state.scenario.vars.get(VAR, {}).pop(self.instance_id, None)

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def cleanup_on_enemy_defeated(self, ctx):
        """被叠加的敌人被击败离场时：依附其上的手铐一并弃置。"""
        enemy_iid = self._attached_enemy(ctx.game_state)
        if enemy_iid is None or ctx.target != enemy_iid:
            return
        ctx.game_state.scenario.vars.get(VAR, {}).pop(self.instance_id, None)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        if owner is not None and self.instance_id in owner.play_area:
            owner.play_area.remove(self.instance_id)
            owner.discard.append(self.card_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(inst.owner_id)
        if slot_mgr is not None:
            slot_mgr.vacate(self.instance_id)
        ctx.game_state.log_effect("⛓️ 手铐：被叠加的敌人离场，手铐弃置")
