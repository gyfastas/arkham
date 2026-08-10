<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useGameStore } from '../stores/game'
import type { OptionsData } from '../state/types'

const router = useRouter()
const client = useSocket()
const store = useGameStore()

const showOptions = ref(false)
const options = ref<OptionsData | null>(null)
const saveDirInput = ref('')
const applying = ref(false)

function openOptions() {
  showOptions.value = true
  client.getOptions()
}

function applySaveDir(dir: string) {
  applying.value = true
  client.setSaveDir(dir)
}

function handleOptions(data: OptionsData) {
  applying.value = false
  options.value = data
  saveDirInput.value = data.save_dir
}

function handleError(err: { message: string }) {
  applying.value = false
  store.addToast(err.message || '设置失败', 'error')
}

onMounted(() => {
  client.onOptions = handleOptions
  const prevErr = client.onError
  client.onError = (err) => {
    handleError(err)
    prevErr?.(err)
  }
})

onUnmounted(() => {
  if (client.onOptions === handleOptions) client.onOptions = null
})
</script>

<template>
  <div class="home">
    <div class="home-inner">
      <h1 class="title">诡镇奇谈</h1>
      <p class="subtitle">Arkham Horror: The Card Game</p>

      <div class="mode-cards">
        <div class="mode-card" @click="router.push('/quick')">
          <div class="mode-icon">⚡</div>
          <div class="mode-name">快速游戏</div>
          <div class="mode-desc">任选剧本，直接开局</div>
        </div>
        <div class="mode-card" @click="router.push('/campaign')">
          <div class="mode-icon">📖</div>
          <div class="mode-name">战役模式</div>
          <div class="mode-desc">选择战役与难度，从第一章开始，经验与创伤贯穿全程</div>
        </div>
        <div class="mode-card" @click="router.push('/quick?mode=multi')">
          <div class="mode-icon">👥</div>
          <div class="mode-name">联机合作</div>
          <div class="mode-desc">2-4 人合作：创建房间，或按房间 ID 加入队友的局</div>
        </div>
        <div class="mode-card options-card" @click="openOptions">
          <div class="mode-icon">⚙️</div>
          <div class="mode-name">选项</div>
          <div class="mode-desc">存档目录等设置</div>
        </div>
      </div>
    </div>

    <!-- 选项弹窗 -->
    <div v-if="showOptions" class="modal-overlay" @click.self="showOptions = false">
      <div class="options-modal">
        <div class="opt-title">选项</div>

        <div class="opt-section">
          <div class="opt-label">战役存档目录</div>
          <div class="opt-desc">
            当前：<code>{{ options?.save_dir || '加载中…' }}</code>
            <span v-if="options" class="opt-count">（{{ options.save_count }} 个存档）</span>
          </div>
          <input
            v-model="saveDirInput"
            class="opt-input"
            type="text"
            placeholder="留空则恢复默认目录"
            @keyup.enter="applySaveDir(saveDirInput)"
          />
          <div class="opt-btns">
            <button class="opt-btn" :disabled="applying" @click="applySaveDir(saveDirInput)">
              应用
            </button>
            <button
              v-if="options?.is_custom"
              class="opt-btn secondary"
              :disabled="applying"
              @click="applySaveDir('')"
            >
              恢复默认（{{ options?.default_save_dir }}）
            </button>
          </div>
          <div class="opt-hint">新目录立即生效；已有存档不会自动迁移，请手动移动旧目录中的 JSON 文件。</div>
        </div>

        <div class="opt-close-row">
          <button class="opt-btn secondary" @click="showOptions = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home {
  width: 100vw;
  height: 100vh;
  background: radial-gradient(ellipse at center, #10102a 0%, #06060f 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Noto Sans SC', sans-serif;
}

.home-inner {
  text-align: center;
}

.title {
  font-size: 56px;
  font-weight: 700;
  color: #c0a060;
  letter-spacing: 12px;
  margin: 0 0 8px;
  text-shadow: 0 0 30px rgba(192, 160, 96, 0.35);
}

.subtitle {
  color: #555;
  font-size: 14px;
  letter-spacing: 4px;
  margin: 0 0 56px;
}

.mode-cards {
  display: flex;
  gap: 24px;
  justify-content: center;
}

.mode-card {
  width: 240px;
  padding: 32px 24px;
  background: #12122a;
  border: 2px solid #2a2a4e;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-card:hover {
  border-color: #c0a060;
  transform: translateY(-4px);
  box-shadow: 0 8px 30px rgba(192, 160, 96, 0.15);
}

.mode-icon {
  font-size: 40px;
  margin-bottom: 14px;
}

.mode-name {
  font-size: 20px;
  font-weight: 600;
  color: #e0d0a0;
  margin-bottom: 8px;
}

.mode-desc {
  font-size: 13px;
  color: #777;
  line-height: 1.6;
}

.options-card {
  width: 180px;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.options-modal {
  background: #14142b;
  border: 1px solid #333355;
  border-radius: 10px;
  padding: 24px;
  width: 520px;
  max-width: 92vw;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.7);
  text-align: left;
}

.opt-title {
  font-size: 18px;
  font-weight: 600;
  color: #eee;
  margin-bottom: 18px;
}

.opt-section {
  margin-bottom: 20px;
}

.opt-label {
  font-size: 14px;
  color: #c0a060;
  margin-bottom: 6px;
}

.opt-desc {
  font-size: 12px;
  color: #999;
  margin-bottom: 10px;
  word-break: break-all;
}

.opt-desc code {
  color: #bbb;
  background: #0d0d20;
  padding: 2px 6px;
  border-radius: 4px;
}

.opt-count {
  color: #666;
}

.opt-input {
  width: 100%;
  box-sizing: border-box;
  background: #0d0d20;
  border: 1px solid #2a2a4e;
  color: #eee;
  padding: 8px 10px;
  border-radius: 4px;
  font-size: 13px;
  margin-bottom: 10px;
}

.opt-input:focus {
  outline: none;
  border-color: #4a4a8e;
}

.opt-btns {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.opt-btn {
  background: #27ae60;
  border: none;
  color: #fff;
  padding: 8px 18px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}

.opt-btn.secondary {
  background: #1a1a2e;
  border: 1px solid #333;
  color: #aaa;
}

.opt-btn:hover:not(:disabled) {
  filter: brightness(1.15);
}

.opt-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.opt-hint {
  margin-top: 8px;
  font-size: 11px;
  color: #666;
  line-height: 1.6;
}

.opt-close-row {
  display: flex;
  justify-content: flex-end;
}
</style>
