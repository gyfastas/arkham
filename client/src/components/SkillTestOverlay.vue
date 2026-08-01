<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { CardDisplay, CardInstanceDisplay, EnemyDisplay, SkillTestAnimation } from '../state/types'
import Card from './Card.vue'
import { useGameStore } from '../stores/game'
import { localizeDisplayText } from '../utils/displayText'

const props = defineProps<{
  test: SkillTestAnimation | null
  hand: CardDisplay[]
  assets: CardInstanceDisplay[]
  enemies: EnemyDisplay[]
  resources: number
  mode: 'commit' | 'spinning'
}>()

const emit = defineEmits<{
  roll: [payload: { committed: string[]; effectCardIds: string[]; weaponInstanceId?: string }]
  activateCard: [instanceId: string, activationId: string, targetInstanceId?: string]
  complete: []
}>()
const store = useGameStore()

const FALLBACK_TOKENS = [
  '+1', '0', '0', '-1', '-1', '-1', '-2', '-2', '-3', '-4',
  'skull', 'skull', 'cultist', 'tablet', 'auto_fail', 'elder_sign',
]

const TOKEN_LABELS: Record<string, string> = {
  '+1': '+1', '0': '0', '-1': '-1', '-2': '-2', '-3': '-3', '-4': '-4',
  '-5': '-5', '-6': '-6', '-7': '-7', '-8': '-8',
  skull: '骷髅', cultist: '邪教徒', tablet: '石板', elder_thing: '远古者',
  auto_fail: '自动失败', elder_sign: '古老印记', bless: '祝福', curse: '诅咒', frost: '霜冻',
}

const TOKEN_CLASSES: Record<string, string> = {
  skull: 'symbol-skull', cultist: 'symbol-cultist', tablet: 'symbol-tablet',
  elder_thing: 'symbol-elder', auto_fail: 'symbol-fail', elder_sign: 'symbol-elder-sign',
  bless: 'symbol-bless', curse: 'symbol-curse', frost: 'symbol-frost',
}

const SKILL_LABELS: Record<string, string> = {
  willpower: '意志', intellect: '智力', combat: '战斗', agility: '敏捷', wild: '万能',
}

const selected = ref<string[]>([])
const effectSelected = ref<string[]>([])
const selectedWeaponId = ref<string | null>(null)
const selectedActivationTargetId = ref<string | null>(null)
const activeIndex = ref(0)
const spinning = ref(false)
const resultVisible = ref(false)
const spinStarted = ref(false)
let spinTimer: ReturnType<typeof setTimeout> | null = null
const SPIN_DURATION = 3000

const tokens = computed(() => {
  const source = props.test?.possible_tokens?.length
    ? props.test.possible_tokens
    : FALLBACK_TOKENS
  const target = props.test?.token
  return target && !source.includes(target) ? [...source, target] : [...source]
})

const targetIndex = computed(() => {
  const target = props.test?.token
  const index = target ? tokens.value.indexOf(target) : -1
  return index >= 0 ? index : 0
})

const wheelTokens = computed(() => {
  const count = tokens.value.length || 1
  return tokens.value.map((token, index) => {
    const angle = (360 / count) * index - 90
    return {
      token,
      index,
      label: TOKEN_LABELS[token] || token,
      className: TOKEN_CLASSES[token] || '',
      style: {
        transform: `rotate(${angle}deg) translateY(-132px) rotate(${-angle}deg)`,
      },
    }
  })
})

const skillLabel = computed(() => SKILL_LABELS[props.test?.skill_type || ''] || props.test?.skill_type || '技能')
const eligibleCards = computed(() => props.hand.filter(card => {
  const icons = card.skill_icons || {}
  const skill = props.test?.skill_type || ''
  return (icons[skill] || 0) > 0 || (icons.wild || 0) > 0
}))

const weapons = computed(() => props.test?.skill_type === 'combat'
  ? props.assets.filter(asset => (asset.traits || []).some(trait => trait.toLowerCase() === 'weapon'))
  : [])

