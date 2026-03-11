/** Floating card detail tooltip for hover. */

import Phaser from 'phaser'
import type { CardDisplay, CardInstanceDisplay } from '../state/types'

const TOOLTIP_W = 180
const TOOLTIP_PAD = 10

const CLASS_CN: Record<string, string> = {
  guardian: '守卫者', seeker: '探求者', rogue: '流浪者',
  mystic: '潜修者', survivor: '求生者', neutral: '中立',
}

const TYPE_CN: Record<string, string> = {
  asset: '支援', event: '事件', skill: '技能',
}

const ICON_CN: Record<string, string> = {
  willpower: '意', intellect: '智', combat: '战', agility: '敏', wild: '万',
}

export class Tooltip {
  private container: Phaser.GameObjects.Container
  private scene: Phaser.Scene

  constructor(scene: Phaser.Scene) {
    this.scene = scene
    this.container = scene.add.container(0, 0).setDepth(200).setVisible(false)
  }

  showCard(card: CardDisplay, worldX: number, worldY: number): void {
    this.container.removeAll(true)

    const lines: string[] = []
    lines.push(card.name_cn || card.name)
    lines.push(`${CLASS_CN[card.class] || card.class} · ${TYPE_CN[card.type] || card.type}`)
    if (card.cost !== null && card.cost !== undefined) lines.push(`费用: ${card.cost}`)
    if (card.slots && card.slots.length > 0) lines.push(`槽位: ${card.slots.join(', ')}`)
    if (card.traits && card.traits.length > 0) lines.push(card.traits.join(', '))

    const icons = card.skill_icons || {}
    const iconStr = Object.entries(icons)
      .filter(([, v]) => v > 0)
      .map(([k, v]) => `${ICON_CN[k] || k}×${v}`)
      .join(' ')
    if (iconStr) lines.push(`图标: ${iconStr}`)

    if (card.text) {
      lines.push('─'.repeat(12))
      lines.push(card.text)
    }

    const text = this.scene.add.text(TOOLTIP_PAD, TOOLTIP_PAD, lines.join('\n'), {
      fontSize: '11px',
      color: '#cccccc',
      fontFamily: 'sans-serif',
      wordWrap: { width: TOOLTIP_W - TOOLTIP_PAD * 2 },
      lineSpacing: 4,
    })

    const h = text.height + TOOLTIP_PAD * 2
    const bg = this.scene.add.rectangle(0, 0, TOOLTIP_W, h, 0x1a1a2e, 0.95)
      .setStrokeStyle(1, 0xc0a060)
      .setOrigin(0, 0)

    this.container.add(bg)
    this.container.add(text)

    // Position: above and to the right, clamped to screen
    const { width, height } = this.scene.scale
    let tx = worldX + 20
    let ty = worldY - h - 10
    if (tx + TOOLTIP_W > width) tx = worldX - TOOLTIP_W - 10
    if (ty < 0) ty = worldY + 20

    this.container.setPosition(tx, ty)
    this.container.setVisible(true)
  }

  showAsset(asset: CardInstanceDisplay, worldX: number, worldY: number): void {
    this.container.removeAll(true)

    const lines: string[] = []
    lines.push(asset.name_cn || asset.name)
    if (asset.exhausted) lines.push('（已横置）')
    if (asset.uses) {
      const usesStr = Object.entries(asset.uses).map(([k, v]) => `${k}: ${v}`).join(', ')
      lines.push(`使��次数: ${usesStr}`)
    }
    if (asset.slots && asset.slots.length > 0) lines.push(`槽位: ${asset.slots.join(', ')}`)

    const text = this.scene.add.text(TOOLTIP_PAD, TOOLTIP_PAD, lines.join('\n'), {
      fontSize: '11px',
      color: '#cccccc',
      fontFamily: 'sans-serif',
      wordWrap: { width: TOOLTIP_W - TOOLTIP_PAD * 2 },
      lineSpacing: 4,
    })

    const h = text.height + TOOLTIP_PAD * 2
    const bg = this.scene.add.rectangle(0, 0, TOOLTIP_W, h, 0x1a1a2e, 0.95)
      .setStrokeStyle(1, 0xc0a060)
      .setOrigin(0, 0)

    this.container.add(bg)
    this.container.add(text)

    const { width, height } = this.scene.scale
    let tx = worldX + 20
    let ty = worldY - h - 10
    if (tx + TOOLTIP_W > width) tx = worldX - TOOLTIP_W - 10
    if (ty < 0) ty = worldY + 20

    this.container.setPosition(tx, ty)
    this.container.setVisible(true)
  }

  hide(): void {
    this.container.setVisible(false)
  }

  destroy(): void {
    this.container.removeAll(true)
    this.container.destroy()
  }
}
