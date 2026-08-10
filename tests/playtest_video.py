"""Playtest video recorder for Arkham Horror LCG (Vue 3 client + Socket.IO server).

Drives the real UI with simulated clicks and records a .webm video via Playwright.

Usage:
    python3 tests/playtest_video.py [--port 8910] [--out /tmp/arkham_playtest]

Requires: server running (python3 server/main.py --port 8910), client built.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 1440, "height": 900}
SETTLE_MS = 1600          # wait after each action for socket update + animations
OVERLAY_CHECK_MS = 400


def _card_display_name(text: str) -> str:
    """手牌 DOM 文本中取卡名：第一行含 CJK 且非类型标签的行。"""
    for line in text.split("\n"):
        line = line.strip()
        if line and any("\u4e00" <= ch <= "\u9fff" for ch in line) \
                and line not in ("支援", "事件", "技能"):
            return line
    return text.split("\n")[0] if text else "?"


class Playtest:
    def __init__(self, page, out: Path):
        self.page = page
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.step = 0

    # ---------- helpers ----------
    def shot(self, name: str):
        self.step += 1
        try:
            diag = self.page.evaluate(
                "() => ({y: window.scrollY, "
                "locs: document.querySelectorAll('.location-node').length, "
                "enemies: document.querySelectorAll('.enemy-card').length})"
            )
            if diag["y"] != 0 or diag["locs"] == 0:
                print(f"  ⚠️ diag: scrollY={diag['y']} locations={diag['locs']} enemies={diag['enemies']}")
                self.page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass
        self.page.screenshot(path=str(self.out / f"{self.step:02d}_{name}.png"))
        print(f"  📸 {self.step:02d}_{name}.png")

    def settle(self, ms: int = SETTLE_MS):
        self.page.wait_for_timeout(ms)

    def dismiss_overlays(self) -> bool:
        """Close encounter popup / resolve choice modal if present. Returns True if any handled."""
        handled = False
        try:
            btn = self.page.locator(".encounter-overlay .dismiss-btn")
            if btn.count() and btn.first.is_visible():
                btn.first.click()
                handled = True
                self.settle(800)
        except Exception:
            pass
        try:
            opts = self.page.locator(".modal-overlay .option-btn")
            if opts.count() and opts.first.is_visible():
                label = opts.first.inner_text()
                print(f"  🎯 选择弹窗 → 选第一项: {label}")
                opts.first.click()
                handled = True
                self.settle(1000)
        except Exception:
            pass
        # 技能检定轮盘：投掷（等待转动动画）→ 确认
        try:
            roll = self.page.locator(".skill-overlay .overlay-actions button.roll-button:not([disabled])")
            if roll.count() and roll.first.is_visible():
                roll.first.click()
                self.settle(3600)
                handled = True
        except Exception:
            pass
        try:
            confirm = self.page.locator(".skill-overlay button.confirm-button")
            if confirm.count() and confirm.first.is_visible():
                confirm.first.click()
                handled = True
                self.settle(800)
        except Exception:
            pass
        # 开局调度：保留手牌
        try:
            keep = self.page.locator("button:has-text('保留手牌')")
            if keep.count() and keep.first.is_visible():
                keep.first.click()
                handled = True
                self.settle(600)
        except Exception:
            pass
        return handled

    def click_action(self, label: str) -> bool:
        """Click an action bar button by its label text."""
        try:
            btn = self.page.locator(f".action-btn:has-text('{label}')")
            if btn.count() and btn.first.is_visible():
                btn.first.click()
                self.settle()
                self.dismiss_overlays()
                return True
        except Exception as e:
            print(f"  ⚠️ action {label} 失败: {e}")
        return False

    def play_card_by_name(self, keyword: str) -> bool:
        """Click a playable hand card whose text contains keyword."""
        try:
            cards = self.page.locator(".hand-card-wrapper:not(.disallowed)")
            for i in range(cards.count()):
                c = cards.nth(i)
                if keyword in c.inner_text():
                    c.click()
                    self.settle()
                    self.dismiss_overlays()
                    return True
        except Exception as e:
            print(f"  ⚠️ 打牌 {keyword} 失败: {e}")
        return False

    def play_first_asset(self) -> bool:
        """Play the first allowed asset (支援) hand card."""
        try:
            cards = self.page.locator(".hand-card-wrapper:not(.disallowed)")
            for i in range(cards.count()):
                c = cards.nth(i)
                # 只打支援卡；技能卡不能打出，事件卡留给实战时机
                ctype = c.locator(".card-type").inner_text().strip()
                if ctype != "支援":
                    continue
                name = c.locator(".card-name").inner_text().strip()
                print(f"  🃏 打出: {name}")
                c.click()
                self.settle()
                self.dismiss_overlays()
                return True
        except Exception as e:
            print(f"  ⚠️ 打牌失败: {e}")
        return False

    def move_to_connected(self) -> bool:
        """Click the first location node marked as movable."""
        try:
            node = self.page.locator(".location-node:has(.move-badge)")
            if node.count() and node.first.is_visible():
                name = node.first.locator(".loc-name").inner_text()
                print(f"  🚶 移动到: {name}")
                node.first.click()
                self.settle()
                self.dismiss_overlays()
                return True
        except Exception as e:
            print(f"  ⚠️ 移动失败: {e}")
        return False

    def has_enemies(self) -> bool:
        try:
            return self.page.locator(".enemy-card").count() > 0
        except Exception:
            return False

    def engaged_enemies(self) -> bool:
        try:
            return self.page.locator(".enemy-card .engaged-badge").count() > 0
        except Exception:
            return False

    def actions_remaining(self) -> int:
        try:
            text = self.page.locator(".action-count").inner_text()  # "行动: N"
            return int(text.split(":")[-1].strip())
        except Exception:
            return 0

    # ---------- script ----------
    def run(self, base_url: str, scenario: str = "聚集", investigator: str = "佐伊"):
        page = self.page
        print("== 大厅 ==")
        page.goto(f"{base_url}/#/quick")
        page.wait_for_load_state("networkidle")
        self.settle(1200)
        self.shot("lobby")

        # 选剧本
        page.locator(".col-scenario .list-item", has_text=scenario).first.click()
        self.settle(600)
        # 选调查员
        page.locator(".investigator-item", has_text=investigator).first.click()
        self.settle(1200)  # 等调查员详情加载
        self.shot("select_investigator")

        # 开始游戏
        page.locator("button.btn-primary", has_text="开始游戏").click()
        print("== 游戏开始，等待状态 ==")
        page.wait_for_selector(".game-view", timeout=15000)
        self.settle(2500)
        # 开局调度：显式等待并保留手牌（弹窗出现时机有竞争，dismiss 可能漏掉）
        try:
            keep = page.locator("button", has_text="保留手牌").first
            keep.wait_for(state="visible", timeout=8000)
            keep.click()
            self.settle(1000)
        except Exception:
            pass
        self.dismiss_overlays()
        self.shot("game_start")

        # ---- 回合 1 ----
        print("== 回合 1：备战 ==")
        for weapon in ("弯刀", "大砍刀", "自动手枪", "警棍", "柯尔特", "弯刀", "铁铲", "指虎"):
            if self.play_card_by_name(weapon):
                print(f"  ⚔️ 装备武器: {weapon}")
                break
        self.shot("weapon")
        self.play_first_asset()
        self.shot("asset")
        self.move_to_connected()
        self.shot("moved")
        self.click_action("结束回合")
        self.settle(2000)
        self.dismiss_overlays()
        self.shot("round1_end")

        # ---- 回合 2-6：自适应 ----
        for rnd in range(2, 7):
            print(f"== 回合 {rnd} ==")
            self.dismiss_overlays()

            # 有敌人：交战 → 佐伊反应弹窗 → 战斗到底
            if self.has_enemies():
                if not self.engaged_enemies():
                    self.click_action("交战")
                    self.settle(800)
                    self.dismiss_overlays()  # 佐伊交战反应选择
                    self.shot("zoey_reaction")
                fights = 0
                while fights < 5 and self.actions_remaining() > 0 and self.has_enemies():
                    if not self.click_action("战斗"):
                        break
                    fights += 1
                    self.shot("fight")
            else:
                # 无敌人：发展+调查
                self.play_first_asset()
                if self.actions_remaining() > 0:
                    self.click_action("调查")
                    self.shot("investigate")
                if self.actions_remaining() > 0:
                    self.click_action("调查")
                if self.actions_remaining() > 0:
                    self.move_to_connected() or self.click_action("资源")
                    self.shot("move_or_resource")

            self.click_action("结束回合")
            self.settle(2200)
            self.dismiss_overlays()
            self.shot(f"round{rnd}_end")

        self.shot("final")
        print("== 试玩结束 ==")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8910)
    ap.add_argument("--out", default="/tmp/arkham_playtest")
    ap.add_argument("--scenario", default="聚集")
    ap.add_argument("--investigator", default="佐伊")
    args = ap.parse_args()

    out = Path(args.out)
    video_dir = out / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(video_dir),
            record_video_size=VIEWPORT,
        )
        page = ctx.new_page()
        page.on("pageerror", lambda e: print(f"  🔥 PAGE ERROR: {e}"))
        page.on("console", lambda m: print(f"  🖥️ console.{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
        try:
            Playtest(page, out).run(f"http://localhost:{args.port}", scenario=args.scenario, investigator=args.investigator)
        finally:
            ctx.close()  # 触发视频落盘
            browser.close()

    videos = list(video_dir.glob("*.webm"))
    print(f"\n✅ 完成。视频: {[str(v) for v in videos]}")
    print(f"   截图: {out}")


if __name__ == "__main__":
    main()
