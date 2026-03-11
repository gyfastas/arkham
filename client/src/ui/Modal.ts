/** Reusable modal system for weapon select, card commit, etc. */

import Phaser from 'phaser'

export interface ModalOption {
  id: string
  label: string
  sublabel?: string
  color?: number
}

export interface ModalConfig {
  title: string
  options: ModalOption[]
  onSelect: (optionId: string) => void
  onCancel?: () => void
  allowSkip?: boolean
}

export class ModalUI {
  private container: Phaser.GameObjects.Container
  private scene: Phaser.Scene
  private visible = false

  constructor(scene: Phaser.Scene) {
    this.scene = scene
    this.container = scene.add.container(0, 0).setDepth(100).setVisible(false)
  }

  get isVisible(): boolean { return this.visible }

  show(config: ModalConfig): void {
    this.container.removeAll(true)
    const { width, height } = this.scene.scale

    // Overlay
    const overlay = this.scene.add.rectangle(width / 2, height / 2, width, height, 0x000000, 0.7)
      .setInteractive()
    if (config.onCancel) {
      overlay.on('pointerdown', () => {
        config.onCancel!()
        this.hide()
      })
    }
    this.container.add(overlay)

    // Panel
    const panelW = 420
    const optH = 46
    const panelH = 60 + config.options.length * optH + (config.allowSkip ? 50 : 0)

    const panel = this.scene.add.rectangle(width / 2, height / 2, panelW, panelH, 0x1a1a2e)
      .setStrokeStyle(2, 0xc0a060)
    this.container.add(panel)

    // Title
    this.container.add(
      this.scene.add.text(width / 2, height / 2 - panelH / 2 + 22, config.title, {
        fontSize: '16px', color: '#c0a060', fontFamily: 'sans-serif',
      }).setOrigin(0.5)
    )

    // Options
    config.options.forEach((opt, i) => {
      const y = height / 2 - panelH / 2 + 55 + i * optH
      const color = opt.color || 0x2a2a4e

      const btn = this.scene.add.rectangle(width / 2, y, panelW - 30, 38, color)
        .setStrokeStyle(1, 0x445566)
        .setInteractive({ useHandCursor: true })

      const label = this.scene.add.text(width / 2, y - (opt.sublabel ? 6 : 0), opt.label, {
        fontSize: '14px', color: '#ffffff', fontFamily: 'sans-serif',
      }).setOrigin(0.5)

      this.container.add(btn)
      this.container.add(label)

      if (opt.sublabel) {
        this.container.add(
          this.scene.add.text(width / 2, y + 10, opt.sublabel, {
            fontSize: '11px', color: '#888888', fontFamily: 'sans-serif',
          }).setOrigin(0.5)
        )
      }

      btn.on('pointerover', () => btn.setAlpha(0.8))
      btn.on('pointerout', () => btn.setAlpha(1))
      btn.on('pointerdown', () => {
        config.onSelect(opt.id)
        this.hide()
      })
    })

    // Skip button
    if (config.allowSkip) {
      const skipY = height / 2 + panelH / 2 - 30
      const skipBtn = this.scene.add.text(width / 2, skipY, '跳过', {
        fontSize: '14px', color: '#888888', fontFamily: 'sans-serif',
        backgroundColor: '#222233', padding: { x: 20, y: 6 },
      }).setOrigin(0.5).setInteractive({ useHandCursor: true })

      skipBtn.on('pointerdown', () => {
        config.onCancel?.()
        this.hide()
      })
      this.container.add(skipBtn)
    }

    this.container.setVisible(true)
    this.visible = true
  }

  hide(): void {
    this.container.setVisible(false)
    this.container.removeAll(true)
    this.visible = false
  }

  destroy(): void {
    this.container.removeAll(true)
    this.container.destroy()
  }
}
