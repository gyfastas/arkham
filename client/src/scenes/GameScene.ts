/** Main game scene: renders the full game board. */

import Phaser from 'phaser'
import { SocketClient } from '../network/SocketClient'
import { GameStore, STORE_EVENTS } from '../state/GameStore'
import { AnimationManager } from '../objects/AnimationManager'
import { ModalUI } from '../ui/Modal'
import { Tooltip } from '../ui/Tooltip'
import { SkillCommitModal } from '../ui/SkillCommitModal'
import type {
  GameState, CardDisplay, CardInstanceDisplay, EnemyDisplay,
  LocationDisplay, InvestigatorDisplay, ActionResult, GameEventData, PendingChoice,
} from '../state/types'

// Class colors
const CLASS_COLORS: Record<string, number> = {
  guardian: 0x2980b9,
  seeker: 0xd4a017,
  rogue: 0x27ae60,
  mystic: 0x8e44ad,
  survivor: 0xc0392b,
  neutral: 0x666666,
}

// Layout constants
const HUD_HEIGHT = 90
const HAND_HEIGHT = 140
const LOG_WIDTH = 260
const CARD_W = 90
const CARD_H = 120

export class GameScene extends Phaser.Scene {
  private client!: SocketClient
  private store!: GameStore

  // Systems
  private animationMgr!: AnimationManager
  private modalUI!: ModalUI
  private tooltip!: Tooltip
  private skillCommitModal!: SkillCommitModal
  private pendingStateAfterAnim: GameState | null = null

  // UI containers
  private hudContainer!: Phaser.GameObjects.Container
  private mapContainer!: Phaser.GameObjects.Container
  private handContainer!: Phaser.GameObjects.Container
  private enemyContainer!: Phaser.GameObjects.Container
  private playAreaContainer!: Phaser.GameObjects.Container
  private logContainer!: Phaser.GameObjects.Container
  private actionBar!: Phaser.GameObjects.Container
  private modalContainer!: Phaser.GameObjects.Container

  // Drag state
  private dragCard: { card: CardDisplay; ghost: Phaser.GameObjects.Rectangle } | null = null

  // HUD text elements
  private hudTexts: Record<string, Phaser.GameObjects.Text> = {}
  private logTexts: Phaser.GameObjects.Text[] = []

  constructor() {
    super({ key: 'GameScene' })
  }

  init(data: { client: SocketClient; store: GameStore }) {
    this.client = data.client
    this.store = data.store
  }

  create() {
    const { width, height } = this.scale

    // Background
    this.add.rectangle(width / 2, height / 2, width, height, 0x0a0a1a)

    // Create layout containers
    this.createHUD()
    this.createMapArea()
    this.createHandArea()
    this.createEnemyPanel()
    this.createPlayArea()
    this.createLogPanel()
    this.createActionBar()
    this.createModalContainer()

    // Initialize systems
    this.animationMgr = new AnimationManager(this)
    this.modalUI = new ModalUI(this)
    this.tooltip = new Tooltip(this)
    this.skillCommitModal = new SkillCommitModal(this)

    // Wire up store events
    this.store.events.on(STORE_EVENTS.STATE_CHANGED, this.onStateChanged, this)
    this.store.events.on(STORE_EVENTS.GAME_OVER, this.onGameOver, this)

    // Wire up network — play animations before updating state
    this.client.onStateUpdate = (state: GameState, events?: GameEventData[]) => {
      this.handleStateWithEvents(state, events || [])
    }
    this.client.onActionResult = (result: ActionResult) => {
      if (!result.success) {
        this.showToast(result.message)
      }
      if (result.state) {
        this.handleStateWithEvents(result.state, result.events || [])
      }
    }

    // Initial render
    if (this.store.state) {
      this.renderAll(this.store.state)
    }
  }

