import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { SocketClient } from './network/SocketClient'
import { SOCKET_KEY } from './composables/useSocket'
import { useGameStore } from './stores/game'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// Create and provide socket client
const client = new SocketClient()
app.provide(SOCKET_KEY, client)

// Wire socket events to store
const store = useGameStore()

client.connect().then(() => {
  store.connected = true
  store.playerId = (client as any)._playerId || ''
}).catch(() => {
  store.addToast('无法连接到服务器', 'error')
})

client.onStateUpdate = (state, events) => {
  store.updateState(state, events)
}
client.onActionResult = (result) => {
  store.lastActionResult = result
  if (!result.success) {
    store.addToast(result.message, 'error')
  }
  if (result.state) {
    store.updateState(result.state, result.events)
  }
}
client.onCardList = (cards, presets, deckReq, sigCards, weakCards) => {
  store.availableCards = cards
  store.deckPresets = presets
  store.deckRequirements = deckReq
  store.signatureCards = sigCards || []
  store.weaknessCards = weakCards || []
}
client.onInvestigatorDetail = (detail) => {
  store.investigatorDetail = detail
}
client.onCampaignState = (cs) => {
  store.campaignState = cs
}
client.onError = (err) => {
  store.addToast(err.message || '发生错误', 'error')
}
client.onDisconnect = () => {
  store.connected = false
}

app.mount('#app')
