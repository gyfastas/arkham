"""Roland Banks — Guardian Investigator.
能力：在你击败一名敌人后：发现你所在地点的1个线索。（每轮限制1次。）
远古印记：+1（你所在地点每有1个线索，+1）。

实现说明：
- ENEMY_DEFEATED 事件的 ctx 不携带 investigator_id（见 engine/damage.py），
  因此通过 DAMAGE_DEALT 事件记录最后对该敌人造成伤害的调查员来判断"你击败"；
  若无记录（例如被直接伤害击败），回退为检查敌人是否在某个调查员的威胁区中。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class RolandBanks(CardImplementation):
    card_id = "roland_banks"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_round = False
        self._last_damager: dict[str, str] = {}  # enemy instance_id -> investigator_id

    def _get_roland(self, ctx, investigator_id):
        """Return the investigator state iff it is Roland Banks."""
        if investigator_id is None:
            return None
        inv = ctx.game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "roland_banks":
            return None
        return inv

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        """每轮开始时重置限次。"""
        self._used_this_round = False

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.AFTER)
    def track_damager(self, ctx):
        """记录每个敌人最后受到的伤害来源，用于 ENEMY_DEFEATED 归属判断。"""
        if ctx.target and ctx.investigator_id:
            self._last_damager[ctx.target] = ctx.investigator_id

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def discover_clue_on_defeat(self, ctx):
        """在你击败一名敌人后：发现你所在地点的1个线索（每轮限1次）。"""
        if self._used_this_round or not ctx.target:
            return

        # 判断击败者：优先伤害记录，回退威胁区归属
        defeater_id = self._last_damager.pop(ctx.target, None)
        if defeater_id is None:
            for inv_id, inv in ctx.game_state.investigators.items():
                if ctx.target in inv.threat_area:
                    defeater_id = inv_id
                    break
        if defeater_id is None:
            return

        inv = self._get_roland(ctx, defeater_id)
        if inv is None:
            return

        location = ctx.game_state.get_location(inv.location_id)
        if location is None or location.clues <= 0:
            return

        location.clues -= 1
        inv.clues += 1
        self._used_this_round = True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1（你所在地点每有1个线索，+1）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_roland(ctx, ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        clues = location.clues if location else 0
        if clues:
            ctx.modify_amount(clues, "roland_banks_elder_sign")
