<script setup lang="ts">
import { computed } from 'vue'
import type { CardInstanceDisplay, SlotSummary } from '../state/types'
import { useGameStore } from '../stores/game'
import Card from './Card.vue'
import { localizeDisplayText } from '../utils/displayText'

const props = defineProps<{
  assets: CardInstanceDisplay[]
  threatCards?: CardInstanceDisplay[]
  slotSummary?: SlotSummary[]
}>()

const emit = defineEmits<{
  activate: [instanceId: string]
  activateCard: [instanceId: string, activationId: string]
}>()

const store = useGameStore()

const SLOT_GROUPS = [
  { key: 'hand', slot: 'hand', limit: 2, cn: '手部装备', hant: '手部裝備', detailCn: '手部槽位', detailHant: '手部槽位', emptyCn: '手部空位', emptyHant: '手部空位' },
  { key: 'accessory', slot: 'accessory', limit: 1, cn: '饰品', hant: '飾品', detailCn: '饰品槽位', detailHant: '飾品槽位', emptyCn: '饰品空位', emptyHant: '飾品空位' },
  { key: 'body', slot: 'body', limit: 1, cn: '身体', hant: '身體', detailCn: '身体槽位', detailHant: '身體槽位', emptyCn: '身体空位', emptyHant: '身體空位' },
  { key: 'ally', slot: 'ally', limit: 1, cn: '盟友', hant: '盟友', detailCn: '盟友槽位', detailHant: '盟友槽位', emptyCn: '盟友空位', emptyHant: '盟友空位' },
  { key: 'arcane', slot: 'arcane', limit: 2, cn: '奥秘装备', hant: '奧秘裝備', detailCn: '奥秘槽位', detailHant: '奧秘槽位', emptyCn: '奥秘空位', emptyHant: '奧秘空位' },
  { key: 'tarot', slot: 'tarot', limit: 1, cn: '塔罗', hant: '塔羅', detailCn: '塔罗槽位', detailHant: '塔羅槽位', emptyCn: '塔罗空位', emptyHant: '塔羅空位' },
] as const

type SlotGroup = typeof SLOT_GROUPS[number]
type SlotItem =
  | { kind: 'asset'; asset: CardInstanceDisplay; span: number }
  | { kind: 'empty'; index: number }

function slotSummaryFor(type: string): SlotSummary | undefined {
  return props.slotSummary?.find(item => item.type === type)
}

function groupLimit(group: SlotGroup): number {
  return slotSummaryFor(group.slot)?.limit ?? group.limit
}

function groupUsed(group: SlotGroup): number {
  return slotSummaryFor(group.slot)?.used ?? props.assets.reduce(
    (total, asset) => total + (asset.slots || []).filter(slot => slot === group.slot).length,
    0,
  )
}

function assetsForGroup(group: SlotGroup): CardInstanceDisplay[] {
  return props.assets.filter(asset => (asset.slots || []).includes(group.slot))
}

function slotItems(group: SlotGroup): SlotItem[] {
  const limit = groupLimit(group)
  const occupied = Array.from({ length: limit }, () => false)
  const items: SlotItem[] = []

  for (const asset of assetsForGroup(group)) {
    const requestedSpan = Math.max(1, (asset.slots || []).filter(slot => slot === group.slot).length)
    let start = -1
    for (let i = 0; i <= limit - requestedSpan; i += 1) {
      if (occupied.slice(i, i + requestedSpan).every(value => !value)) {
        start = i
        break
      }
    }
    if (start < 0) {
      start = occupied.findIndex(value => !value)
      if (start < 0) continue
    }
    const span = Math.min(requestedSpan, limit - start)
    for (let i = start; i < start + span; i += 1) occupied[i] = true
    items.push({ kind: 'asset', asset, span })
  }

  occupied.forEach((isOccupied, index) => {
    if (!isOccupied) items.push({ kind: 'empty', index })
  })
  return items
}

function unlimitedAssets(): CardInstanceDisplay[] {
  return props.assets.filter(asset => !(asset.slots || []).length)
}

function isActivationAvailable(asset: CardInstanceDisplay): boolean {
  if (asset.exhausted) return false
  if (!asset.uses) return true
  return Object.values(asset.uses).some(value => value > 0)
}

function hasWeaponTrait(asset: CardInstanceDisplay): boolean {
  return (asset.traits || []).some(trait => {
    const normalized = trait.toLowerCase()
        return normalized.includes('weapon') || trait.includes('武器')
  })
}

