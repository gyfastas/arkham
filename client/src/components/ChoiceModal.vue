<script setup lang="ts">
import type { PendingChoice } from '../state/types'
import { useGameStore } from '../stores/game'
import { localizeDisplayHtml, localizeDisplayText } from '../utils/displayText'

defineProps<{ choice: PendingChoice | null }>()
const store = useGameStore()

const emit = defineEmits<{
  choose: [optionId: string]
}>()
</script>

<template>
  <Teleport to="body">
    <div v-if="choice" class="modal-overlay">
      <div class="modal-content">
        <div class="modal-prompt" v-html="localizeDisplayHtml(choice.prompt, store.language)"></div>
        <div class="modal-options">
          <button
            v-for="opt in choice.options"
            :key="opt.id"
            class="option-btn"
            @click="emit('choose', opt.id)"
          >
            {{ localizeDisplayText(opt.label, store.language) }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: #1a1a2e;
  border: 2px solid #c0a060;
  border-radius: 10px;
  padding: 24px;
  max-width: 450px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
}
.modal-prompt {
  font-size: 15px;
  color: #e0e0e0;
  margin-bottom: 20px;
  text-align: center;
  line-height: 1.5;
}
.modal-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.option-btn {
  padding: 10px 16px;
  border: 1px solid #333344;
  border-radius: 6px;
  background: #2a2a44;
  color: #e0e0e0;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  text-align: left;
}
.option-btn:hover {
  background: #3a3a5e;
  border-color: #c0a060;
  color: #fff;
}
</style>
