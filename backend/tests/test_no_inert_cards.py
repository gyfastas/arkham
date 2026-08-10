"""Meta-test: no card implementation may be inert.

Regression guard for the class of bug where a card file exists with a
`card_id` but its handlers are empty (`pass`) or it has no handlers at all —
the card appears "implemented" (registered) but silently does nothing in
real games (e.g. Shortcut before 2026-07-17).

Rules enforced:
1. Every @on_event handler must have a non-trivial body (not just `pass`).
2. Every registered card implementation must expose at least one
   @on_event handler or one public action method.
"""

import ast
from pathlib import Path

import pytest

from backend.cards.registry import CardRegistry

CARDS_ROOT = Path(__file__).resolve().parents[1] / "cards"

# Public methods that count as a real effect entry point
_ACTION_PREFIXES = ("activate", "resolve", "use", "spend", "attach",
                    "trade", "choose", "setup", "play_top", "game_end_penalty")
_ACTION_EXACT = {"is_disc", "pay_to_draw", "bind_chaos_bag"}

# card_ids that are intentionally inert because their effect is handled
# elsewhere (documented in the file's docstring)
_ALLOWED_INERT = {
    "zoeys_cross_lv0",      # effect unified into zoey_samaras.py choice flow
    "disc_of_itzamna_lv2",  # spawn interception lives in official_core spawn hook
    "unexpected_courage_lv0",  # pure skill-icon card: works via commit, no effect text
    # 官方卡面无文字能力：asset 自带4生命/理智用于承伤/承恐，soak 分配
    # 通道（get_ally_soak_targets 仅限盟友）暂不支持非盟友 asset，见卡内注释。
    "bulletproof_vest_lv3",
    "elder_sign_amulet_lv3",
    "leather_coat_lv0",       # 同上：health:2 承伤
    "cherished_keepsake_lv0",  # 同上：官方卡面无文字能力，sanity:2 承恐
}


def _handler_funcs(tree: ast.AST) -> tuple[list[ast.FunctionDef], list[ast.FunctionDef]]:
    """Return (working_handlers, stub_handlers) for a module AST."""
    working, stubs = [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        is_handler = any(
            (isinstance(d, ast.Call) and getattr(d.func, "id", "") == "on_event")
            or (isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "on_event")
            or getattr(d, "id", "") == "on_event"
            or getattr(d, "attr", "") == "on_event"
            for d in node.decorator_list
        )
        if not is_handler:
            continue
        body = [n for n in node.body
                if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        (stubs if (len(body) == 1 and isinstance(body[0], ast.Pass)) else working).append(node)
    return working, stubs


def _public_action_methods(tree: ast.AST) -> list[str]:
    """Public methods that may serve as an effect entry point.

    Any non-underscore method counts (activate/resolve/spend/boost/...),
    except lifecycle helpers which every implementation has.
    """
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            if node.name in ("__init__", "register", "unregister"):
                continue
            names.append(node.name)
    return names


def _card_files() -> list[Path]:
    return sorted(
        p for p in CARDS_ROOT.rglob("*.py")
        if p.name not in ("__init__.py", "base.py", "registry.py", "_shared.py")
        and "__pycache__" not in p.parts
    )


class TestNoInertHandlers:
    def test_no_stub_event_handlers(self):
        """No @on_event handler may be a bare `pass`."""
        offenders = []
        for path in _card_files():
            _, stubs = _handler_funcs(ast.parse(path.read_text(encoding="utf-8")))
            for fn in stubs:
                offenders.append(f"{path.relative_to(CARDS_ROOT)}::{fn.name}")
        assert not offenders, f"空壳 handler（只有 pass）: {offenders}"

    def test_every_registered_card_has_effect_entry(self):
        """Every registered card must have ≥1 handler or public action method
        (collected across the whole MRO so level-2/3 subclasses count)."""
        import inspect

        from backend.cards.base import CardImplementation

        registry = CardRegistry()
        registry.discover_cards()
        inert = []
        for card_id in registry.registered_cards:
            if card_id in _ALLOWED_INERT:
                continue
            impl_class = registry.get_implementation(card_id)
            working_total, action_total = [], []
            for klass in impl_class.__mro__:
                if klass in (object, CardImplementation):
                    continue
                try:
                    path = Path(inspect.getfile(klass))
                except TypeError:
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"))
                working, _ = _handler_funcs(tree)
                working_total += working
                action_total += _public_action_methods(tree)
            if not working_total and not action_total:
                inert.append(card_id)
        assert not inert, f"注册但完全无效果的卡: {inert}"


PLAYER_CARDS_ROOT = Path(__file__).resolve().parents[2] / "data" / "player_cards"

# Data-only cards with no effect of their own (placeholder entries)
_NO_IMPL_WHITELIST = {
    "random_basic_weakness",  # 占位卡：开局时替换为一张随机基础弱点
}


class TestDataCoverage:
    def test_every_player_card_data_has_implementation(self):
        """Every data/player_cards JSON must have a registered implementation.

        Guards the opposite direction of the inert-card tests: a card that
        exists in the deck-building pool but silently has no effect in game.
        """
        import json

        registry = CardRegistry()
        registry.discover_cards()
        missing = []
        for path in sorted(PLAYER_CARDS_ROOT.rglob("*.json")):
            if path.name == "schema.json":
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            card_id = data.get("id")
            if not card_id or card_id in _NO_IMPL_WHITELIST:
                continue
            if registry.get_implementation(card_id) is None:
                missing.append(f"{path.parent.name}/{card_id}")
        assert not missing, f"有数据但无实现的卡: {missing}"