  // ===== HUD (top bar) =====
  private createHUD() {
    const { width } = this.scale
    this.hudContainer = this.add.container(0, 0)

    // Background bar
    this.hudContainer.add(
      this.add.rectangle(width / 2, HUD_HEIGHT / 2, width, HUD_HEIGHT, 0x1a1a2e)
    )

    const labels = [
      { key: 'name', x: 20, label: '' },
      { key: 'hp', x: 200, label: '❤️' },
      { key: 'san', x: 300, label: '🧠' },
      { key: 'res', x: 400, label: '💰' },
      { key: 'clues', x: 500, label: '🔍' },
      { key: 'actions', x: 600, label: '▶️' },
      { key: 'doom', x: 720, label: '👹' },
      { key: 'deck', x: 840, label: '🃏' },
      { key: 'round', x: 940, label: '📅' },
    ]

    labels.forEach(({ key, x, label }) => {
      if (label) {
        this.hudContainer.add(
          this.add.text(x, 20, label, { fontSize: '14px', color: '#888' })
        )
      }
      this.hudTexts[key] = this.add.text(x + (label ? 24 : 0), key === 'name' ? 15 : 40, '', {
        fontSize: key === 'name' ? '22px' : '20px',
        fontFamily: 'sans-serif',
        color: '#ffffff',
      })
      this.hudContainer.add(this.hudTexts[key])
    })

    // Phase indicator
    this.hudTexts['phase'] = this.add.text(width - 20, 35, '', {
      fontSize: '16px', color: '#c0a060', fontFamily: 'sans-serif',
    }).setOrigin(1, 0.5)
    this.hudContainer.add(this.hudTexts['phase'])

    // Scenario info
    this.hudTexts['scenario'] = this.add.text(width - 20, 60, '', {
      fontSize: '12px', color: '#666', fontFamily: 'sans-serif',
    }).setOrigin(1, 0.5)
    this.hudContainer.add(this.hudTexts['scenario'])
  }

  private updateHUD(state: GameState) {
    const inv = state.investigator
    const classColor = CLASS_COLORS[inv.class] || 0xffffff
    this.hudTexts['name'].setText(inv.name_cn).setColor(`#${classColor.toString(16).padStart(6, '0')}`)
    this.hudTexts['hp'].setText(`${inv.health - inv.damage}/${inv.health}`)
    this.hudTexts['san'].setText(`${inv.sanity - inv.horror}/${inv.sanity}`)
    this.hudTexts['res'].setText(`${inv.resources}`)
    this.hudTexts['clues'].setText(`${inv.clues}`)
    this.hudTexts['actions'].setText(`${inv.actions_remaining}`)
    this.hudTexts['doom'].setText(`${state.doom}/${state.doom_threshold}`)
    this.hudTexts['deck'].setText(`${inv.deck_count}`)
    this.hudTexts['round'].setText(`R${state.round}`)

    const phaseCn: Record<string, string> = {
      INVESTIGATION: '调查阶段', MYTHOS: '神话阶段',
      ENEMY: '敌人阶段', UPKEEP: '刷新阶段',
    }
    this.hudTexts['phase'].setText(phaseCn[state.phase] || state.phase)

    if (state.scenario.act && state.scenario.agenda) {
      this.hudTexts['scenario'].setText(
        `事件: ${state.scenario.act.name_cn} | 密谋: ${state.scenario.agenda.name_cn}`
      )
    }
  }

  // ===== Location Map (center) =====
  private createMapArea() {
    const { width, height } = this.scale
    const mapY = HUD_HEIGHT + 10
    this.mapContainer = this.add.container(LOG_WIDTH, mapY)
  }

