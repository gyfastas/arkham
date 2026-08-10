"""Aquinnah (Level 1) — Survivor Asset, Ally slot.
[reaction] When an enemy attacks you, exhaust Aquinnah and deal 1 horror to her:
Deal that enemy's damage to another enemy at your location, instead.
(You still take horror dealt by the attack.)

简化说明：
- 触发挂 DAMAGE_ASSIGNED（调查员被分配伤害、来源为敌人）；官方仅限"敌人攻击"，
  引擎中反击/警觉/借机攻击走同一流程，当前不加区分。
- 目标自动选你所在地点的第一个其他敌人（lv3 默认攻击者本身），无 UI 选择。
- 引擎在事件发出前已完成盟友分摊、且事件后不读取 amount，
  因此"取消伤害"通过预先扣减调查员伤害近似（若本次伤害已被盟友分摊，
  会多回复相应点数；罕见边界，从简）。
- 卡牌代码无法访问引擎的 DamageEngine/EventBus，对敌人的伤害击败结算与
  安奎娜自身恐惧击败结算为内联复制（不发 ENEMY_DEFEATED/ASSET_DEFEATED 事件）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import CardType, GameEvent, TimingPriority


class AquinnahLv1(CardImplementation):
    card_id = "aquinnah_lv1"
    # lv3：目标可以是你所在地点的任意敌人（含攻击者本身），默认选攻击者
    target_any_enemy = False

    def _enemies_at_location(self, game_state, location_id):
        """所在地点的敌人实例 id：未交战的 + 当地点各调查员威胁区中交战的。"""
        result = []
        loc = game_state.get_location(location_id)
        if loc is not None:
            result.extend(loc.enemies)
        for inv in game_state.investigators.values():
            if inv.location_id != location_id:
                continue
            for eid in inv.threat_area:
                if eid not in result:
                    result.append(eid)
        return result

    def _pick_target(self, ctx, inv, attacker_iid):
        candidates = self._enemies_at_location(ctx.game_state, inv.location_id)
        if self.target_any_enemy:
            # lv3：任意敌人，默认攻击者本身（最常见选择）
            if attacker_iid in candidates:
                return attacker_iid
            return candidates[0] if candidates else None
        for eid in candidates:
            if eid != attacker_iid:
                return eid
        return None

    def _defeat_self(self, ctx, inv, inst):
        """安奎娜恐惧达到理智上限时被击败（内联复制引擎资产击败流程）。"""
        vacate_asset_slots(ctx.game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)
        ctx.game_state.log_effect("💀 安奎娜恐惧达到上限，被击败")

    def _deal_to_enemy(self, ctx, enemy_iid, amount, inv):
        """对敌人造成 amount 点伤害，达到生命上限则击败（内联复制引擎流程，
        不发 ENEMY_DEFEATED 事件——卡牌代码访问不到 EventBus）。"""
        enemy = ctx.game_state.get_card_instance(enemy_iid)
        if enemy is None or amount <= 0:
            return
        enemy.damage += amount
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return
        if enemy_data.enemy_health and enemy.damage >= enemy_data.enemy_health:
            if getattr(enemy_data, "victory", 0):
                ctx.game_state.scenario.victory_display.append(enemy.card_id)
            ctx.game_state.cards_in_play.pop(enemy_iid, None)
            for other in ctx.game_state.investigators.values():
                if enemy_iid in other.threat_area:
                    other.threat_area.remove(enemy_iid)
            for loc in ctx.game_state.locations.values():
                if enemy_iid in loc.enemies:
                    loc.enemies.remove(enemy_iid)
            ctx.game_state.scenario.encounter_discard.append(enemy.card_id)
            ctx.game_state.log_effect(
                f"⚔️ 安奎娜：【{ctx.game_state.card_name(enemy.card_id)}】被转移的伤害击败")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def redirect_damage(self, ctx):
        """敌人攻击你时：横置安奎娜并对她造成1恐惧，把该敌人的伤害改对目标敌人造成。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        if (ctx.amount or 0) < 1:
            return
        attacker = ctx.game_state.get_card_instance(ctx.source) if ctx.source else None
        if attacker is None:
            return
        attacker_data = ctx.game_state.get_card_data(attacker.card_id)
        if attacker_data is None or attacker_data.type != CardType.ENEMY:
            return

        target_iid = self._pick_target(ctx, inv, attacker.instance_id)
        if target_iid is None:
            return

        # 费用：横置安奎娜 + 对她造成1点恐惧
        inst.exhausted = True
        inst.horror += 1

        # 取消调查员承受的伤害部分（近似，见模块 docstring）；恐惧部分照常承受
        inv.damage -= ctx.amount

        # 把攻击敌人的伤害值改对目标敌人造成
        redirect = attacker_data.enemy_damage or 0
        target = ctx.game_state.get_card_instance(target_iid)
        target_name = ctx.game_state.card_name(target.card_id) if target else target_iid
        self._deal_to_enemy(ctx, target_iid, redirect, inv)

        # 安奎娜恐惧达到上限则被击败
        inst_data = ctx.game_state.get_card_data(self.card_id)
        if inst_data is not None and inst_data.sanity is not None \
                and inst.horror >= inst_data.sanity:
            self._defeat_self(ctx, inv, inst)

        ctx.extra["aquinnah_redirected"] = redirect
        ctx.extra["aquinnah_target"] = target_iid
        ctx.game_state.log_effect(
            f"🛡️ 安奎娜：横置并承受1恐惧，将{redirect}点伤害转移给【{target_name}】")
