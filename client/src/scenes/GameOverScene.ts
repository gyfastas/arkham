/** Game over scene: victory/defeat display with restart option. */

import Phaser from 'phaser'
import { SocketClient } from '../network/SocketClient'
import { GameStore } from '../state/GameStore'

export class GameOverScene extends Phaser.Scene {
  private client!: SocketClient
  private store!: GameStore
  private result!: { type: string; message: string }

  constructor() {
    super({ key: 'GameOverScene' })
  }

  init(data: { client: SocketClient; store: GameStore; result: { type: string; message: string } }) {
    this.client = data.client
    this.store = data.store
    this.result = data.result
  }

  create() {
    const { width, height } = this.scale
    const isWin = this.result.type === 'win'

    // Overlay
    this.add.rectangle(width / 2, height / 2, width, height, 0x000000, 0.85)

    // Result title
    this.add.text(width / 2, height / 2 - 80, isWin ? '胜利' : '失败', {
      fontSize: '48px',
      fontFamily: 'serif',
      color: isWin ? '#c0a060' : '#e74c3c',
    }).setOrigin(0.5)

    // Message
    this.add.text(width / 2, height / 2, this.result.message, {
      fontSize: '18px',
      fontFamily: 'sans-serif',
      color: '#cccccc',
      wordWrap: { width: 500 },
      align: 'center',
    }).setOrigin(0.5)

    // Restart button
    const btn = this.add.rectangle(width / 2, height / 2 + 80, 180, 44, 0x2980b9)
      .setStrokeStyle(2, 0x4aa3df)
      .setInteractive({ useHandCursor: true })

    this.add.text(width / 2, height / 2 + 80, '返回大厅', {
      fontSize: '18px', color: '#ffffff', fontFamily: 'sans-serif',
    }).setOrigin(0.5)

    btn.on('pointerover', () => btn.setFillStyle(0x3498db))
    btn.on('pointerout', () => btn.setFillStyle(0x2980b9))
    btn.on('pointerdown', () => {
      this.store.clear()
      this.client.leaveRoom()
      this.scene.start('LobbyScene', { client: this.client, store: this.store })
    })
  }
}
