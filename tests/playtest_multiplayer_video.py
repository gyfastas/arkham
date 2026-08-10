"""Two-player multiplayer playtest recorder.

Two browser contexts (P1/P2) join the same room and play cooperatively via the
real UI. Both screens are recorded (webm) plus screenshots.

Usage:
    python3 tests/playtest_multiplayer_video.py [--port 8910] [--out /tmp/arkham_mp]

Requires: server running, client built, playwright chromium installed.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 1440, "height": 900}
SETTLE_MS = 1500


class MpPlayer:
    def __init__(self, page, name: str, out: Path):
        self.page = page
        self.name = name
        self.out = out
        self.step = 0

    def shot(self, tag: str):
        self.step += 1
        self.page.screenshot(path=str(self.out / f"{self.name}_{self.step:02d}_{tag}.png"))

    def settle(self, ms: int = SETTLE_MS):
        self.page.wait_for_timeout(ms)

    def dismiss_overlays(self):
        for sel in ("text=继续", "text=确认", "text=知道了", "text=保留手牌"):
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=400):
                    btn.click()
                    self.settle(500)
            except Exception:
                pass
        # 技能检定轮盘：投掷 → 确认
        try:
            roll = self.page.locator(".skill-overlay .overlay-actions button.roll-button:not([disabled])").first
            if roll.is_visible(timeout=400):
                roll.click()
                self.settle(3600)
        except Exception:
            pass
        try:
            confirm = self.page.locator(".skill-overlay button.confirm-button").first
            if confirm.is_visible(timeout=400):
                confirm.click()
                self.settle(600)
        except Exception:
            pass

    def my_turn(self) -> bool:
        try:
            badge = self.page.locator("text=你的回合").first
            return badge.is_visible(timeout=800)
        except Exception:
            return False

    def click_action(self, label: str) -> bool:
        try:
            btn = self.page.locator(".action-bar button, .overlay-actions button", has_text=label).first
            if btn.is_visible(timeout=800) and btn.is_enabled():
                btn.click()
                self.settle()
                self.dismiss_overlays()
                return True
        except Exception:
            pass
        return False

    def play_first_asset(self) -> bool:
        try:
            card = self.page.locator(".hand-area .hand-card").first
            if not card.is_visible(timeout=600):
                return False
            card.click()
            self.settle(400)
            play = self.page.locator("button", has_text="打出").first
            if play.is_visible(timeout=600) and play.is_enabled():
                play.click()
                self.settle()
                return True
        except Exception:
            pass
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8910)
    ap.add_argument("--out", default="/tmp/arkham_mp")
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    base = f"http://localhost:{args.port}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx1 = browser.new_context(viewport=VIEWPORT, record_video_dir=str(out / "v1"), record_video_size=VIEWPORT)
        ctx2 = browser.new_context(viewport=VIEWPORT, record_video_dir=str(out / "v2"), record_video_size=VIEWPORT)
        p1 = MpPlayer(ctx1.new_page(), "p1", out)
        p2 = MpPlayer(ctx2.new_page(), "p2", out)

        try:
            # --- 大厅：P1 建房，P2 按 ID 加入 ---
            print("== 大厅 ==")
            p1.page.goto(f"{base}/#/quick?mode=multi")
            p1.page.wait_for_load_state("networkidle")
            p1.settle(1000)
            p1.page.locator("button", has_text="创建房间").first.click()
            p1.settle(1500)
            room_id = p1.page.locator("code.room-id").inner_text(timeout=5000).strip()
            print(f"  room_id={room_id}")
            assert room_id, "未能获取房间 ID"

            p2.page.goto(f"{base}/#/quick?mode=multi")
            p2.page.wait_for_load_state("networkidle")
            p2.settle(800)
            p2.page.locator("input.room-id-input").first.fill(room_id)
            p2.page.locator("button", has_text="加入").first.click()
            p2.settle(1500)
            p1.shot("lobby_seats")
            p2.shot("lobby_seats")

            # --- 选剧本 + 调查员并准备 ---
            for pp in (p1, p2):
                pp.page.locator(".col-scenario .list-item", has_text="谢幕").first.click()
                pp.settle(400)
            p1.page.locator(".investigator-item", has_text="马克").first.click()
            p1.settle(800)
            p1.page.locator("button.btn-primary", has_text="准备").first.click()
            p1.settle(800)

            p2.page.locator(".investigator-item", has_text="潘明").first.click()
            p2.settle(800)
            p2.page.locator("button.btn-primary", has_text="准备").first.click()

            # 等开局
            p1.page.wait_for_selector(".game-view", timeout=15000)
            p2.page.wait_for_selector(".game-view", timeout=15000)
            p1.settle(2000)
            p1.shot("game_start")
            p2.shot("game_start")
            print("== 游戏开始 ==")

            # --- 轮流行动 ---
            players = [p1, p2]
            for rnd in range(1, args.rounds + 1):
                print(f"== 第 {rnd} 轮 ==")
                for who in players:
                    p1.dismiss_overlays()
                    p2.dismiss_overlays()
                    if not who.my_turn():
                        who.settle(1500)
                    if not who.my_turn():
                        print(f"  {who.name} 尚无回合，跳过")
                        continue
                    print(f"  {who.name} 行动中")
                    who.play_first_asset()
                    who.click_action("调查")
                    who.click_action("资源")
                    who.shot("turn")
                    who.click_action("结束回合")
                    who.settle(1800)
                    p1.dismiss_overlays()
                    p2.dismiss_overlays()
                p1.shot(f"round{rnd}_end")
                p2.shot(f"round{rnd}_end")

        finally:
            ctx1.close()
            ctx2.close()
            browser.close()

    print(f"\n✅ 完成。视频: {out}/v1, {out}/v2；截图: {out}")


if __name__ == "__main__":
    main()
