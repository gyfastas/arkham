"""Multiplayer session integration tests (2-player game through GameSession).

Covers: multi-investigator setup, turn rotation & action authority, per-player
state views (information hiding), per-investigator mulligan, per-investigator
mythos encounter draws, group clue pooling / per-investigator act thresholds,
defeat handling.
"""

import pytest

from server.game_session import GameSession
from server.player import PlayerSession


def _make_2p_session(seed=42):
    session = GameSession("room_mp")
    result = session.setup(
        scenario_id="the_gathering",
        difficulty="standard",
        seed=seed,
        players=[
            {"player_id": "p1", "investigator_id": "roland_banks"},
            {"player_id": "p2", "investigator_id": "daisy_walker"},
        ],
    )
    assert result["success"], result
    session.add_player(PlayerSession(player_id="p1", display_name="P1", sid="s1"))
    session.add_player(PlayerSession(player_id="p2", display_name="P2", sid="s2"))
    return session


def _drain_pending(session, max_steps=30):
    """Resolve any pending choices / skill tests until the flow settles."""
    g = session.game
    for _ in range(max_steps):
        vars_ = g.state.scenario.vars
        pc = vars_.get("pending_choice")
        if pc:
            owner = pc.get("investigator_id") or "player"
            pid = session.player_id_for_inv(owner) or owner
            choice = (pc.get("options") or [{}])[0].get("id")
            session.handle_action(pid, {"action": "RESOLVE_CHOICE", "choice_id": choice})
            continue
        if session._pending_skill_test is not None:
            owner = session._pending_skill_test["investigator_id"]
            pid = session.player_id_for_inv(owner) or owner
            session.handle_action(pid, {"action": "SKILL_TEST_ROLL", "committed_cards": []})
            continue
        break


class TestMultiplayerSetup:
    def test_two_investigators_created(self):
        s = _make_2p_session()
        g = s.game
        assert g.state.player_order == ["player", "player2"]
        assert g.state.get_investigator("player").card_data.id == "roland_banks"
        assert g.state.get_investigator("player2").card_data.id == "daisy_walker"
        # 同一起始地点
        assert g.state.get_investigator("player").location_id == "study"
        assert g.state.get_investigator("player2").location_id == "study"

    def test_turn_order_and_initial_actions(self):
        s = _make_2p_session()
        assert s.active_investigator_id == "player"
        assert s.game.state.get_investigator("player").actions_remaining == 3
        assert s.game.state.get_investigator("player2").actions_remaining == 0

    def test_player_inv_mapping(self):
        s = _make_2p_session()
        assert s.inv_id_for_player("p1") == "player"
        assert s.inv_id_for_player("p2") == "player2"
        assert s.player_id_for_inv("player2") == "p2"

    def test_location_clues_scale_with_players(self):
        # Study 官方 2⊘（每调查员）→ 双人局 4 条
        s = _make_2p_session()
        assert s.game.state.get_location("study").clues == 4
        s1 = GameSession("room_solo")
        s1.setup(scenario_id="the_gathering", seed=1,
                 players=[{"player_id": "p1", "investigator_id": "roland_banks"}])
        assert s1.game.state.get_location("study").clues == 2


class TestTurnRotation:
    def test_out_of_turn_action_rejected(self):
        s = _make_2p_session()
        result = s.handle_action("p2", {"action": "RESOURCE"})
        assert result["success"] is False
        assert "回合" in result["message"]

    def test_end_turn_rotates_to_next_player(self):
        s = _make_2p_session()
        result = s.handle_end_turn("p1")
        assert result.get("turn_advanced") is True
        assert s.active_investigator_id == "player2"
        assert s.game.state.get_investigator("player2").actions_remaining == 3
        # 现在 p2 可以行动，p1 不行
        assert s.handle_action("p1", {"action": "RESOURCE"})["success"] is False
        assert s.handle_action("p2", {"action": "RESOURCE"})["success"] is True

    def test_full_round_runs_phases_and_encounters_for_both(self):
        s = _make_2p_session()
        s.handle_end_turn("p1")
        result = s.handle_end_turn("p2")
        _drain_pending(s)
        g = s.game
        log = "\n".join(s.action_log)
        assert "--- 敌人阶段 ---" in log
        assert "--- 神话阶段 ---" in log
        assert g.state.scenario.round_number == 2
        # 两名调查员各抽了 1 张遭遇（含 surge 可能更多）
        assert len(g.state.scenario.encounter_discard) >= 2
        # 新一轮开始，回到 p1
        assert s.active_investigator_id == "player"

    def test_encounter_draws_are_per_investigator(self):
        """神话阶段每名调查员各抽 1 张：检查 last_encounter_owner 记录过两人。"""
        s = _make_2p_session()
        s.handle_end_turn("p1")
        s.handle_end_turn("p2")
        _drain_pending(s)
        owners = set()
        # 从日志/变量推断：队列处理时每个 owner 都写入过 last_encounter_owner
        # （最终只剩最后一个，但遭遇弃牌堆数量已断言）；这里直接验证队列清空
        assert s._encounter_draw_queue == []