const combatSupports = computed(() => props.test?.skill_type === 'combat'
  ? props.assets.filter(asset => !weapons.value.some(weapon => weapon.instance_id === asset.instance_id)
      && (asset.activations || []).some(activation => activation.timing === 'combat'))
  : [])
const targetEnemies = computed(() => props.enemies.filter(enemy => enemy.engaged))

function cardIcons(card: CardDisplay): number {
  const icons = card.skill_icons || {}
  const skill = props.test?.skill_type || ''
  return (icons[skill] || 0) + (icons.wild || 0)
}

function cardKey(card: CardDisplay, index: number): string {
  return `${card.id}::${index}`
}

const selectedCards = computed(() => eligibleCards.value
  .filter((card, index) => selected.value.includes(cardKey(card, index))))

const selectedEffectCards = computed(() => eligibleCards.value
  .filter((card, index) => effectSelected.value.includes(cardKey(card, index))))

const selectedEffectCost = computed(() => selectedEffectCards.value
  .reduce((sum, card) => sum + (card.commit_effect_cost || 0), 0))

const selectedIcons = computed(() => selectedCards.value
  .reduce((sum, card) => sum + cardIcons(card), 0))

const selectedWeapon = computed(() => weapons.value.find(weapon => weapon.instance_id === selectedWeaponId.value) || null)
const weaponPreviewBonus = computed(() => {
  const id = selectedWeapon.value?.id
  return id === 'machete_lv0' || id === '45_automatic_lv0' ? 1 : 0
})

const baseValue = computed(() => props.test?.base_skill ?? 0)
const committedValue = computed(() => props.mode === 'commit'
  ? selectedIcons.value
  : props.test?.committed_icons ?? selectedIcons.value)
const currentValue = computed(() => baseValue.value + committedValue.value + weaponPreviewBonus.value)
const finalValue = computed(() => props.test?.modified_skill ?? currentValue.value)
const targetValue = computed(() => props.test?.difficulty ?? 0)
const activeToken = computed(() => tokens.value[activeIndex.value] || '')

function tokenModifier(token: string): number {
  const value = Number(token)
  return Number.isFinite(value) ? value : 0
}

const successPercentage = computed(() => {
  if (targetValue.value <= 0) return 100
  const possible = tokens.value.length ? tokens.value : FALLBACK_TOKENS
  const successful = possible.filter(token =>
    token !== 'auto_fail' && currentValue.value + tokenModifier(token) >= targetValue.value,
  ).length
  return Math.round((successful / possible.length) * 100)
})

function clearTimer() {
  if (spinTimer) clearTimeout(spinTimer)
  spinTimer = null
}

function toggleCard(card: CardDisplay, index: number) {
  if (props.mode !== 'commit' || spinStarted.value) return
  const key = cardKey(card, index)
  const selectedIndex = selected.value.indexOf(key)
  if (selectedIndex >= 0) {
    selected.value.splice(selectedIndex, 1)
    const effectIndex = effectSelected.value.indexOf(key)
    if (effectIndex >= 0) effectSelected.value.splice(effectIndex, 1)
  } else {
    selected.value.push(key)
  }
}

function canEnableEffect(card: CardDisplay, index: number): boolean {
  const key = cardKey(card, index)
  return Boolean(
    card.has_commit_effect
    && selected.value.includes(key)
    && (effectSelected.value.includes(key)
      || props.resources >= selectedEffectCost.value + (card.commit_effect_cost || 0)),
  )
}

function toggleEffect(card: CardDisplay, index: number) {
  if (props.mode !== 'commit' || spinStarted.value || !card.has_commit_effect) return
  const key = cardKey(card, index)
  if (!selected.value.includes(key)) return
  const effectIndex = effectSelected.value.indexOf(key)
  if (effectIndex >= 0) {
    effectSelected.value.splice(effectIndex, 1)
  } else if (canEnableEffect(card, index)) {
    effectSelected.value.push(key)
  }
}

function toggleWeapon(weapon: CardInstanceDisplay) {
  if (props.mode !== 'commit' || spinStarted.value) return
  selectedWeaponId.value = selectedWeaponId.value === weapon.instance_id ? null : weapon.instance_id
}

