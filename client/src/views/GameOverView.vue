<template>
  <div class="gameover">
    <div class="panel">
      <div class="icon">{{ isWin ? '🏆' : '💀' }}</div>
      <h1 :class="isWin ? 'win' : 'lose'">
        {{ isWin ? '调查成功' : '调查失败' }}
      </h1>
      <p class="message">{{ message }}</p>

      <div v-if="campaignState" class="xp-summary">
        <h3>经验结算</h3>
        <p>获得经验: {{ campaignState.xp_earned }} XP</p>
        <p>已花费: {{ campaignState.xp_spent }} XP</p>
        <p>可用经验: {{ campaignState.xp }} XP</p>
      </div>

      <div class="actions">
        <button @click="backToLobby">返回大厅</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '../stores/game'

const router = useRouter()
const store = useGameStore()

const isWin = computed(() => store.gameOver?.type === 'win')
const message = computed(() => store.gameOver?.message || '游戏结束')
const campaignState = computed(() => store.campaignState)

function backToLobby() {
  store.reset()
  router.push('/')
}
</script>

<style scoped>
.gameover {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0a1a;
}
.panel {
  background: #1a1a2e;
  border: 2px solid #333344;
  border-radius: 12px;
  padding: 48px 64px;
  text-align: center;
  max-width: 500px;
}
.icon {
  font-size: 64px;
  margin-bottom: 16px;
}
h1 {
  font-size: 28px;
  margin-bottom: 12px;
}
h1.win { color: #c0a060; }
h1.lose { color: #e74c3c; }
.message {
  color: #aaa;
  font-size: 15px;
  margin-bottom: 24px;
  line-height: 1.5;
}
.xp-summary {
  background: #111122;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 24px;
  text-align: left;
}
.xp-summary h3 {
  color: #c0a060;
  font-size: 14px;
  margin-bottom: 8px;
}
.xp-summary p {
  color: #aaa;
  font-size: 13px;
  margin: 4px 0;
}
.actions {
  margin-top: 24px;
}
button {
  padding: 10px 32px;
  font-size: 16px;
  background: #2a2a4e;
  border: 1px solid #c0a060;
  color: #c0a060;
  border-radius: 6px;
}
button:hover {
  background: #3a3a6e;
}
</style>
