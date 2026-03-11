/** Centralized animation manager for game events.
 *
 * Processes server event sequences and plays Phaser tweens/particles
 * in order before updating to the final state.
 */

import Phaser from 'phaser'
import type { GameEventData } from '../state/types'

/** Duration presets in ms */
const DUR = {
  FAST: 200,
  NORMAL: 400,
  SLOW: 600,
  TOKEN: 800,
} as const

export class AnimationManager {
  private scene: Phaser.Scene
  private overlay: Phaser.GameObjects.Container
  private busy = false

  constructor(scene: Phaser.Scene) {
    this.scene = scene
    this.overlay = scene.add.container(0, 0).setDepth(50)
  }

  get isBusy(): boolean { return this.busy }

  /** Play a sequence of game events with animations. */
  async playEvents(events: GameEventData[]): Promise<void> {
    if (events.length === 0) return
    this.busy = true
    for (const event of events) {
      await this.animateEvent(event)
    }
    this.busy = false
  }

  private async animateEvent(event: GameEventData): Promise<void> {
    switch (event.event) {
      case 'CHAOS_TOKEN_REVEALED':
        await this.animateChaosToken(event.chaos_token || '?')
        break
      case 'SKILL_TEST_SUCCESSFUL':
        await this.animateTestResult(true)
        break
      case 'SKILL_TEST_FAILED':
        await this.animateTestResult(false)
        break
      case 'DAMAGE_DEALT':
        await this.animateDamage(event.amount || 0, event.target || '')
        break
      case 'HORROR_DEALT':
        await this.animateHorror(event.amount || 0)
        break
      case 'CARD_PLAYED':
      case 'CARD_ENTERS_PLAY':
        await this.animateCardPlay(event.card_id)
        break
      case 'CARD_DRAWN':
        await this.animateCardDraw()
        break
      case 'ENEMY_DEFEATED':
        await this.animateEnemyDefeated()
        break
      case 'CLUE_DISCOVERED':
        await this.animateClueDiscovered(event.amount || 1)
        break
      case 'ENEMY_ENGAGED':
        await this.animateEnemyEngaged()
        break
      case 'ENEMY_ATTACKS':
        await this.animateEnemyAttack()
        break
      case 'RESOURCES_GAINED':
        await this.animateResourceGain(event.amount || 1)
        break
      case 'MOVE_ACTION_INITIATED':
        await this.animateMovement(event.location_id)
        break
      default:
        // Skip unknown events without delay
        break
    }
  }

  // ===== Chaos Token =====
  private animateChaosToken(token: string): Promise<void> {
    const { width, height } = this.scene.scale
    const cx = width / 2
    const cy = height / 2

    // Token label mapping
    const tokenLabels: Record<string, string> = {
      '+1': '+1', '0': '0', '-1': '-1', '-2': '-2', '-3': '-3',
      '-4': '-4', '-5': '-5', '-6': '-6', '-7': '-7', '-8': '-8',
      skull: '💀', cultist: '🔮', tablet: '📜', elder_thing: '👁',
      auto_fail: '❌', elder_sign: '⭐', bless: '✨', curse: '💀',
    }
    const label = tokenLabels[token] || token

    // Background circle
    const circle = this.scene.add.circle(cx, cy - 100, 0, 0x2a2a4e, 0.95)
      .setStrokeStyle(3, 0xc0a060).setDepth(55)
    const text = this.scene.add.text(cx, cy - 100, label, {
      fontSize: '36px', color: '#ffffff', fontFamily: 'serif',
    }).setOrigin(0.5).setAlpha(0).setDepth(56)

    this.overlay.add(circle)
    this.overlay.add(text)

    return new Promise(resolve => {
      // Expand circle + fade in text
      this.scene.tweens.add({
        targets: circle,
        radius: 45,
        y: cy,
        duration: DUR.TOKEN / 2,
        ease: 'Back.easeOut',
      })
      this.scene.tweens.add({
        targets: text,
        alpha: 1,
        y: cy,
        duration: DUR.TOKEN / 2,
        ease: 'Back.easeOut',
      })

      // Hold, then shrink and fade
      this.scene.time.delayedCall(DUR.TOKEN, () => {
        this.scene.tweens.add({
          targets: [circle, text],
          alpha: 0,
          scaleX: 0.3,
          scaleY: 0.3,
          duration: DUR.NORMAL,
          ease: 'Power2',
          onComplete: () => {
            circle.destroy()
            text.destroy()
            resolve()
          },
        })
      })
    })
  }