function canUseCombatActivation(asset: CardInstanceDisplay, activation: NonNullable<CardInstanceDisplay['activations']>[number]): boolean {
  if (asset.exhausted) return false
  if (activation.resource_cost && props.resources < activation.resource_cost) return false
  if (asset.uses && !Object.values(asset.uses).some(value => value > 0)) return false
  return true
}

function needsActivationTarget(activation: NonNullable<CardInstanceDisplay['activations']>[number]): boolean {
  return activation.target === 'enemy' && targetEnemies.value.length > 1
}

function useCombatActivation(asset: CardInstanceDisplay, activation: NonNullable<CardInstanceDisplay['activations']>[number]) {
  if (!canUseCombatActivation(asset, activation)) return
  if (needsActivationTarget(activation) && !selectedActivationTargetId.value) return
  emit('activateCard', asset.instance_id, activation.id, selectedActivationTargetId.value || undefined)
}

function beginSpin() {
  if (!props.test || spinStarted.value) return
  spinStarted.value = true
  spinning.value = true
  resultVisible.value = false
  const count = Math.max(tokens.value.length, 1)
  activeIndex.value = Math.floor(Math.random() * count)

  const startedAt = performance.now()
  const step = () => {
    const elapsed = performance.now() - startedAt
    if (elapsed >= SPIN_DURATION) {
      activeIndex.value = targetIndex.value
      spinning.value = false
      resultVisible.value = true
      spinTimer = null
      return
    }

    // 依次点亮每个结果：开始快速切换，随后逐渐减速。
    activeIndex.value = (activeIndex.value + 1) % count
    const progress = elapsed / SPIN_DURATION
    const delay = 45 + Math.pow(progress, 3) * 360
    spinTimer = setTimeout(step, delay)
  }

  step()
}

function startSpin() {
  if (props.mode !== 'commit' || spinStarted.value) return
  beginSpin()
  emit('roll', {
    committed: selectedCards.value.map(card => card.id),
    effectCardIds: selectedEffectCards.value.map(card => card.id),
    weaponInstanceId: selectedWeaponId.value || undefined,
  })
}

function confirmResult() {
  if (resultVisible.value && !spinning.value) emit('complete')
}

watch(() => Boolean(props.test), (hasTest) => {
  clearTimer()
  selected.value = []
  effectSelected.value = []
  selectedWeaponId.value = null
  selectedActivationTargetId.value = null
  spinStarted.value = false
  spinning.value = false
  resultVisible.value = false
  activeIndex.value = hasTest ? Math.floor(Math.random() * Math.max(tokens.value.length, 1)) : 0
}, { immediate: true })

watch(() => props.mode, mode => {
  if (mode === 'spinning' && !spinStarted.value) beginSpin()
  if (mode === 'commit' && !spinStarted.value) resultVisible.value = false
})

onBeforeUnmount(clearTimer)
</script>

