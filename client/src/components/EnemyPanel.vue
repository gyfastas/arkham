<script setup lang="ts">
import type { EnemyDisplay } from '../state/types'

defineProps<{ enemies: EnemyDisplay[] }>()

const emit = defineEmits<{
  attack: [enemyInstanceId: string]
  evade: [enemyInstanceId: string]
  engage: [enemyInstanceId: string]
}>()
</script>

<template>
  <div class="enemy-panel">
    <div class="panel-title">敌人 ({{ enemies.length }})</div>
    <div class="enemy-list">
      <div
        v-for="enemy in enemies"
        :key="enemy.instance_id"
        class="enemy-card"
        :class="{ exhausted: enemy.exhausted }"
      >
        <div class="enemy-name">{{ enemy.name_cn || enemy.name }}</div>
        <div class="enemy-stats">
          <span class="fight" title="战斗">⚔{{ enemy.fight }}</span>
          <span class="health" title="生命">♥{{ enemy.health - enemy.current_damage }}/{{ enemy.health }}</span>
          <span class="evade-stat" title="闪避">🏃{{ enemy.evade }}</span>
        </div>
        <div class="enemy-threat">
          <span v-if="enemy.damage_dealt" class="dmg">伤害: {{ enemy.damage_dealt }}</span>
          <span v-if="enemy.horror_dealt" class="hor">恐惧: {{ enemy.horror_dealt }}</span>
        </div>
        <div v-if="enemy.engaged" class="engaged-badge">已交战</div>
        <div v-if="enemy.exhausted" class="exhausted-badge">已消耗</div>
        <div class="enemy-actions">
          <button class="btn-fight" @click="emit('attack', enemy.instance_id)">战斗</button>
          <button class="btn-evade" @click="emit('evade', enemy.instance_id)">闪避</button>
          <button
            v-if="!enemy.engaged"
            class="btn-engage"
            @click="emit('engage', enemy.instance_id)"
          >交战</button>
        </div>
      </div>
      <div v-if="!enemies.length" class="no-enemies">无敌人</div>
    </div>
  </div>
</template>

<style scoped>
.enemy-panel {
  display: flex;
  flex-direction: column;
}
.panel-title {
  padding: 8px 12px;
  font-weight: bold;
  font-size: 13px;
  color: #e74c3c;
  border-bottom: 1px solid #333344;
}
.enemy-list {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}
.enemy-card {
  background: #2a1a1a;
  border: 1px solid #553333;
  border-radius: 6px;
  padding: 8px;
  font-size: 12px;
}
.enemy-card.exhausted {
  opacity: 0.6;
}
.enemy-name {
  font-weight: bold;
  color: #e74c3c;
  margin-bottom: 4px;
}
.enemy-stats {
  display: flex;
  gap: 10px;
  margin-bottom: 4px;
  color: #e0e0e0;
}
.fight { color: #e67e22; }
.health { color: #e74c3c; }
.evade-stat { color: #2ecc71; }
.enemy-threat {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #aaa;
  margin-bottom: 4px;
}
.engaged-badge, .exhausted-badge {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-bottom: 4px;
  margin-right: 4px;
}
.engaged-badge {
  background: #553333;
  color: #e74c3c;
}
.exhausted-badge {
  background: #333344;
  color: #888;
}
.enemy-actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}
.enemy-actions button {
  flex: 1;
  padding: 4px 8px;
  border: 1px solid #555;
  border-radius: 4px;
  background: #1a1a2e;
  color: #e0e0e0;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-fight:hover { background: #e67e22; color: #000; }
.btn-evade:hover { background: #2ecc71; color: #000; }
.btn-engage:hover { background: #3498db; color: #000; }
.no-enemies {
  color: #555;
  font-style: italic;
  text-align: center;
  padding: 12px;
  font-size: 12px;
}
</style>
