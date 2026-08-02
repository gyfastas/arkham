<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useGameStore } from '../stores/game'
import { localizeDisplayText } from '../utils/displayText'

const props = defineProps<{ log: string[] }>()
const store = useGameStore()

const container = ref<HTMLDivElement | null>(null)

watch(() => props.log.length, async () => {
  await nextTick()
  if (container.value) {
    container.value.scrollTop = container.value.scrollHeight
  }
})
</script>

<template>
  <div class="log-panel">
    <div class="log-title">{{ store.language === 'zh-Hant' ? '行動日誌' : '行动日志' }}</div>
    <div ref="container" class="log-content">
      <div v-for="(entry, i) in log" :key="i" class="log-entry">
        {{ localizeDisplayText(entry, store.language) }}
      </div>
      <div v-if="!log.length" class="log-empty">{{ store.language === 'zh-Hant' ? '暫無日誌' : '暂无日志' }}</div>
    </div>
  </div>
</template>

<style scoped>
.log-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a2e;
  border-right: 1px solid #333344;
}
.log-title {
  padding: 8px 12px;
  font-weight: bold;
  font-size: 13px;
  color: #c0a060;
  border-bottom: 1px solid #333344;
}
.log-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  font-size: 12px;
  color: #ccc;
  line-height: 1.5;
}
.log-entry {
  padding: 2px 0;
  border-bottom: 1px solid #1e1e36;
}
.log-empty {
  color: #555;
  font-style: italic;
  text-align: center;
  padding: 16px;
}
</style>
