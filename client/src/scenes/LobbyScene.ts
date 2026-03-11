/** Lobby scene: create/join room, pick investigator, start game. */

import Phaser from 'phaser'
import { SocketClient } from '../network/SocketClient'
import { GameStore } from '../state/GameStore'
import type { RoomState, GameState, GameEventData } from '../state/types'

const INVESTIGATORS = [
  { id: 'daisy_walker', name_cn: '黛西·沃克', class: 'seeker', color: 0xd4a017 },
  { id: 'roland_banks', name_cn: '罗兰·班克斯', class: 'guardian', color: 0x2980b9 },
  { id: 'skids_otoole', name_cn: '斯基兹·奥图尔', class: 'rogue', color: 0x27ae60 },
  { id: 'agnes_baker', name_cn: '艾格尼丝·贝克', class: 'mystic', color: 0x8e44ad },
  { id: 'wendy_adams', name_cn: '温蒂·亚当斯', class: 'survivor', color: 0xc0392b },
]

const SCENARIOS = [
  { id: 'the_gathering', name_cn: '聚合' },
  { id: 'the_midnight_masks', name_cn: '午夜面具' },
  { id: 'the_devourer_below', name_cn: '下方的吞噬者' },
]

export class LobbyScene extends Phaser.Scene {
  private client!: SocketClient
  private store!: GameStore
  private selectedInvestigator = 0
  private selectedScenario = 0
  private room: RoomState | null = null

  constructor() {
    super({ key: 'LobbyScene' })
  }

  init(data: { client: SocketClient; store: GameStore }) {
    this.client = data.client
    this.store = data.store
  }

  create() {
    const { width, height } = this.scale

    // Title
    this.add.text(width / 2, 40, 'ARKHAM HORROR LCG', {
      fontSize: '28px', fontFamily: 'serif', color: '#c0a060',
    }).setOrigin(0.5)

    // Scenario selection
    this.add.text(width / 2, 90, '选择剧本', {
      fontSize: '16px', fontFamily: 'sans-serif', color: '#aaa',
    }).setOrigin(0.5)

    SCENARIOS.forEach((s, i) => {
      const y = 120 + i * 40
      const btn = this.add.text(width / 2, y, s.name_cn, {
        fontSize: '20px', fontFamily: 'sans-serif',
        color: i === this.selectedScenario ? '#ffffff' : '#666666',
        backgroundColor: i === this.selectedScenario ? '#334' : undefined,
        padding: { x: 16, y: 6 },
      }).setOrigin(0.5).setInteractive({ useHandCursor: true })

      btn.on('pointerdown', () => {
        this.selectedScenario = i
        this.scene.restart({ client: this.client, store: this.store })
      })
    })

    // Investigator selection
    this.add.text(width / 2, 260, '选择调查员', {
      fontSize: '16px', fontFamily: 'sans-serif', color: '#aaa',
    }).setOrigin(0.5)

    INVESTIGATORS.forEach((inv, i) => {
      const x = width / 2 + (i - 2) * 130
      const y = 320
      const isSelected = i === this.selectedInvestigator
      const color = inv.color

      // Card background
      const rect = this.add.rectangle(x, y, 110, 60, isSelected ? color : 0x222233, isSelected ? 1 : 0.3)
        .setStrokeStyle(2, color)
        .setInteractive({ useHandCursor: true })

      this.add.text(x, y, inv.name_cn, {
        fontSize: '14px', fontFamily: 'sans-serif',
        color: isSelected ? '#ffffff' : '#888888',
      }).setOrigin(0.5)

      rect.on('pointerdown', () => {
        this.selectedInvestigator = i
        this.scene.restart({ client: this.client, store: this.store })
      })
    })

    // Start button
    const startBtn = this.add.rectangle(width / 2, height - 80, 200, 50, 0x2980b9)
      .setStrokeStyle(2, 0x4aa3df)
      .setInteractive({ useHandCursor: true })

    this.add.text(width / 2, height - 80, '开始游戏', {
      fontSize: '22px', fontFamily: 'sans-serif', color: '#ffffff',
    }).setOrigin(0.5)

    startBtn.on('pointerover', () => startBtn.setFillStyle(0x3498db))
    startBtn.on('pointerout', () => startBtn.setFillStyle(0x2980b9))
    startBtn.on('pointerdown', () => this.startGame())

    // Listen for state updates (game started)
    this.client.onStateUpdate = (state: GameState) => {
      this.store.update(state)
      this.scene.start('GameScene', { client: this.client, store: this.store })
    }

    this.client.onRoomUpdate = (room: RoomState) => {
      this.room = room
    }

    this.client.onError = (err) => {
      console.error('Server error:', err)
    }
  }

  private startGame() {
    const inv = INVESTIGATORS[this.selectedInvestigator]
    const scenario = SCENARIOS[this.selectedScenario]

    // Create room and setup game
    this.client.createRoom()
    // Wait a moment for room creation, then setup
    this.time.delayedCall(300, () => {
      this.client.setupGame(scenario.id, inv.id)
    })
  }
}
