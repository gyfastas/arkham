"""In the Thick of It (Level 0) — Neutral Asset (Permanent).
永久。每牌组限1张。牌组创建时购买。
当你购买身经百战时，承受共计2点肉体和/或精神创伤。然后获得3点经验。

简化说明：
- 永久卡不进入游戏；购买效果实现为公开方法 purchase()，由牌组创建/
  会话层调用：默认 1肉体+1精神创伤（可由参数指定分配），经验+3。
"""

from backend.cards.base import CardImplementation


class InTheThickOfIt(CardImplementation):
    card_id = "in_the_thick_of_it_lv0"

    def purchase(self, game_state, investigator_id: str,
                 physical: int = 1, mental: int = 1) -> bool:
        """购买：承受2点创伤（任意分配），获得3点经验。"""
        if physical < 0 or mental < 0 or physical + mental != 2:
            return False
        inv = game_state.get_investigator(investigator_id)
        card = getattr(inv, "investigator_card", None) if inv else None
        if card is None:
            return False
        card.physical_trauma += physical
        card.mental_trauma += mental
        card.experience += 3
        game_state.log_effect(
            f"🩹 身经百战：承受 {physical} 肉体/{mental} 精神创伤，获得3点经验"
        )
        return True
