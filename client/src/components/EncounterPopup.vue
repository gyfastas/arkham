<script setup lang="ts">
import { watch, ref } from 'vue'
import type { EncounterCardDisplay } from '../state/types'
import { useGameStore } from '../stores/game'
import { localizeDisplayHtml, localizeDisplayText } from '../utils/displayText'

const props = defineProps<{ encounter: EncounterCardDisplay | null }>()
const store = useGameStore()

const emit = defineEmits<{
  dismiss: []
}>()

const visible = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

watch(() => props.encounter, (enc) => {
  if (timer) clearTimeout(timer)
  if (enc) {
    visible.value = true
    timer = setTimeout(() => {
      visible.value = false
      emit('dismiss')
    }, 4000)
  } else {
    visible.value = false
  }
})

function dismiss() {
  if (timer) clearTimeout(timer)
  visible.value = false
  emit('dismiss')
}

const TYPE_LABELS: Record<string, string> = {
  enemy: '敌人',
  treachery: '诡计',
}
const TYPE_LABELS_HANT: Record<string, string> = {
  enemy: '敵人',
  treachery: '詭計',
}
</script>

<template>
  <Teleport to="body">
    <Transition name="encounter">
      <div v-if="visible && encounter" class="encounter-overlay" @click.self="dismiss">
        <div class="encounter-card">
          <div class="encounter-type">{{ (store.language === 'zh-Hant' ? TYPE_LABELS_HANT : TYPE_LABELS)[encounter.type] || encounter.type }}</div>
          <div class="encounter-name">{{ localizeDisplayText(encounter.name_cn || encounter.name, store.language) }}</div>
          <div v-if="encounter.type === 'enemy'" class="encounter-stats">
            <span v-if="encounter.fight != null" class="stat" title="战斗">⚔ {{ encounter.fight }}</span>
            <span v-if="encounter.health != null" class="stat" title="生命">♥ {{ encounter.health }}</span>
            <span v-if="encounter.evade != null" class="stat" title="闪避">🏃 {{ encounter.evade }}</span>
            <span v-if="encounter.damage != null" class="stat dmg" title="伤害">🗡 {{ encounter.damage }}</span>
            <span v-if="encounter.horror != null" class="stat hor" title="恐惧">🧠 {{ encounter.horror }}</span>
          </div>
          <div v-if="encounter.traits && encounter.traits.length" class="encounter-traits">
            {{ encounter.traits.map(trait => localizeDisplayText(trait, store.language)).join(' · ') }}
          </div>
          <div v-if="encounter.text" class="encounter-text" v-html="localizeDisplayHtml(encounter.text, store.language)"></div>
          <button class="dismiss-btn" @click="dismiss">关闭</button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.encounter-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 900;
}
.encounter-card {
  background: #2a1a2a;
  border: 2px solid #9b59b6;
  border-radius: 10px;
  padding: 24px;
  max-width: 380px;
  width: 85%;
  text-align: center;
  box-shadow: 0 8px 32px rgba(155, 89, 182, 0.3);
}
.encounter-type {
  font-size: 11px;
  color: #9b59b6;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.encounter-name {
  font-size: 18px;
  font-weight: bold;
  color: #e0e0e0;
  margin-bottom: 8px;
}
.encounter-traits {
  font-size: 12px;
  color: #c0a060;
  font-style: italic;
  margin-bottom: 8px;
}
.encounter-stats {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin: 6px 0;
  font-size: 13px;
}

.encounter-stats .stat {
  color: #c0c0d8;
}

.encounter-stats .stat.dmg {
  color: #d98880;
}

.encounter-stats .stat.hor {
  color: #af7ac5;
}

.encounter-text {
  font-size: 13px;
  color: #ccc;
  line-height: 1.5;
  margin-bottom: 16px;
}
.dismiss-btn {
  padding: 6px 20px;
  border: 1px solid #9b59b6;
  border-radius: 4px;
  background: transparent;
  color: #9b59b6;
  cursor: pointer;
  font-size: 12px;
}
.dismiss-btn:hover {
  background: #9b59b6;
  color: #fff;
}

.encounter-enter-active { transition: opacity 0.3s, transform 0.3s; }
.encounter-leave-active { transition: opacity 0.2s, transform 0.2s; }
.encounter-enter-from { opacity: 0; transform: scale(0.8); }
.encounter-leave-to { opacity: 0; transform: scale(0.9); }
</style>
