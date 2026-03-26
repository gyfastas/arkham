"""Simulation play test for Arkham Horror LCG."""

import json
import random
import requests

BASE_URL = "http://localhost:8907"

def get_state():
    """Get current game state."""
    r = requests.get(f"{BASE_URL}/api/state")
    return r.json()

def do_action(action, **kwargs):
    """Perform an action."""
    data = {"action": action, **kwargs}
    r = requests.post(f"{BASE_URL}/api/action", json=data)
    return r.json()

def simulate_fight_scenario():
    """Simulate a fight scenario."""
    print("=" * 60)
    print("模拟场景: 战斗测试")
    print("=" * 60)

    state = get_state()
    print(f"\n初始状态:")
    print(f"  调查员: 生命 {state['investigator']['health']}/{state['investigator']['sanity']}")
    print(f"  资源: {state['investigator']['resources']}")
    print(f"  手牌: {len(state['hand'])}张")
    print(f"  行动点: {state['investigator']['actions_remaining']}")
    print(f"  敌人: {state['enemies'][0]['name_cn']} (生命 {state['enemies'][0]['health']})")

    # Try fight action
    print("\n执行攻击...")
    enemy = state['enemies'][0]
    result = do_action("FIGHT", enemy_instance_id=enemy['instance_id'])
    print(f"  结果: {result.get('message', 'Unknown')}")

    state = get_state()
    print(f"  敌人剩余生命: {state['enemies'][0]['health'] - state['enemies'][0]['current_damage']}")
    print(f"  剩余行动点: {state['investigator']['actions_remaining']}")

    return state

def simulate_investigate_scenario():
    """Simulate investigation."""
    print("\n" + "=" * 60)
    print("模拟场景: 调查地点")
    print("=" * 60)

    state = get_state()
    print(f"\n当前地点: {state['location']['name_cn']}")
    print(f"  隐藏值: {state['location']['shroud']}")
    print(f"  线索: {state['location']['clues']}")
    print(f"  我的线索: {state['investigator']['clues']}")

    # Try investigate
    print("\n执行调查...")
    result = do_action("INVESTIGATE")
    print(f"  结果: {result.get('message', 'Unknown')}")

    state = get_state()
    print(f"  地点剩余线索: {state['location']['clues']}")
    print(f"  我的线索: {state['investigator']['clues']}")
    print(f"  剩余行动点: {state['investigator']['actions_remaining']}")

    return state

def simulate_evade_scenario():
    """Simulate evasion."""
    print("\n" + "=" * 60)
    print("模拟场景: 闪避敌人")
    print("=" * 60)

    state = get_state()
    if not state['enemies'] or not state['enemies'][0].get('engaged'):
        print("  没有交战的敌人，跳过")
        return state

    enemy = state['enemies'][0]
    print(f"\n尝试闪避: {enemy['name_cn']}")
    print(f"  躲避值: {enemy['evade']}")

    result = do_action("EVADE", enemy_instance_id=enemy['instance_id'])
    print(f"  结果: {result.get('message', 'Unknown')}")

    state = get_state()
    print(f"  敌人横置状态: {state['enemies'][0]['exhausted']}")
    print(f"  剩余行动点: {state['investigator']['actions_remaining']}")

    return state

def simulate_resource_action():
    """Simulate resource action."""
    print("\n" + "=" * 60)
    print("模拟场景: 获取资源")
    print("=" * 60)

    state = get_state()
    initial_resources = state['investigator']['resources']
    print(f"\n当前资源: {initial_resources}")

    result = do_action("RESOURCE")
    print(f"  结果: {result.get('message', 'Unknown')}")

    state = get_state()
    print(f"  新资源: {state['investigator']['resources']}")
    print(f"  剩余行动点: {state['investigator']['actions_remaining']}")

    return state

def simulate_full_round():
    """Simulate a full round of actions."""
    print("\n" + "=" * 60)
    print("模拟场景: 完整回合")
    print("=" * 60)

    state = get_state()
    print(f"\n回合 {state['round']} - {state['phase']} 阶段")
    print(f"行动点: {state['investigator']['actions_remaining']}")

    # Use all 3 actions
    actions_taken = 0

    while state['investigator']['actions_remaining'] > 0 and actions_taken < 3:
        actions_taken += 1
        print(f"\n  行动 {actions_taken}:")

        # Random action based on state
        if state['enemies'] and state['enemies'][0].get('engaged') and not state['enemies'][0].get('exhausted'):
            # Fight if enemy engaged
            result = do_action("FIGHT", enemy_instance_id=state['enemies'][0]['instance_id'])
            print(f"    攻击 -> {result.get('message', 'Unknown')}")
        elif state['location']['clues'] > 0:
            # Investigate if clues available
            result = do_action("INVESTIGATE")
            print(f"    调查 -> {result.get('message', 'Unknown')}")
        else:
            # Resource
            result = do_action("RESOURCE")
            print(f"    资源 -> {result.get('message', 'Unknown')}")

        state = get_state()
        if state['investigator'].get('defeated'):
            print("  调查员被击败!")
            break

    print(f"\n回合结束:")
    print(f"  最终资源: {state['investigator']['resources']}")
    print(f"  手牌数: {state['investigator']['hand_count']}")
    print(f"  日志: {state['log'][-3:] if len(state['log']) > 3 else state['log']}")

    return state

def check_ui_elements():
    """Check key UI elements are present in state."""
    print("\n" + "=" * 60)
    print("UI元素检查")
    print("=" * 60)

    state = get_state()

    checks = [
        ("调查员状态", 'investigator' in state),
        ("地点信息", 'location' in state),
        ("手牌数据", 'hand' in state and len(state['hand']) >= 0),
        ("敌人列表", 'enemies' in state),
        ("阶段信息", 'phase' in state),
        ("回合数", 'round' in state),
        ("日志", 'log' in state and len(state['log']) > 0),
        ("行动点", state['investigator'].get('actions_remaining', 0) > 0),
    ]

    print()
    for name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")

    return all(p for _, p in checks)

def main():
    """Run all simulation tests."""
    print("\n" + "=" * 60)
    print("Arkham Horror LCG - 模拟游玩测试")
    print("=" * 60)

    try:
        # Check server is running
        state = get_state()
        print(f"\n✅ 服务器连接成功")
        print(f"   游戏ID: 测试场景")

        # Run tests
        results = []

        # UI check
        results.append(("UI元素检查", check_ui_elements()))

        # Individual scenarios
        try:
            simulate_fight_scenario()
            results.append(("战斗场景", True))
        except Exception as e:
            print(f"战斗场景失败: {e}")
            results.append(("战斗场景", False))

        try:
            simulate_resource_action()
            results.append(("资源获取", True))
        except Exception as e:
            print(f"资源获取失败: {e}")
            results.append(("资源获取", False))

        try:
            simulate_investigate_scenario()
            results.append(("调查场景", True))
        except Exception as e:
            print(f"调查场景失败: {e}")
            results.append(("调查场景", False))

        # Summary
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        for name, passed in results:
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"  {status}: {name}")

        passed_count = sum(1 for _, p in results if p)
        total_count = len(results)
        print(f"\n总计: {passed_count}/{total_count} 通过")

        return passed_count == total_count

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器 (端口 8907)")
        print("   请先运行: python3 frontend/server.py")
        return False
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