<template>
  <div v-if="test" class="skill-overlay">
    <div class="skill-panel" :class="{ resolved: resultVisible }">
      <div class="skill-heading">
        <span class="heading-kicker">技能检定</span>
        <span class="heading-title">{{ skillLabel }}</span>
        <span class="heading-sub">混沌袋揭示</span>
      </div>

      <div class="wheel-stage">
        <div class="wheel-glow"></div>
        <div class="wheel-ring">
          <div
            v-for="item in wheelTokens"
            :key="`${item.token}-${item.index}`"
            class="wheel-token"
            :class="[item.className, { active: item.index === activeIndex }]"
            :style="item.style"
          >
            {{ item.label }}
          </div>
        </div>
        <div class="wheel-pointer"></div>
        <div class="wheel-center">
          <div class="center-token" :class="TOKEN_CLASSES[activeToken] || ''">
            {{ TOKEN_LABELS[activeToken] || activeToken || '?' }}
          </div>
          <div class="center-caption">{{ spinning ? '转动中…' : resultVisible ? '已揭示' : '等待投掷' }}</div>
        </div>
      </div>

      <div class="value-strip">
        <div class="value-card investigator-value">
          <div class="value-label">你的数值</div>
          <div class="value-number">{{ resultVisible ? finalValue : currentValue }}</div>
          <div class="value-detail">
            基础 {{ baseValue }}
            <span v-if="committedValue">+ 投入 {{ committedValue }}</span>
            <span v-if="resultVisible && test.token_modifier">{{ test.token_modifier >= 0 ? '+' : '' }}{{ test.token_modifier }}</span>
          </div>
        </div>
        <div class="versus-column">
          <div class="success-probability">成功率 {{ successPercentage }}%</div>
          <div class="versus">VS</div>
        </div>
        <div class="value-card target-value">
          <div class="value-label">目标数值</div>
          <div class="value-number">{{ targetValue }}</div>
          <div class="value-detail">{{ test.target_label || '检定难度' }}</div>
        </div>
      </div>

      <div v-if="mode === 'commit'" class="commit-area">
        <div class="commit-heading">可投入的牌（点击选择，再次点击取消）</div>
        <div v-if="eligibleCards.length" class="commit-cards">
          <div
            v-for="(card, index) in eligibleCards"
            :key="cardKey(card, index)"
            class="commit-card"
            :class="{ selected: selected.includes(cardKey(card, index)) }"
            role="button"
            tabindex="0"
            @click="toggleCard(card, index)"
          >
            <span class="card-name">{{ localizeDisplayText(card.name_cn || card.name, store.language) }}</span>
            <span class="card-icons">+{{ cardIcons(card) }}</span>
            <span v-if="card.text_cn" class="card-text">{{ localizeDisplayText(card.text_cn, store.language) }}</span>
            <span v-if="selected.includes(cardKey(card, index))" class="card-check">✓</span>
            <div v-if="selected.includes(cardKey(card, index)) && card.has_commit_effect" class="effect-choice">
              <button
                type="button"
                class="effect-toggle"
                :class="{ enabled: effectSelected.includes(cardKey(card, index)) }"
                :disabled="!canEnableEffect(card, index) && !effectSelected.includes(cardKey(card, index))"
                :title="!canEnableEffect(card, index) && !effectSelected.includes(cardKey(card, index)) ? '费用不足，仍可只作为普通投入牌' : ''"
                @click.stop="toggleEffect(card, index)"
              >
                {{ effectSelected.includes(cardKey(card, index)) ? '已启用效果' : '启用效果' }}
                <span v-if="card.commit_effect_cost">（-{{ card.commit_effect_cost }}资源）</span>
              </button>
              <span v-if="!canEnableEffect(card, index) && !effectSelected.includes(cardKey(card, index))" class="effect-unavailable">费用不足</span>
              <span class="effect-label">{{ card.commit_effect_label || '成功后触发牌面效果' }}</span>
            </div>
          </div>
        </div>
        <div v-else class="commit-empty">手中没有可投入的技能牌</div>

        <template v-if="weapons.length">
          <div class="commit-heading weapon-heading">本次战斗使用的武器（可选）</div>
          <div class="weapon-cards">
            <button
              v-for="weapon in weapons"
              :key="weapon.instance_id"
              type="button"
              class="weapon-choice"
              :class="{ selected: selectedWeaponId === weapon.instance_id }"
              @click="toggleWeapon(weapon)"
            >
              <Card :card="weapon" />
              <span v-if="selectedWeaponId === weapon.instance_id" class="weapon-check">✓ 已选择</span>
            </button>
          </div>
        </template>

        <template v-if="combatSupports.length">
          <div class="commit-heading support-heading">战斗中可主动使用的支援</div>
          <div class="support-cards">
            <div v-for="support in combatSupports" :key="support.instance_id" class="support-choice">
              <Card :card="support" />
              <template v-for="act in (support.activations || []).filter(item => item.timing === 'combat')" :key="act.id">
                <div v-if="act.target === 'enemy' && targetEnemies.length > 1" class="activation-targets">
                  <button
                    v-for="enemy in targetEnemies"
                    :key="enemy.instance_id"
                    type="button"
                    class="target-button"
                    :class="{ selected: selectedActivationTargetId === enemy.instance_id }"
                    @click.stop="selectedActivationTargetId = enemy.instance_id"
                  >{{ localizeDisplayText(enemy.name_cn || enemy.name, store.language) }}</button>
                </div>
                <button
                  type="button"
                  class="support-use-button"
                  :disabled="!canUseCombatActivation(support, act) || (needsActivationTarget(act) && !selectedActivationTargetId)"
                  @click.stop="useCombatActivation(support, act)"
                >
                  {{ canUseCombatActivation(support, act) ? `使用：${localizeDisplayText(act.label, store.language)}` : (act.resource_cost ? `费用不足（需要${act.resource_cost}资源）` : '已使用') }}
                </button>
              </template>
            </div>
          </div>
        </template>
      </div>

      <div v-if="resultVisible" class="result-banner" :class="test.success ? 'success' : 'failure'">
        <span class="result-mark">{{ test.success ? '✓' : '✕' }}</span>
        <span>{{ test.success ? '检定成功' : (test.auto_fail ? '自动失败' : '检定失败') }}</span>
        <span v-if="test.rexs_curse_redrawn_token" class="result-note">诅咒强制重抽</span>
        <span class="result-score">{{ finalValue }} / {{ targetValue }}</span>
      </div>
      <div v-else-if="spinning" class="result-hint">混沌袋正在决定命运…</div>
      <div v-else class="result-hint">请先选择投入牌，然后点击投掷</div>

      <div class="overlay-actions">
        <button
          v-if="mode === 'commit' && !spinStarted"
          class="overlay-button roll-button"
          type="button"
          @click="startSpin"
        >
          投掷
        </button>
        <button
          v-else-if="resultVisible"
          class="overlay-button confirm-button"
          type="button"
          @click="confirmResult"
        >
          确认
        </button>
        <button v-else class="overlay-button roll-button" type="button" disabled>转动中…</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.skill-overlay { position: fixed; inset: 0; z-index: 2000; display: flex; align-items: center; justify-content: center; padding: 20px; background: rgba(3, 4, 15, 0.92); }