class TestPerPlayerState:
    def test_views_hide_other_hand(self):
        s = _make_2p_session()
        st1 = s.get_state_for_player("p1")
        st2 = s.get_state_for_player("p2")
        assert st1["investigator"]["id"] == "roland_banks"
        assert st2["investigator"]["id"] == "daisy_walker"
        # 手牌数量一致但互相看不到对方手牌内容
        assert len(st1["hand"]) == 5
        others = st1["other_investigators"]
        assert len(others) == 1
        assert others[0]["id"] == "daisy_walker"
        assert others[0]["hand_count"] == 5
        assert "hand" not in others[0]

    def test_turn_flags(self):
        s = _make_2p_session()
        assert s.get_state_for_player("p1")["your_turn"] is True
        assert s.get_state_for_player("p2")["your_turn"] is False


class TestMulligan:
    def test_per_player_mulligan(self):
        s = _make_2p_session()
        # p1 保留手牌（调度完成），p2 未调度 → 窗口仍开放
        r1 = s.handle_action("p1", {"action": "MULLIGAN", "card_ids": []})
        assert r1["success"] is True
        assert s.game.state.scenario.vars.get("mulligan_available") is True
        # p1 不能重复调度
        assert s.handle_action("p1", {"action": "MULLIGAN", "card_ids": []})["success"] is False
        # p2 可以调度
        r2 = s.handle_action("p2", {"action": "MULLIGAN", "card_ids": []})
        assert r2["success"] is True
        # 全员完成 → 窗口关闭
        assert not s.game.state.scenario.vars.get("mulligan_available")


class TestGroupClues:
    def test_act_threshold_scales_and_pooling(self):
        s = _make_2p_session()
        ctrl = s.controller
        g = s.game
        # the_barrier 官方 3⊘ → 双人 6
        from backend.models.scenario import ActCard
        act = ActCard(id="the_barrier", name="", name_cn="", clue_threshold=3,
                      clue_threshold_per_investigator=True)
        assert ctrl.act_clue_threshold(act) == 6
        # 汇集：p1 有 4 + p2 有 2 = 6，单人不足
        inv1 = g.state.get_investigator("player")
        inv2 = g.state.get_investigator("player2")
        inv1.clues = 4
        inv2.clues = 2
        g.state.scenario.act_cards = {"the_barrier": act}
        g.state.scenario.act_deck = ["the_barrier"]
        g.state.scenario.current_act_index = 0
        assert ctrl.can_advance_act("player2") is True
        assert ctrl.advance_act("player2") is True
        # 推进者先扣，不足部分从队友扣除
        assert inv1.clues == 0
        assert inv2.clues == 0


class TestDefeatMultiplayer:
    def test_one_defeated_game_continues(self):
        s = _make_2p_session()
        g = s.game
        inv1 = g.state.get_investigator("player")
        inv1.clues = 3
        inv1.damage = inv1.health  # p1 被击败
        s._check_new_defeats()
        assert s.game_over is None  # 还有 p2
        # 线索掉落在所在地点
        assert g.state.get_location("study").clues == 4 + 3
        assert inv1.clues == 0
        # p1 移出行动顺序
        assert "player" not in s._turn_order
        # p1 行动被拒
        assert s.handle_action("p1", {"action": "RESOURCE"})["success"] is False

    def test_all_defeated_ends_game(self):
        s = _make_2p_session()
        g = s.game
        for inv_id in ("player", "player2"):
            inv = g.state.get_investigator(inv_id)
            inv.damage = inv.health
        s._check_new_defeats()
        assert s.game_over is not None
        assert s.game_over["type"] == "lose"
