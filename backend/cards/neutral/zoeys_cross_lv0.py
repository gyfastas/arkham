"""Zoey's Cross — Signature Asset.
[reaction]在一名敌人与你交战后，消耗佐伊的十字架并花费1资源：对该敌人造成1点伤害。

Note: This card's Reaction is now handled by Zoey's investigator ability
in zoey_samaras.py to provide a unified choice interface when engaging.
"""

from backend.cards.base import CardImplementation


class ZoeysCross(CardImplementation):
    card_id = "zoeys_cross_lv0"

    # The reaction ability is handled by the ZoeySamaras class
    # to provide a unified choice interface when an enemy engages.
    # The actual effect execution is in game_session.py _resolve_choice
    # under the "zoey_reactions_on_engage" kind.
