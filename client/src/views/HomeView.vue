<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
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
</style>