  private renderLocations(locations: Record<string, LocationDisplay>, currentLocId: string) {
    this.mapContainer.removeAll(true)
    const { width, height } = this.scale
    const mapW = width - LOG_WIDTH * 2
    const mapH = height - HUD_HEIGHT - HAND_HEIGHT - 100

    const ids = Object.keys(locations)
    const nodeW = 140
    const nodeH = 70
    const cols = Math.min(ids.length, 3)
    const rows = Math.ceil(ids.length / cols)

    // Draw connection edges first
    const gfx = this.add.graphics()
    this.mapContainer.add(gfx)
    gfx.lineStyle(2, 0x334455)

    const positions: Record<string, { x: number; y: number }> = {}
    ids.forEach((id, i) => {
      const col = i % cols
      const row = Math.floor(i / cols)
      const x = (col + 0.5) * (mapW / cols)
      const y = (row + 0.5) * (mapH / rows)
      positions[id] = { x, y }
    })

    // Draw edges
    ids.forEach(id => {
      const loc = locations[id]
      const pos = positions[id]
      loc.connections.forEach(connId => {
        const connPos = positions[connId]
        if (connPos && id < connId) {
          gfx.beginPath()
          gfx.moveTo(pos.x, pos.y)
          gfx.lineTo(connPos.x, connPos.y)
          gfx.strokePath()
        }
      })
    })

    // Draw nodes
    ids.forEach(id => {
      const loc = locations[id]
      const pos = positions[id]
      const isCurrent = id === currentLocId

      const bg = this.add.rectangle(pos.x, pos.y, nodeW, nodeH, isCurrent ? 0x1a2a4a : 0x1a1a2e)
        .setStrokeStyle(2, isCurrent ? 0x667eea : 0x333344)
        .setInteractive({ useHandCursor: true })

      // Name
      this.mapContainer.add(bg)
      this.mapContainer.add(
        this.add.text(pos.x, pos.y - 15, loc.name_cn || id, {
          fontSize: '13px', color: isCurrent ? '#ffffff' : '#aaaaaa',
          fontFamily: 'sans-serif',
        }).setOrigin(0.5)
      )

      // Stats
      this.mapContainer.add(
        this.add.text(pos.x, pos.y + 12, `帷幕:${loc.shroud}  线索:${loc.clues}`, {
          fontSize: '11px', color: '#888888', fontFamily: 'sans-serif',
        }).setOrigin(0.5)
      )

      if (loc.enemies_here > 0) {
        this.mapContainer.add(
          this.add.text(pos.x + nodeW / 2 - 5, pos.y - nodeH / 2 + 5, `👹${loc.enemies_here}`, {
            fontSize: '11px', color: '#e74c3c',
          }).setOrigin(1, 0)
        )
      }

      // Click to move
      if (!isCurrent) {
        bg.on('pointerdown', () => {
          this.client.sendAction('MOVE', { location_id: id })
        })
        bg.on('pointerover', () => bg.setStrokeStyle(2, 0x667eea))
        bg.on('pointerout', () => bg.setStrokeStyle(2, 0x333344))
      }
    })
  }

  // ===== Hand Cards (bottom) =====
  private createHandArea() {
    const { width, height } = this.scale
    this.handContainer = this.add.container(LOG_WIDTH + 10, height - HAND_HEIGHT)
  }