  // ===== Skill Test Result =====
  private animateTestResult(success: boolean): Promise<void> {
    const { width, height } = this.scene.scale
    const symbol = success ? '✓' : '✗'
    const color = success ? '#44ff44' : '#ff4444'
    const bgColor = success ? 0x004400 : 0x440000

    const flash = this.scene.add.rectangle(width / 2, height / 2, width, height, bgColor, 0)
      .setDepth(54)
    const text = this.scene.add.text(width / 2, height / 2, symbol, {
      fontSize: '72px', color, fontFamily: 'serif',
    }).setOrigin(0.5).setAlpha(0).setScale(2).setDepth(56)

    this.overlay.add(flash)
    this.overlay.add(text)

    return new Promise(resolve => {
      // Flash background
      this.scene.tweens.add({
        targets: flash,
        alpha: 0.3,
        duration: DUR.FAST,
        yoyo: true,
      })
      // Pop-in symbol
      this.scene.tweens.add({
        targets: text,
        alpha: 1,
        scaleX: 1,
        scaleY: 1,
        duration: DUR.NORMAL,
        ease: 'Back.easeOut',
        onComplete: () => {
          this.scene.time.delayedCall(DUR.NORMAL, () => {
            this.scene.tweens.add({
              targets: text,
              alpha: 0,
              y: text.y - 40,
              duration: DUR.FAST,
              onComplete: () => {
                flash.destroy()
                text.destroy()
                resolve()
              },
            })
          })
        },
      })
    })
  }

