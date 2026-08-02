/** Shared game metadata: investigators, campaigns, scenarios. */

export interface InvestigatorEntry {
  id: string
  name_cn: string
  name_hant: string
  class: string
}

export interface CampaignEntry {
  id: string
  name_cn: string
  name_hant: string
  chapters: { id: string; name_cn: string; name_hant: string }[]
}

export const INVESTIGATOR_GROUPS: { label: string; investigators: InvestigatorEntry[] }[] = [
  {
    label: '核心包',
    investigators: [
      { id: 'roland_banks', name_cn: '罗兰·班克斯', name_hant: '羅蘭·班克斯', class: 'guardian' },
      { id: 'daisy_walker', name_cn: '黛西·沃克', name_hant: '黛西·沃克', class: 'seeker' },
      { id: 'skids_otoole', name_cn: '斯基兹·奥图尔', name_hant: '斯基茲·奧圖爾', class: 'rogue' },
      { id: 'agnes_baker', name_cn: '阿格妮丝·贝克', name_hant: '阿格妮絲·貝克', class: 'mystic' },
      { id: 'wendy_adams', name_cn: '温蒂·亚当斯', name_hant: '溫蒂·亞當斯', class: 'survivor' },
    ],
  },
  {
    label: '敦威治',
    investigators: [
      { id: 'zoey_samaras', name_cn: '佐伊·萨马拉斯', name_hant: '佐伊·薩馬拉斯', class: 'guardian' },
      { id: 'rex_murphy', name_cn: '雷克斯·墨菲', name_hant: '雷克斯·墨菲', class: 'seeker' },
      { id: 'jenny_barnes', name_cn: '珍妮·巴恩斯', name_hant: '珍妮·巴恩斯', class: 'rogue' },
      { id: 'jim_culver', name_cn: '吉姆·卡尔弗', name_hant: '吉姆·卡爾弗', class: 'mystic' },
      { id: 'ashcan_pete', name_cn: '流浪汉皮特', name_hant: '流浪漢皮特', class: 'survivor' },
    ],
  },
]

export const ALL_INVESTIGATORS: InvestigatorEntry[] =
  INVESTIGATOR_GROUPS.flatMap(g => g.investigators)

export const CAMPAIGNS: CampaignEntry[] = [
  {
    id: 'core',
    name_cn: '狂热者之夜',
    name_hant: '狂熱者之夜',
    chapters: [
      { id: 'the_gathering', name_cn: '聚集于此', name_hant: '聚集於此' },
      { id: 'the_midnight_masks', name_cn: '午夜假面', name_hant: '午夜假面' },
      { id: 'the_devourer_below', name_cn: '吞噬星辰', name_hant: '吞噬星辰' },
    ],
  },
  {
    id: 'dunwich_legacy',
    name_cn: '敦威治遗产',
    name_hant: '敦威治遺產',
    chapters: [
      { id: 'extracurricular_activity', name_cn: '课外活动', name_hant: '課外活動' },
      { id: 'the_house_always_wins', name_cn: '赌场必胜', name_hant: '賭場必勝' },
      { id: 'the_miskatonic_museum', name_cn: '米斯卡塔尼克博物馆', name_hant: '米斯卡塔尼克博物館' },
      { id: 'essex_county_express', name_cn: '埃塞克斯快车', name_hant: '埃塞克斯縣快車' },
      { id: 'blood_on_the_altar', name_cn: '祭坛之血', name_hant: '祭壇之血' },
      { id: 'undimensioned_and_unseen', name_cn: '无形无踪', name_hant: '無形無蹤' },
      { id: 'where_doom_awaits', name_cn: '末日将至', name_hant: '末日將至' },
      { id: 'lost_in_time_and_space', name_cn: '迷失于时空', name_hant: '迷失於時空' },
    ],
  },
]

/** scenario_id → campaign_id */
export const SCENARIO_CAMPAIGN: Record<string, string> = Object.fromEntries(
  CAMPAIGNS.flatMap(c => c.chapters.map(ch => [ch.id, c.id])),
)

export const DIFFICULTIES = ['easy', 'standard', 'hard', 'expert'] as const
export const DIFFICULTY_LABELS: Record<string, string> = {
  easy: '简单',
  standard: '标准',
  hard: '困难',
  expert: '专家',
}

/** 混沌标记显示（图标 + 中文名） */
export const TOKEN_LABELS: Record<string, { icon: string; label: string }> = {
  '+1': { icon: '+1', label: '' },
  '0': { icon: '0', label: '' },
  '-1': { icon: '−1', label: '' },
  '-2': { icon: '−2', label: '' },
  '-3': { icon: '−3', label: '' },
  '-4': { icon: '−4', label: '' },
  '-5': { icon: '−5', label: '' },
  '-6': { icon: '−6', label: '' },
  '-7': { icon: '−7', label: '' },
  '-8': { icon: '−8', label: '' },
  skull: { icon: '💀', label: '骷髅' },
  cultist: { icon: '🜏', label: '邪教徒' },
  tablet: { icon: '📜', label: '石板' },
  elder_thing: { icon: '🐙', label: '旧神之物' },
  auto_fail: { icon: '✖', label: '自动失败' },
  elder_sign: { icon: '✦', label: '远古印记' },
}
