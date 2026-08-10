"""Seeker 内部工具：CardInstance.uses 计数读取/扣减。

数据兼容：部分后期 pack 的数据 JSON 把 uses 键写成了双 s 结尾
（"secretss"/"suppliess"/"resourcess"/"chargess"，fetch 脚本复数化瑕疵），
引擎原样拷贝进 CardInstance.uses（actions._play_asset 与
server._load_player_cards 均不做规范化）。本助手优先读规范键，
回退双 s 键，使卡实现同时兼容生产数据与手工构造的测试数据。
"""

from __future__ import annotations


def uses_key(inst, key: str) -> str:
    """返回实例上实际存在的 uses 键（规范键优先，回退双 s 变体）。"""
    if key in inst.uses:
        return key
    alt = f"{key}s"
    if alt in inst.uses:
        return alt
    return key


def uses_count(inst, key: str) -> int:
    return inst.uses.get(uses_key(inst, key), 0)


def uses_spend(inst, key: str, n: int = 1) -> bool:
    """扣减 n 点 uses；不足则不扣并返回 False。"""
    k = uses_key(inst, key)
    if inst.uses.get(k, 0) < n:
        return False
    inst.uses[k] -= n
    return True
