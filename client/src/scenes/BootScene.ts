/** Boot scene: connects to server, then transitions to Lobby. */

import Phaser from 'phaser'
import { SocketClient } from '../network/SocketClient'
import { GameStore } from '../state/GameStore'

export class BootScene extends Phaser.Scene {
  private client!: SocketClient
  private store!: GameStore
  private statusText!: Phaser.GameObjects.Text

  constructor() {
    super({ key: 'BootScene' })
  }

  init(data: { client: SocketClient; store: GameStore }) {
    this.client = data.client
    this.store = data.store
  }

  create() {
    const { width, height } = this.scale

    this.add.text(width / 2, height / 2 - 60, 'ARKHAM HORROR LCG', {
      fontSize: '36px',
      fontFamily: 'serif',
      color: '#c0a060',
    }).setOrigin(0.5)

    this.statusText = this.add.text(width / 2, height / 2 + 20, '连接服务器中...', {
      fontSize: '18px',
      fontFamily: 'sans-serif',
      color: '#888888',
    }).setOrigin(0.5)

    this.connectToServer()
  }

  private async connectToServer() {
    try {
      await this.client.connect()
      this.statusText.setText(`已连接 (ID: ${this.client.playerId.slice(0, 6)})`)
      this.time.delayedCall(500, () => {
        this.scene.start('LobbyScene', { client: this.client, store: this.store })
      })
    } catch (err) {
      this.statusText.setText('连接失败，请确保服务端已启动')
      this.statusText.setColor('#ff4444')
    }
  }
}
