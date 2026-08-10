"""Book of Shadows (Level 1) — Mystic Asset, Hand slot. (03154)
[action] 横置影之书并花费1资源：给你控制的一张[[法术]]支援卡添加1个充能。

简化说明：
- 无奥秘槽加成（那是 lv3 的效果）：覆盖 lv3 的 enter_play/leaves_play 为空实现。
- 添加充能的目标默认为你控制的第一张带充能的法术支援卡（无选择 UI）；
  调用方可传 target_instance_id 指定目标。
"""

from backend.cards.mystic.book_of_shadows_lv3 import BookOfShadows


class BookOfShadowsLv1(BookOfShadows):
    card_id = "book_of_shadows_lv1"
    activations = [{
        "id": "add_charge",
        "label": "横置+1资源：给你控制的一张法术支援加1充能",
        "method": "activate",
        "actions": 1,
    }]

    # lv1 没有"额外奥秘槽位"：覆盖 lv3 的进场/离场处理器（不带装饰器即不注册）
    def enter_play(self, ctx):
        pass

    def leaves_play(self, ctx):
        pass

    def activate(self, game_state, investigator_id: str,
                 target_instance_id: str | None = None) -> bool:
        """横置并花费1资源：给你控制的一张法术支援卡添加1个充能。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or inv.resources < 1:
            return False
        if not super().activate(game_state, investigator_id, target_instance_id):
            return False
        inv.resources -= 1
        return True
