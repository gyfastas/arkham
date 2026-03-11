/** Phaser game bootstrap. */

import Phaser from 'phaser'
import { SocketClient } from './network/SocketClient'
import { GameStore } from './state/GameStore'
import { BootScene } from './scenes/BootScene'
import { LobbyScene } from './scenes/LobbyScene'
import { GameScene } from './scenes/GameScene'
import { GameOverScene } from './scenes/GameOverScene'

const client = new SocketClient()
const store = new GameStore()

const config: Phaser.Types.Core.GameConfig = {
  type: Phaser.AUTO,
  parent: 'game-container',
  width: 1280,
  height: 720,
  backgroundColor: '#0a0a1a',
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  scene: [BootScene, LobbyScene, GameScene, GameOverScene],
}

const game = new Phaser.Game(config)

// Pass shared instances to the first scene
game.scene.start('BootScene', { client, store })
