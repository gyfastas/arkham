/** Skill card commit modal for skill tests.
 *
 * Shows eligible hand cards with matching skill icons.
 * Player toggles cards on/off, then confirms or skips.
 */

import Phaser from 'phaser'
import type { CardDisplay } from '../state/types'

const ICON_CN: Record<string, string> = {
  willpower: '意', intellect: '智', combat: '战', agility: '敏', wild: '万',
}

const SKILL_CN: Record<string, string> = {
  combat: '战斗', intellect: '智力', agility: '敏捷', willpower: '意志',
}

export interface SkillCommitConfig {
  skillType: string
  hand: CardDisplay[]
  onConfirm: (committedIds: string[]) => void
  onSkip: () => void
}

export class SkillCommitModal {
  private container: Phaser.GameObjects.Container
  private scene: Phaser.Scene
  private selected: Set<string> = new Set()
  private config: SkillCommitConfig | null = null
  private summaryText: Phaser.GameObjects.Text | null = null
  private cardItems: Map<string, { bg: Phaser.GameObjects.Rectangle; check: Phaser.GameObjects.Text }> = new Map()

  constructor(scene: Phaser.Scene) {
    this.scene = scene
    this.container = scene.add.container(0, 0).setDepth(110).setVisible(false)
  }

  show(config: SkillCommitConfig): void {
    this.config = config
    this.selected.clear()
    this.cardItems.clear()
    this.container.removeAll(true)

    const { width, height } = this.scene.scale
    const skillType = config.skillType

    // Filter eligible cards (have matching skill icon or wild)
    const eligible = config.hand.filter(c => {
      const icons = c.skill_icons || {}
      return ((icons[skillType] || 0) + (icons['wild'] || 0)) > 0
    })

    if (eligible.length === 0) {
      // No eligible cards — skip directly
      config.onSkip()
      return
    }

    // Overlay
    const overlay = this.scene.add.rectangle(width / 2, height / 2, width, height, 0x000000, 0.7)
      .setInteractive()
    overlay.on('pointerdown', () => {}) // block clicks
    this.container.add(overlay)

    // Panel
    const panelW = 440
    const cardH = 48
    const panelH = 100 + eligible.length * cardH + 60
    const panelY = height / 2

    this.container.add(
      this.scene.add.rectangle(width / 2, panelY, panelW, panelH, 0x1a1a2e)
        .setStrokeStyle(2, 0xc0a060)
    )

    // Title
    const skillName = SKILL_CN[skillType] || skillType
    this.container.add(
      this.scene.add.text(width / 2, panelY - panelH / 2 + 22, `投入卡牌到${skillName}检定`, {
        fontSize: '16px', color: '#c0a060', fontFamily: 'sans-serif',
      }).setOrigin(0.5)
    )

    // Summary
    this.summaryText = this.scene.add.text(width / 2, panelY - panelH / 2 + 48, '已选 0 张，提供 +0 图标加成', {
      fontSize: '12px', color: '#888888', fontFamily: 'sans-serif',
    }).setOrigin(0.5)
    this.container.add(this.summaryText)

    // Card list
    eligible.forEach((card, i) => {
      const y = panelY - panelH / 2 + 75 + i * cardH
      const icons = card.skill_icons || {}
      const matching = (icons[skillType] || 0) + (icons['wild'] || 0)
      const detail = Object.entries(icons)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => `${ICON_CN[k] || k}×${v}`)
        .join(' ')

      const bg = this.scene.add.rectangle(width / 2, y, panelW - 30, cardH - 6, 0x2a2a4e)
        .setStrokeStyle(1, 0x445566)
        .setInteractive({ useHandCursor: true })

      const check = this.scene.add.text(width / 2 - panelW / 2 + 30, y, '', {
        fontSize: '16px', color: '#44ff44', fontFamily: 'sans-serif',
      }).setOrigin(0.5)

      // Card name
      this.container.add(bg)
      this.container.add(check)
      this.container.add(
        this.scene.add.text(width / 2 - 30, y - 8, card.name_cn || card.name, {
          fontSize: '13px', color: '#ffffff', fontFamily: 'sans-serif',
        }).setOrigin(0.5, 0.5)
      )

      // Card detail (type + icons)
      const typeCn: Record<string, string> = { asset: '支援', event: '事件', skill: '技能' }
      this.container.add(
        this.scene.add.text(width / 2 - 30, y + 10, `${typeCn[card.type] || card.type} | ${detail}`, {
          fontSize: '10px', color: '#888888', fontFamily: 'sans-serif',
        }).setOrigin(0.5, 0.5)
      )

      // Matching badge
      this.container.add(
        this.scene.add.text(width / 2 + panelW / 2 - 40, y, `+${matching}`, {
          fontSize: '14px', color: '#c0a060', fontFamily: 'sans-serif',
        }).setOrigin(0.5)
      )

      this.cardItems.set(card.id, { bg, check })

      bg.on('pointerdown', () => {
        this.toggleCard(card.id)
      })
      bg.on('pointerover', () => {
        if (!this.selected.has(card.id)) bg.setAlpha(0.8)
      })
      bg.on('pointerout', () => bg.setAlpha(1))
    })

    // Buttons
    const btnY = panelY + panelH / 2 - 30

    const skipBtn = this.scene.add.text(width / 2 - 70, btnY, '跳过', {
      fontSize: '14px', color: '#888888', backgroundColor: '#222233',
      padding: { x: 20, y: 6 },
    }).setOrigin(0.5).setInteractive({ useHandCursor: true })
    skipBtn.on('pointerdown', () => {
      this.hide()
      config.onSkip()
    })

    const confirmBtn = this.scene.add.text(width / 2 + 70, btnY, '确认投入', {
      fontSize: '14px', color: '#ffffff', backgroundColor: '#2a4a2a',
      padding: { x: 20, y: 6 },
    }).setOrigin(0.5).setInteractive({ useHandCursor: true })
    confirmBtn.on('pointerdown', () => {
      this.hide()
      config.onConfirm(Array.from(this.selected))
    })

    this.container.add(skipBtn)
    this.container.add(confirmBtn)
    this.container.setVisible(true)
  }

  private toggleCard(cardId: string): void {
    if (this.selected.has(cardId)) {
      this.selected.delete(cardId)
    } else {
      this.selected.add(cardId)
    }

    const item = this.cardItems.get(cardId)
    if (item) {
      const isSelected = this.selected.has(cardId)
      item.check.setText(isSelected ? '✓' : '')
      item.bg.setFillStyle(isSelected ? 0x2a4a2a : 0x2a2a4e)
      item.bg.setStrokeStyle(1, isSelected ? 0x44ff44 : 0x445566)
    }

    this.updateSummary()
  }

  private updateSummary(): void {
    if (!this.config || !this.summaryText) return
    const skillType = this.config.skillType
    let total = 0
    for (const id of this.selected) {
      const card = this.config.hand.find(c => c.id === id)
      if (card?.skill_icons) {
        total += (card.skill_icons[skillType] || 0) + (card.skill_icons['wild'] || 0)
      }
    }
    this.summaryText.setText(`已选 ${this.selected.size} 张，提供 +${total} 图标加成`)
  }

  private hide(): void {
    this.container.setVisible(false)
    this.container.removeAll(true)
    this.cardItems.clear()
  }

  destroy(): void {
    this.container.removeAll(true)
    this.container.destroy()
  }
}