function shouldShowPassiveStatus(asset: CardInstanceDisplay): boolean {
  return !hasWeaponTrait(asset)
}

function localized(value: string): string {
  return localizeDisplayText(value, store.language)
}

function groupLabel(group: SlotGroup): string {
  return store.language === 'zh-Hant' ? group.hant : group.cn
}

function groupDetail(group: SlotGroup): string {
  return store.language === 'zh-Hant' ? group.detailHant : group.detailCn
}

function emptyLabel(group: SlotGroup): string {
  return store.language === 'zh-Hant' ? group.emptyHant : group.emptyCn
}

function useLabel(): string {
  return '使用'
}

function usedLabel(): string {
  return store.language === 'zh-Hant' ? '已使用' : '已使用'
}

const slotGroups = computed(() => SLOT_GROUPS.map(group => ({
  ...group,
  items: slotItems(group),
  limit: groupLimit(group),
  used: groupUsed(group),
})))

const unlimited = computed(() => unlimitedAssets())
</script>

<template>
  <div class="play-area">
    <div v-if="threatCards && threatCards.length" class="support-section threat-section">
      <div class="play-label threat-label">{{ store.language === 'zh-Hant' ? '威脅區' : '威胁区' }}（{{ threatCards.length }}）</div>
      <div class="compact-row">
        <div v-for="card in threatCards" :key="card.instance_id" class="compact-item threat-item" :class="{ disabled: !isActivationAvailable(card) }">
          <Card :card="card" small />
          <div v-if="card.activations?.length" class="compact-actions">
            <button
              v-for="act in card.activations"
              :key="act.id"
              class="act-btn"
              :class="{ disabled: !isActivationAvailable(card) }"
              :disabled="!isActivationAvailable(card)"
              type="button"
              :title="localized(act.label)"
              @click.stop="emit('activateCard', card.instance_id, act.id)"
            >{{ isActivationAvailable(card) ? useLabel() : usedLabel() }}</button>
          </div>
        </div>
      </div>
    </div>

    <div class="play-label">{{ store.language === 'zh-Hant' ? '場上裝備與支援' : '场上装备与支援' }}（{{ assets.length }}）</div>

    <div class="slot-groups">
      <div v-for="group in slotGroups" :key="group.key" class="slot-group" :class="`${group.key}-group`">
        <div class="slot-group-header">
          <span>{{ groupLabel(group) }}</span>
          <span class="slot-count">{{ groupDetail(group) }} {{ group.used }}/{{ group.limit }}</span>
        </div>
        <div class="slot-track" :style="{ '--slot-limit': group.limit }">
          <div
            v-for="(item, index) in group.items"
            :key="item.kind === 'asset' ? item.asset.instance_id : `empty-${index}`"
            class="slot-item"
            :class="{ 'asset-item': item.kind === 'asset', 'empty-item': item.kind === 'empty', disabled: item.kind === 'asset' && !isActivationAvailable(item.asset) }"
            :style="item.kind === 'asset' ? { gridColumn: `span ${item.span}` } : undefined"
          >
            <template v-if="item.kind === 'asset'">
              <Card :card="item.asset" small />
              <span v-if="item.asset.activations?.length" class="activation-state">
                {{ isActivationAvailable(item.asset) ? '可使用' : '已使用' }}
              </span>
              <span v-else-if="shouldShowPassiveStatus(item.asset)" class="activation-state passive">
                {{ store.language === 'zh-Hant' ? '被動效果' : '被动效果' }}
              </span>
              <div v-if="item.asset.activations?.length" class="compact-actions">
                <button
                  v-for="act in item.asset.activations"
                  :key="act.id"
                  class="act-btn"
                  :class="{ disabled: !isActivationAvailable(item.asset) }"
                  :disabled="!isActivationAvailable(item.asset)"
                  type="button"
                  :title="localized(act.label)"
                  @click.stop="emit('activateCard', item.asset.instance_id, act.id)"
                >{{ isActivationAvailable(item.asset) ? useLabel() : usedLabel() }}</button>
              </div>
            </template>
            <template v-else>
              <span class="empty-slot-icon">□</span>
              <span>{{ emptyLabel(group) }}</span>
            </template>
          </div>
        </div>
      </div>

      <div v-if="unlimited.length" class="slot-group unlimited-group">
        <div class="slot-group-header">
          <span>{{ store.language === 'zh-Hant' ? '無槽位支援' : '无槽位支援' }}</span>
          <span class="slot-count">{{ store.language === 'zh-Hant' ? '不佔用槽位' : '不占用槽位' }}</span>
        </div>
        <div class="compact-row">
          <div v-for="asset in unlimited" :key="asset.instance_id" class="compact-item" :class="{ disabled: !isActivationAvailable(asset) }">
            <Card :card="asset" small />
            <span v-if="asset.activations?.length" class="activation-state">{{ isActivationAvailable(asset) ? '可使用' : '已使用' }}</span>
            <span v-else-if="shouldShowPassiveStatus(asset)" class="activation-state passive">
              {{ store.language === 'zh-Hant' ? '被動效果' : '被动效果' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!assets.length && !(threatCards && threatCards.length)" class="play-empty">{{ store.language === 'zh-Hant' ? '暫無場上支援或威脅' : '暂无场上支援或威胁' }}</div>
  </div>
</template>

<style scoped>
.play-area { display: flex; flex-direction: column; min-width: 0; padding: 6px 6px 8px; border-bottom: 1px solid #333344; }
.play-label { margin-bottom: 6px; padding-left: 4px; color: #c0a060; font-size: 12px; font-weight: bold; }
.support-section { min-width: 0; }
.threat-section { position: sticky; top: 0; z-index: 4; padding: 4px 0 2px; background: #0d0d1d; }
.threat-label { color: #f0a19a; }
.compact-row { display: flex; gap: 8px; overflow-x: auto; padding: 2px 2px 6px; }
.compact-item { position: relative; display: flex; min-width: 112px; flex: 0 0 112px; flex-direction: column; padding: 3px; border: 1px solid #4b4770; border-radius: 7px; background: rgba(15, 15, 32, .72); }
.compact-item :deep(.card), .slot-item :deep(.card) { width: 100px; min-height: 0; padding: 4px; border-width: 1px; cursor: pointer; }
.compact-item :deep(.card:hover), .slot-item :deep(.card:hover) { transform: translateY(-2px); box-shadow: none; }
.compact-item.disabled, .slot-item.disabled { opacity: .48; filter: grayscale(.65); }
.slot-groups { display: grid; grid-template-columns: repeat(6, minmax(118px, 1fr)); gap: 5px; min-width: 0; }
.slot-group { min-width: 0; padding: 4px; border: 1px solid #36344e; border-radius: 6px; background: rgba(17, 17, 35, .6); }
.slot-group-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px; color: #e0e0e0; font-size: 11px; font-weight: bold; }
.slot-count { color: #aaa5bd; font-size: 10px; font-weight: normal; }
.slot-track { display: grid; grid-template-columns: repeat(var(--slot-limit), minmax(52px, 1fr)); gap: 5px; min-height: 58px; }
.slot-item { display: flex; min-width: 0; min-height: 54px; align-items: center; justify-content: center; flex-direction: column; border: 1px dashed #4d4a68; border-radius: 6px; background: rgba(11, 11, 25, .5); overflow: hidden; }
.asset-item { align-items: stretch; justify-content: flex-start; border-style: solid; border-color: #5d5980; }
.empty-item { color: #77738c; font-size: 10px; }
.empty-slot-icon { color: #77738c; font-size: 18px; line-height: 18px; }
.hand-group { border-color: #765f27; } .accessory-group { border-color: #5e4470; } .body-group { border-color: #47616c; }
.ally-group { border-color: #386888; } .arcane-group { border-color: #554586; } .tarot-group { border-color: #806536; }
.unlimited-group { grid-column: 1 / -1; border-color: #496b50; }
.activation-state { padding: 2px 4px 0; color: #f0c56b; font-size: 9px; text-align: center; white-space: nowrap; }
.activation-state.passive { color: #8dd4a5; }
.compact-actions { display: flex; gap: 3px; padding: 4px 2px 1px; }
.act-btn { min-width: 0; flex: 1; padding: 3px 5px; border: 1px solid #4a6a9a; border-radius: 4px; background: #2a3a52; color: #b8d4f0; cursor: pointer; font-size: 9px; line-height: 1.2; }
.act-btn:hover:not(:disabled) { border-color: #86b6e5; background: #35486a; }
.act-btn.disabled, .act-btn:disabled { border-color: #555; background: #292936; color: #777; cursor: not-allowed; }
.threat-item { border-color: #8a3a34; }
.play-empty { padding: 10px 6px; color: #666; font-size: 12px; font-style: italic; text-align: center; }
@media (max-width: 900px) {
  .slot-groups { grid-template-columns: repeat(3, minmax(130px, 1fr)); }
}
@media (max-width: 560px) {
  .slot-groups { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
}
</style>