  private renderHand(hand: CardDisplay[]) {
    this.handContainer.removeAll(true)
    const { width } = this.scale
    const availW = width - LOG_WIDTH * 2 - 20
    const spacing = Math.min(CARD_W + 8, availW / Math.max(hand.length, 1))

    hand.forEach((card, i) => {
      const x = i * spacing
      const color = CLASS_COLORS[card.class] || 0x444444

      // Card bg
      const bg = this.add.rectangle(x + CARD_W / 2, CARD_H / 2, CARD_W, CARD_H, 0x1a1a2e)
        .setStrokeStyle(2, color)
        .setInteractive({ useHandCursor: true, draggable: true })

      // Name
      const nameText = this.add.text(x + CARD_W / 2, 15, card.name_cn || card.name, {
        fontSize: '11px', color: '#ffffff', fontFamily: 'sans-serif',
        wordWrap: { width: CARD_W - 10 },
        align: 'center',
      }).setOrigin(0.5, 0)

      // Type
      const typeCn: Record<string, string> = { asset: '支援', event: '事件', skill: '技能' }
      this.handContainer.add(bg)
      this.handContainer.add(nameText)
      this.handContainer.add(
        this.add.text(x + CARD_W / 2, CARD_H - 25, typeCn[card.type] || card.type, {
          fontSize: '10px', color: '#888',
        }).setOrigin(0.5)
      )

      // Cost badge
      if (card.cost !== null && card.cost !== undefined) {
        const badge = this.add.circle(x + CARD_W - 8, 8, 10, 0xd4a017)
        const costText = this.add.text(x + CARD_W - 8, 8, `${card.cost}`, {
          fontSize: '11px', color: '#000', fontFamily: 'sans-serif',
        }).setOrigin(0.5)
        this.handContainer.add(badge)
        this.handContainer.add(costText)
      }

      // Skill icons
      const icons = card.skill_icons || {}
      const iconStr = Object.entries(icons)
        .filter(([_, v]) => v > 0)
        .map(([k, v]) => {
          const iconMap: Record<string, string> = {
            willpower: '意', intellect: '智', combat: '战', agility: '敏', wild: '万',
          }
          return `${iconMap[k] || k}${v}`
        }).join(' ')
      if (iconStr) {
        this.handContainer.add(
          this.add.text(x + CARD_W / 2, CARD_H - 10, iconStr, {
            fontSize: '9px', color: '#c0a060',
          }).setOrigin(0.5)
        )
      }

      // Store original position for drag reset
      const origX = bg.x
      const origY = bg.y

      // Hover: lift card up + show tooltip
      bg.on('pointerover', (pointer: Phaser.Input.Pointer) => {
        if (!this.dragCard) {
          bg.setScale(1.1)
          bg.y -= 8
          nameText.setScale(1.1)
          nameText.y -= 8
          bg.setStrokeStyle(3, 0xffffff)
        }
        // Show tooltip — compute world position from container
        const worldX = this.handContainer.x + x + CARD_W
        const worldY = this.handContainer.y - 10
        this.tooltip.showCard(card, worldX, worldY)
      })
      bg.on('pointerout', () => {
        if (!this.dragCard || this.dragCard.card !== card) {
          bg.setScale(1)
          bg.y = origY
          nameText.setScale(1)
          nameText.y = 15
          bg.setStrokeStyle(2, color)
        }
        this.tooltip.hide()
      })

      // Drag to play
      bg.on('dragstart', (_pointer: Phaser.Input.Pointer) => {
        if (card.type === 'skill') {
          this.showToast('技能卡只能投入到检定中')
          return
        }
        const ghost = this.add.rectangle(
          this.handContainer.x + bg.x, this.handContainer.y + bg.y,
          CARD_W, CARD_H, color, 0.3,
        ).setDepth(150)
        this.dragCard = { card, ghost }
        bg.setAlpha(0.5)
      })

      bg.on('drag', (_pointer: Phaser.Input.Pointer, dragX: number, dragY: number) => {
        if (this.dragCard?.ghost) {
          this.dragCard.ghost.setPosition(
            this.handContainer.x + dragX,
            this.handContainer.y + dragY,
          )
        }
      })

      bg.on('dragend', () => {
        if (this.dragCard) {
          const ghost = this.dragCard.ghost
          const droppedAboveHand = ghost.y < this.handContainer.y - 30
          ghost.destroy()

          if (droppedAboveHand) {
            // Dropped above hand area — play the card
            this.client.sendAction('PLAY', { card_id: card.id })
          }

          bg.setAlpha(1)
          bg.setScale(1)
          bg.setPosition(origX, origY)
          nameText.setScale(1)
          nameText.y = 15
          bg.setStrokeStyle(2, color)
          this.dragCard = null
        }
      })

      // Click to play (fallback)
      bg.on('pointerdown', (_pointer: Phaser.Input.Pointer) => {
        if (card.type === 'skill') {
          this.showToast('技能卡只能投入到检定中')
          return
        }
        // Only play on click if not dragging — handled by a short timer
        // to distinguish from drag start
      })
      bg.on('pointerup', (pointer: Phaser.Input.Pointer) => {
        // If pointer barely moved, treat as click
        if (!this.dragCard && Math.abs(pointer.upX - pointer.downX) < 5 && Math.abs(pointer.upY - pointer.downY) < 5) {
          if (card.type === 'skill') {
            this.showToast('技能卡只能投入到检定中')
            return
          }
          this.client.sendAction('PLAY', { card_id: card.id })
        }
      })
    })
  }

  // ===== Enemy Panel (right side) =====
  private createEnemyPanel() {
    const { width } = this.scale
    this.enemyContainer = this.add.container(width - LOG_WIDTH + 10, HUD_HEIGHT + 10)
  }