  // ===== Damage =====
  private animateDamage(amount: number, _target: string): Promise<void> {
    const { width, height } = this.scene.scale
    // Red floating number near center-right (enemy area)
    const x = width - 150 + Phaser.Math.Between(-20, 20)
    const y = height / 2 + Phaser.Math.Between(-30, 30)

    const text = this.scene.add.text(x, y, `-${amount}`, {
      fontSize: '32px', color: '#ff3333', fontFamily: 'sans-serif',
      fontStyle: 'bold',
    }).setOrigin(0.5).setDepth(56)

    this.overlay.add(text)

    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: text,
        y: y - 50,
        alpha: 0,
        duration: DUR.SLOW,
        ease: 'Power2',
        onComplete: () => {
          text.destroy()
          resolve()
        },
      })
    })
  }

  // ===== Horror =====
  private animateHorror(amount: number): Promise<void> {
    const { width, height } = this.scene.scale
    const x = width / 2 + Phaser.Math.Between(-30, 30)
    const y = 50

    const text = this.scene.add.text(x, y, `🧠-${amount}`, {
      fontSize: '28px', color: '#9966ff', fontFamily: 'sans-serif',
    }).setOrigin(0.5).setDepth(56)

    this.overlay.add(text)

    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: text,
        y: y - 40,
        alpha: 0,
        duration: DUR.SLOW,
        onComplete: () => { text.destroy(); resolve() },
      })
    })
  }

  // ===== Card Play =====
  private animateCardPlay(_cardId?: string): Promise<void> {
    const { width, height } = this.scale

    const glow = this.scene.add.rectangle(width / 2, height - 140, 100, 130, 0xc0a060, 0)
      .setDepth(55)
    this.overlay.add(glow)

    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: glow,
        alpha: 0.4,
        duration: DUR.FAST,
        yoyo: true,
        onComplete: () => { glow.destroy(); resolve() },
      })
    })
  }

  // ===== Card Draw =====
  private animateCardDraw(): Promise<void> {
    const { width, height } = this.scene.scale

    // Card slides from deck to hand area
    const card = this.scene.add.rectangle(width / 2 + 200, 50, 60, 80, 0x2a2a4e)
      .setStrokeStyle(2, 0x445566).setDepth(55)
    this.overlay.add(card)

    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: card,
        x: width / 2,
        y: height - 140,
        scaleX: 1.2,
        scaleY: 1.2,
        duration: DUR.NORMAL,
        ease: 'Power2',
        onComplete: () => {
          this.scene.tweens.add({
            targets: card,
            alpha: 0,
            duration: DUR.FAST,
            onComplete: () => { card.destroy(); resolve() },
          })
        },
      })
    })
  }

  // ===== Enemy Defeated =====
  private animateEnemyDefeated(): Promise<void> {
    const { width } = this.scene.scale
    const x = width - 130
    const y = 200

    // Shatter effect: multiple fragments
    const fragments: Phaser.GameObjects.Rectangle[] = []
    for (let i = 0; i < 6; i++) {
      const frag = this.scene.add.rectangle(
        x + Phaser.Math.Between(-20, 20),
        y + Phaser.Math.Between(-20, 20),
        15, 15, 0xe74c3c,
      ).setDepth(55)
      fragments.push(frag)
      this.overlay.add(frag)
    }

    return new Promise(resolve => {
      fragments.forEach(frag => {
        this.scene.tweens.add({
          targets: frag,
          x: frag.x + Phaser.Math.Between(-80, 80),
          y: frag.y + Phaser.Math.Between(-80, 80),
          alpha: 0,
          angle: Phaser.Math.Between(-180, 180),
          duration: DUR.SLOW,
          ease: 'Power2',
          onComplete: () => frag.destroy(),
        })
      })
      this.scene.time.delayedCall(DUR.SLOW, resolve)
    })
  }

  // ===== Clue Discovered =====
  private animateClueDiscovered(amount: number): Promise<void> {
    const { width } = this.scene.scale

    const text = this.scene.add.text(width / 2, 200, `🔍+${amount}`, {
      fontSize: '28px', color: '#ffdd44', fontFamily: 'sans-serif',
    }).setOrigin(0.5).setDepth(56)
    this.overlay.add(text)

    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: text,
        y: 50,
        alpha: 0,
        duration: DUR.SLOW,
        ease: 'Power2',
        onComplete: () => { text.destroy(); resolve() },
      })
    })
  }

  // ===== Enemy Engaged =====
  private animateEnemyEngaged(): Promise<void> {
    const { width, height } = this.scene.scale
    const flash = this.scene.add.rectangle(width / 2, height / 2, width, height, 0x440000, 0)
      .setDepth(54)
    this.overlay.add(flash)

    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: flash,
        alpha: 0.2,
        duration: DUR.FAST,
        yoyo: true,
        onComplete: () => { flash.destroy(); resolve() },
      })
    })
  }

  // ===== Enemy Attack =====
  private animateEnemyAttack(): Promise<void> {
    const { width, height } = this.scene.scale

    // Screen shake effect
    const camera = this.scene.cameras.main
    camera.shake(DUR.NORMAL, 0.01)

    const text = this.scene.add.text(width / 2, height / 2, '⚔️', {
      fontSize: '48px',
    }).setOrigin(0.5).setAlpha(0).setDepth(56)
    this.overlay.add(text)

    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: text,
        alpha: 1,
        scaleX: 1.5,
        scaleY: 1.5,
        duration: DUR.FAST,
        yoyo: true,
        onComplete: () => { text.destroy(); resolve() },
      })
    })
  }

  // ===== Resource Gain =====
  private animateResourceGain(amount: number): Promise<void> {
    const text = this.scene.add.text(420, 30, `+${amount}`, {
      fontSize: '24px', color: '#44ff44', fontFamily: 'sans-serif',
    }).setOrigin(0.5).setDepth(56)
    this.overlay.add(text)

    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: text,
        y: 10,
        alpha: 0,
        duration: DUR.NORMAL,
        onComplete: () => { text.destroy(); resolve() },
      })
    })
  }

  // ===== Movement =====
  private animateMovement(_locationId?: string): Promise<void> {
    // Brief fade transition
    const { width, height } = this.scene.scale
    const overlay = this.scene.add.rectangle(width / 2, height / 2, width, height, 0x000000, 0)
      .setDepth(54)
    this.overlay.add(overlay)

    return new Promise(resolve => {
      this.scene.tweens.add({
        targets: overlay,
        alpha: 0.3,
        duration: DUR.FAST,
        yoyo: true,
        onComplete: () => { overlay.destroy(); resolve() },
      })
    })
  }

  private get scale() {
    return this.scene.scale
  }

  destroy(): void {
    this.overlay.removeAll(true)
    this.overlay.destroy()
  }
}