.skill-panel { position: relative; width: min(900px, 96vw); max-height: 94vh; padding: 22px 28px 24px; overflow-y: auto; border: 1px solid #5c527e; border-radius: 18px; background: radial-gradient(circle at 50% 35%, #252347 0%, #15152c 48%, #0d0d1d 100%); box-shadow: 0 0 36px rgba(99, 77, 190, .18), 0 14px 34px rgba(0, 0, 0, .55); contain: layout paint; }
.skill-heading { display: flex; align-items: baseline; gap: 10px; border-bottom: 1px solid rgba(140, 125, 184, .25); padding-bottom: 12px; }
.heading-kicker, .heading-sub { color: #938ba9; font-size: 12px; }
.heading-title { color: #f3e7b2; font-size: 23px; font-weight: 700; }
.wheel-stage { position: relative; height: 300px; margin: 10px auto 0; }
.wheel-glow { position: absolute; top: 50%; left: 50%; width: 265px; height: 265px; border-radius: 50%; transform: translate(-50%, -50%); background: rgba(118, 92, 220, .11); box-shadow: 0 0 30px rgba(106, 82, 210, .16); }
.wheel-ring { position: absolute; top: 50%; left: 50%; width: 280px; height: 280px; border: 1px solid #665a91; border-radius: 50%; transform: translate(-50%, -50%); box-shadow: inset 0 0 18px rgba(120, 100, 205, .14), 0 0 12px rgba(120, 100, 205, .15); }
.wheel-ring::before, .wheel-ring::after { content: ''; position: absolute; inset: 14px; border: 1px dashed rgba(180, 166, 220, .3); border-radius: 50%; }
.wheel-ring::after { inset: 48px; border-style: solid; border-color: rgba(180, 166, 220, .14); }
.wheel-token { position: absolute; top: calc(50% - 17px); left: calc(50% - 31px); width: 62px; padding: 7px 2px; border: 1px solid #4d4770; border-radius: 15px; background: #1a1932; color: #bcb7d0; font-size: 11px; text-align: center; transition: color .12s, border-color .12s, background .12s, box-shadow .12s; }
.wheel-token.active { z-index: 2; border-color: #f4d36e; background: #5d4777; color: #fff9dd; box-shadow: 0 0 20px rgba(244, 211, 110, .8); }
.symbol-fail { color: #ff847c; } .symbol-elder-sign, .symbol-bless { color: #79dcad; } .symbol-skull, .symbol-cultist, .symbol-elder { color: #e2a2ed; }
.wheel-pointer { position: absolute; top: calc(50% - 148px); left: calc(50% - 8px); width: 0; height: 0; border-right: 8px solid transparent; border-bottom: 18px solid #f4d36e; border-left: 8px solid transparent; filter: drop-shadow(0 0 5px rgba(244, 211, 110, .8)); }
.wheel-center { position: absolute; top: 50%; left: 50%; display: flex; width: 108px; height: 108px; align-items: center; justify-content: center; flex-direction: column; border: 2px solid #8b78bd; border-radius: 50%; background: #121126; transform: translate(-50%, -50%); box-shadow: 0 0 30px rgba(135, 107, 225, .28); }
.center-token { color: #f8eab1; font-size: 19px; font-weight: 700; text-align: center; } .center-caption { margin-top: 5px; color: #8f88a7; font-size: 11px; }
.value-strip { display: grid; grid-template-columns: 1fr auto 1fr; gap: 14px; align-items: center; }
.value-card { min-height: 78px; padding: 10px 14px; border: 1px solid #413e61; border-radius: 10px; background: rgba(15, 15, 32, .78); }
.investigator-value { border-color: #527da0; } .target-value { border-color: #a27355; }
.value-label { color: #aaa5bd; font-size: 12px; } .value-number { margin-top: 2px; color: #f4d36e; font-size: 30px; font-weight: 800; line-height: 1; } .value-detail { margin-top: 6px; color: #817c94; font-size: 11px; }
.versus-column { display: flex; align-items: center; flex-direction: column; gap: 8px; } .versus { color: #887ea3; font-size: 13px; font-weight: 700; } .success-probability { color: #89d7ad; font-size: 13px; font-weight: 700; white-space: nowrap; }
.commit-area { margin-top: 16px; padding-top: 14px; border-top: 1px solid rgba(140, 125, 184, .25); }
.commit-heading { margin-bottom: 10px; color: #d7c98e; font-size: 13px; text-align: center; }
.commit-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 9px; }
.commit-card { position: relative; display: flex; min-height: 78px; padding: 10px 12px; align-items: flex-start; flex-direction: column; border: 2px solid #424064; border-radius: 9px; background: rgba(20, 20, 42, .9); color: #e7e3f0; cursor: pointer; text-align: left; transition: border-color .15s, background .15s, box-shadow .15s; }
.commit-card:hover { border-color: #8277ae; } .commit-card.selected { border-color: #55d68b; background: rgba(35, 104, 67, .34); box-shadow: 0 0 14px rgba(85, 214, 139, .25); }
.card-name { padding-right: 20px; font-size: 13px; font-weight: 700; } .card-icons { margin-top: 5px; color: #9ee5bb; font-size: 12px; } .card-text { display: -webkit-box; margin-top: 5px; overflow: hidden; color: #9a96aa; font-size: 11px; line-height: 1.35; -webkit-box-orient: vertical; -webkit-line-clamp: 2; } .card-check { position: absolute; top: 7px; right: 9px; color: #55d68b; font-size: 18px; font-weight: 800; } .commit-empty { padding: 18px 0; color: #8d879e; text-align: center; }
.effect-choice { display: flex; width: 100%; margin-top: 7px; align-items: center; flex-wrap: wrap; gap: 4px 6px; }
.effect-toggle { padding: 3px 6px; border: 1px solid #7c6b42; border-radius: 4px; background: rgba(92, 72, 35, .45); color: #f0d88b; cursor: pointer; font-size: 10px; }
.effect-toggle:hover:not(:disabled), .effect-toggle.enabled { border-color: #55d68b; background: rgba(35, 104, 67, .6); color: #d9ffe5; }
.effect-toggle:disabled { cursor: not-allowed; opacity: .6; }
.effect-unavailable { color: #ff9a9a; font-size: 10px; }
.effect-label { width: 100%; color: #aaa4ba; font-size: 10px; line-height: 1.3; }
.weapon-heading { margin-top: 14px; color: #e4b86b; }
.weapon-cards { display: flex; flex-wrap: wrap; gap: 9px; }
.weapon-choice { position: relative; padding: 3px; border: 2px solid #66553c; border-radius: 9px; background: rgba(37, 31, 25, .72); cursor: pointer; }
.weapon-choice :deep(.card) { width: 140px; }
.weapon-choice:hover { border-color: #d4a017; }
.weapon-choice.selected { border-color: #55d68b; background: rgba(35, 104, 67, .34); box-shadow: 0 0 14px rgba(85, 214, 139, .25); }
.weapon-check { position: absolute; right: 7px; bottom: 7px; padding: 2px 5px; border-radius: 4px; background: #237244; color: #d9ffe5; font-size: 10px; }
.support-heading { margin-top: 14px; color: #8fc5e7; }
.support-cards { display: flex; flex-wrap: wrap; gap: 9px; }
.support-choice { padding: 3px; border: 2px solid #46627c; border-radius: 9px; background: rgba(25, 38, 52, .72); }
.support-choice :deep(.card) { width: 140px; }
.support-use-button { display: block; width: 100%; margin-top: 4px; padding: 5px 7px; border: 1px solid #4a6a9a; border-radius: 5px; background: #2a3a52; color: #b8d4f0; cursor: pointer; font-size: 10px; text-align: left; }
.support-use-button:hover { border-color: #86b6e5; background: #35486a; }
.support-use-button:disabled { border-color: #555; background: #292936; color: #777; cursor: not-allowed; }
.activation-targets { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 5px; }
.target-button { padding: 3px 5px; border: 1px solid #6d5878; border-radius: 4px; background: #241b35; color: #d9c6e6; cursor: pointer; font-size: 9px; }
.target-button.selected { border-color: #55d68b; background: #275d43; color: #e4ffec; }
.result-banner { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 18px; padding: 12px; border-radius: 9px; font-size: 19px; font-weight: 700; animation: result-in .35s ease-out; } .result-banner.success { border: 1px solid #4ca874; background: rgba(35, 106, 69, .32); color: #aaf0c7; } .result-banner.failure { border: 1px solid #b45d62; background: rgba(126, 38, 50, .32); color: #ffb4b4; } .result-mark { font-size: 25px; } .result-note { color: #f3d17d; font-size: 12px; font-weight: 600; } .result-score { color: #fff1bf; font-size: 14px; } .result-hint { margin-top: 14px; color: #8d87a4; font-size: 13px; text-align: center; }
.overlay-actions { display: flex; justify-content: center; margin-top: 16px; } .overlay-button { min-width: 150px; padding: 10px 28px; border: 1px solid #8e7540; border-radius: 8px; background: linear-gradient(180deg, #6e5733, #45351f); color: #fff1bf; cursor: pointer; font-size: 16px; font-weight: 700; transition: border-color .2s, box-shadow .2s, transform .2s; } .overlay-button:hover:not(:disabled) { border-color: #f4d36e; box-shadow: 0 0 18px rgba(244, 211, 110, .35); transform: translateY(-1px); } .overlay-button:disabled { cursor: wait; opacity: .65; } .confirm-button { border-color: #5fae83; background: linear-gradient(180deg, #356b50, #244735); color: #d5ffe4; }
@keyframes result-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
@media (max-width: 600px) { .skill-panel { padding: 16px; } .wheel-stage { height: 280px; } .wheel-ring { transform: translate(-50%, -50%) scale(.82); } .wheel-glow { transform: translate(-50%, -50%) scale(.82); } .wheel-pointer { transform: scale(.82); transform-origin: top center; } .value-strip { gap: 7px; } .value-card { padding: 8px; } .value-number { font-size: 25px; } }
</style>