  private renderEnemies(enemies: EnemyDisplay[]) {
    this.enemyContainer.removeAll(true)
    const cardW = LOG_WIDTH - 20
    const cardH = 80

    enemies.forEach((enemy, i) => {
      const y = i * (cardH + 8)

      const bg = this.add.rectangle(cardW / 2, y + cardH / 2, cardW, cardH, 0x1a0a0a)
        .setStrokeStyle(2, 0xe74c3c)
        .setAlpha(enemy.exhausted ? 0.5 : 1)

      this.enemyContainer.add(bg)

      // Name
      this.enemyContainer.add(
        this.add.text(10, y + 8, enemy.name_cn || enemy.name, {
          fontSize: '13px', color: '#e74c3c', fontFamily: 'sans-serif',
        })
      )

      // Stats
      this.enemyContainer.add(
        this.add.text(10, y + 28, `⚔️${enemy.fight}  ❤️${enemy.health - enemy.current_damage}/${enemy.health}  👣${enemy.evade}`, {
          fontSize: '11px', color: '#aaa',
        })
      )

      // HP bar
      const hpRatio = Math.max(0, (enemy.health - enemy.current_damage) / enemy.health)
      this.enemyContainer.add(
        this.add.rectangle(cardW / 2, y + 50, (cardW - 20) * hpRatio, 6, 0xe74c3c).setOrigin(0.5)
      )

      // Action buttons
      if (enemy.engaged) {
        const atkBtn = this.add.text(cardW - 60, y + 58, '攻击', {
          fontSize: '11px', color: '#ff6666', backgroundColor: '#330000',
          padding: { x: 6, y: 2 },
        }).setInteractive({ useHandCursor: true })
        atkBtn.on('pointerdown', () => {
          this.showWeaponSelect([enemy])
        })
        this.enemyContainer.add(atkBtn)

        const evadeBtn = this.add.text(cardW - 20, y + 58, '闪', {
          fontSize: '11px', color: '#66ff66', backgroundColor: '#003300',
          padding: { x: 6, y: 2 },
        }).setInteractive({ useHandCursor: true })
        evadeBtn.on('pointerdown', () => {
          this.showSkillCommitThen('agility', (committed) => {
            this.client.sendAction('EVADE', {
              enemy_instance_id: enemy.instance_id,
              committed_cards: committed,
            })
          })
        })
        this.enemyContainer.add(evadeBtn)
      } else {
        const engBtn = this.add.text(cardW - 60, y + 58, '交战', {
          fontSize: '11px', color: '#ffaa66', backgroundColor: '#332200',
          padding: { x: 6, y: 2 },
        }).setInteractive({ useHandCursor: true })
        engBtn.on('pointerdown', () => {
          this.client.sendAction('ENGAGE', { enemy_instance_id: enemy.instance_id })
        })
        this.enemyContainer.add(engBtn)
      }
    })
  }

  // ===== Play Area =====
  private createPlayArea() {
    const { width, height } = this.scale
    this.playAreaContainer = this.add.container(LOG_WIDTH + 10, height - HAND_HEIGHT - 70)
  }

  private renderPlayArea(assets: CardInstanceDisplay[]) {
    this.playAreaContainer.removeAll(true)
    const assetW = 70
    const assetH = 40

    assets.forEach((asset, i) => {
      const x = i * (assetW + 6)

      const bg = this.add.rectangle(x + assetW / 2, assetH / 2, assetW, assetH, 0x1a1a2e)
        .setStrokeStyle(1, 0x445566)
        .setAlpha(asset.exhausted ? 0.4 : 1)
        .setAngle(asset.exhausted ? 5 : 0)
        .setInteractive({ useHandCursor: true })

      this.playAreaContainer.add(bg)
      this.playAreaContainer.add(
        this.add.text(x + assetW / 2, assetH / 2, asset.name_cn || asset.name, {
          fontSize: '10px', color: '#aaa', fontFamily: 'sans-serif',
          wordWrap: { width: assetW - 6 }, align: 'center',
        }).setOrigin(0.5).setAlpha(asset.exhausted ? 0.4 : 1)
      )

      // Tooltip on hover for play area assets
      bg.on('pointerover', () => {
        const worldX = this.playAreaContainer.x + x + assetW
        const worldY = this.playAreaContainer.y - 10
        this.tooltip.showAsset(asset, worldX, worldY)
      })
      bg.on('pointerout', () => {
        this.tooltip.hide()
      })
    })
  }

  // ===== Log Panel (left side) =====
  private createLogPanel() {
    this.logContainer = this.add.container(5, HUD_HEIGHT + 10)

    this.logContainer.add(
      this.add.rectangle(LOG_WIDTH / 2 - 5, 0, LOG_WIDTH - 10, 20, 0x111122).setOrigin(0.5, 0)
    )
    this.logContainer.add(
      this.add.text(LOG_WIDTH / 2 - 5, 3, '行动日志', {
        fontSize: '12px', color: '#888', fontFamily: 'sans-serif',
      }).setOrigin(0.5, 0)
    )
  }

  private renderLog(log: string[]) {
    // Remove old log texts
    this.logTexts.forEach(t => t.destroy())
    this.logTexts = []

    const { height } = this.scale
    const maxLines = Math.floor((height - HUD_HEIGHT - 50) / 16)
    const visibleLog = log.slice(-maxLines)

    visibleLog.forEach((line, i) => {
      const t = this.add.text(10, 28 + i * 16, line, {
        fontSize: '10px', color: '#667788', fontFamily: 'monospace',
        wordWrap: { width: LOG_WIDTH - 20 },
      })
      this.logContainer.add(t)
      this.logTexts.push(t)
    })
  }

  // ===== Action Bar =====
  private createActionBar() {
    const { width, height } = this.scale
    this.actionBar = this.add.container(width / 2, height - HAND_HEIGHT - 30)

    const actions = [
      { label: '调查', action: 'INVESTIGATE', color: 0xd4a017, skillType: 'intellect' },
      { label: '抽牌', action: 'DRAW', color: 0x3498db, skillType: null },
      { label: '资源', action: 'RESOURCE', color: 0x27ae60, skillType: null },
      { label: '结束回合', action: 'END_TURN', color: 0x95a5a6, skillType: null },
    ]

    actions.forEach((a, i) => {
      const x = (i - 1.5) * 110
      const btn = this.add.rectangle(x, 0, 100, 30, a.color, 0.8)
        .setStrokeStyle(1, 0xffffff)
        .setInteractive({ useHandCursor: true })

      const label = this.add.text(x, 0, a.label, {
        fontSize: '14px', color: '#ffffff', fontFamily: 'sans-serif',
      }).setOrigin(0.5)

      btn.on('pointerover', () => btn.setAlpha(1))
      btn.on('pointerout', () => btn.setAlpha(0.8))
      btn.on('pointerdown', () => {
        if (a.action === 'END_TURN') {
          this.client.endTurn()
        } else if (a.skillType) {
          // Actions with skill tests show commit modal first
          this.showSkillCommitThen(a.skillType, (committed) => {
            this.client.sendAction(a.action, { committed_cards: committed })
          })
        } else {
          this.client.sendAction(a.action)
        }
      })

      this.actionBar.add(btn)
      this.actionBar.add(label)
    })
  }

  // ===== Modal =====
  private createModalContainer() {
    this.modalContainer = this.add.container(0, 0).setDepth(100).setVisible(false)
  }

  private showChoiceModal(choice: PendingChoice) {
    this.modalContainer.removeAll(true)
    const { width, height } = this.scale

    // Overlay
    const overlay = this.add.rectangle(width / 2, height / 2, width, height, 0x000000, 0.7)
      .setInteractive()
    this.modalContainer.add(overlay)

    // Panel
    const panelW = 400
    const panelH = 60 + choice.options.length * 50
    this.modalContainer.add(
      this.add.rectangle(width / 2, height / 2, panelW, panelH, 0x1a1a2e)
        .setStrokeStyle(2, 0xc0a060)
    )

    // Prompt (strip HTML)
    const promptText = choice.prompt.replace(/<[^>]+>/g, '')
    this.modalContainer.add(
      this.add.text(width / 2, height / 2 - panelH / 2 + 20, promptText, {
        fontSize: '14px', color: '#ffffff', fontFamily: 'sans-serif',
        wordWrap: { width: panelW - 40 }, align: 'center',
      }).setOrigin(0.5, 0)
    )

    // Options
    choice.options.forEach((opt, i) => {
      const y = height / 2 - panelH / 2 + 60 + i * 50
      const btn = this.add.rectangle(width / 2, y, panelW - 40, 36, 0x2a2a4e)
        .setStrokeStyle(1, 0x445566)
        .setInteractive({ useHandCursor: true })

      const label = this.add.text(width / 2, y, opt.label, {
        fontSize: '14px', color: '#ffffff', fontFamily: 'sans-serif',
      }).setOrigin(0.5)

      btn.on('pointerover', () => btn.setFillStyle(0x3a3a6e))
      btn.on('pointerout', () => btn.setFillStyle(0x2a2a4e))
      btn.on('pointerdown', () => {
        this.client.resolveChoice(opt.id)
        this.modalContainer.setVisible(false)
      })

      this.modalContainer.add(btn)
      this.modalContainer.add(label)
    })

    this.modalContainer.setVisible(true)
  }

  // ===== Toast notification =====
  private showToast(message: string) {
    const { width } = this.scale
    const toast = this.add.text(width / 2, HUD_HEIGHT + 20, message, {
      fontSize: '14px', color: '#ff6666', backgroundColor: '#330000',
      padding: { x: 12, y: 6 },
    }).setOrigin(0.5).setDepth(200)

    this.tweens.add({
      targets: toast,
      alpha: 0,
      y: toast.y - 30,
      duration: 2000,
      onComplete: () => toast.destroy(),
    })
  }

  // ===== Skill Commit flow =====
  private showSkillCommitThen(skillType: string, onDone: (committed: string[]) => void): void {
    const state = this.store.state
    if (!state) {
      onDone([])
      return
    }
    this.skillCommitModal.show({
      skillType,
      hand: state.hand,
      onConfirm: (ids) => onDone(ids),
      onSkip: () => onDone([]),
    })
  }

  // ===== Animation + State pipeline =====
  private async handleStateWithEvents(state: GameState, events: GameEventData[]) {
    if (events.length > 0 && !this.animationMgr.isBusy) {
      this.pendingStateAfterAnim = state
      await this.animationMgr.playEvents(events)
      // After animations complete, apply the final state
      if (this.pendingStateAfterAnim) {
        this.store.update(this.pendingStateAfterAnim)
        this.pendingStateAfterAnim = null
      }
    } else {
      this.store.update(state)
    }
  }

  // ===== State update handler =====
  private onStateChanged(state: GameState) {
    this.renderAll(state)
  }

  private renderAll(state: GameState) {
    this.updateHUD(state)
    this.renderLocations(state.locations, state.investigator.location_id)
    this.renderHand(state.hand)
    this.renderEnemies(state.enemies)
    this.renderPlayArea(state.play_area)
    this.renderLog(state.log)

    if (state.pending_choice) {
      this.showChoiceModal(state.pending_choice)
    }
  }

  private onGameOver(data: { type: string; message: string }) {
    this.scene.start('GameOverScene', {
      client: this.client,
      store: this.store,
      result: data,
    })
  }

  // ===== Weapon / Enemy select helpers =====

  private showWeaponSelect(enemies: EnemyDisplay[]) {
    const state = this.store.state
    if (!state) return

    // Find weapons in play area
    const weapons = state.play_area.filter(a =>
      !a.exhausted && a.slots.some(s => s === 'hand')
    )

    if (weapons.length === 0) {
      // No weapon — show commit modal then fight bare-handed
      if (enemies.length === 1) {
        this.showSkillCommitThen('combat', (committed) => {
          this.client.sendAction('FIGHT', {
            enemy_instance_id: enemies[0].instance_id,
            committed_cards: committed,
          })
        })
        return
      }
      this.showEnemySelect(enemies, null)
      return
    }

    // Show weapon select modal
    this.modalUI.show({
      title: '选择武器',
      options: [
        { id: '__none__', label: '徒手', sublabel: '无武器加成', color: 0x333344 },
        ...weapons.map(w => ({
          id: w.instance_id,
          label: w.name_cn || w.name,
          sublabel: w.uses ? `剩余: ${JSON.stringify(w.uses)}` : undefined,
        })),
      ],
      onSelect: (weaponId) => {
        const wid = weaponId === '__none__' ? undefined : weaponId
        if (enemies.length === 1) {
          // After weapon select, show commit modal
          this.showSkillCommitThen('combat', (committed) => {
            this.client.sendAction('FIGHT', {
              enemy_instance_id: enemies[0].instance_id,
              weapon_instance_id: wid,
              committed_cards: committed,
            })
          })
        } else {
          this.showEnemySelect(enemies, wid)
        }
      },
      onCancel: () => {},
      allowSkip: true,
    })
  }

  private showEnemySelect(enemies: EnemyDisplay[], weaponId: string | null | undefined) {
    this.modalUI.show({
      title: '选择目标敌人',
      options: enemies.map(e => ({
        id: e.instance_id,
        label: e.name_cn || e.name,
        sublabel: `⚔️${e.fight} ❤️${e.health - e.current_damage}/${e.health}`,
        color: 0x3a1a1a,
      })),
      onSelect: (enemyId) => {
        // After enemy select, show commit modal
        this.showSkillCommitThen('combat', (committed) => {
          this.client.sendAction('FIGHT', {
            enemy_instance_id: enemyId,
            weapon_instance_id: weaponId,
            committed_cards: committed,
          })
        })
      },
      onCancel: () => {},
      allowSkip: true,
    })
  }

  shutdown() {
    this.store.events.off(STORE_EVENTS.STATE_CHANGED, this.onStateChanged, this)
    this.store.events.off(STORE_EVENTS.GAME_OVER, this.onGameOver, this)
    this.animationMgr?.destroy()
    this.modalUI?.destroy()
    this.tooltip?.destroy()
    this.skillCommitModal?.destroy()
  }
}
