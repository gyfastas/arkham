/** 共享的中文标签映射（traits / uses / 技能等） */

/** 卡牌 traits → 官方中文术语（zh.arkhamdb 惯例） */
export const TRAIT_LABELS: Record<string, string> = {
  tome: '典籍',
  insight: '洞察',
  tactic: '战术',
  item: '物品',
  weapon: '武器',
  firearm: '枪械',
  melee: '近战',
  ranged: '远程',
  spell: '法术',
  ally: '盟友',
  relic: '遗物',
  charm: '护符',
  clothing: '衣物',
  armor: '护甲',
  tool: '工具',
  supply: '补给',
  occult: '神秘',
  arcane: '奥秘',
  spirit: '精魂',
  ritual: '仪式',
  curse: '诅咒',
  bless: '祝福',
  creature: '生物',
  monster: '怪物',
  humanoid: '类人',
  cultist: '邪教徒',
  ghoul: '食尸鬼',
  'ancient one': '远古者',
  'elder thing': '古老者',
  'mi-go': '米·戈',
  yithian: '伊斯人',
  'deep one': '深潜者',
  serpent: '蛇人',
  byakhee: '拜亚基',
  shoggoth: '修格斯',
  spectral: '幽灵',
  undead: '不死',
  beast: '野兽',
  insect: '昆虫',
  expert: '专家',
  illicit: '违禁',
  gambit: '赌招',
  trick: '戏法',
  talent: '才能',
  skill: '技能',
  service: '服务',
  vehicle: '载具',
  location: '地点',
  madness: '疯狂',
  injury: '伤病',
  pact: '契约',
  omen: '预兆',
  omenreader: '解兆者',
  dream: '梦境',
  research: '研究',
  science: '科学',
  medicine: '医疗',
  miskatonic: '米大',
  agency: '警署',
  police: '警察',
  criminal: '罪犯',
  socialite: '名媛',
  scholar: '学者',
  investigator: '调查员',
  wayfarer: '旅人',
  performer: '表演者',
  practitioner: '实践者',
  believer: '信徒',
  hunter: '猎手',
  witch: '女巫',
  coven: '女巫团',
  tarot: '塔罗',
  music: '音乐',
  instrument: '乐器',
  book: '书籍',
  improvised: '临时',
  favor: '恩惠',
  connection: '人脉',
  job: '职业',
  drift: '漂流',
  expedition: '远征',
  guide: '向导',
  haven: '庇护所',
  power: '威能',
  practiced: '熟练',
  condition: '状态',
  attachment: '附着',
  treachery: '诡计',
  hazard: '险境',
  terror: '恐惧',
  discovery: '发现',
  darkness: '黑暗',
  bayou: '河口',
  wilderness: '荒野',
  city: '城市',
  haunted: '闹鬼',
  wood: '树林',
  cave: '洞穴',
  shore: '海岸',
  sea: '海洋',
  otherworld: '异界',
  extraterrestrial: '异星',
}

/** uses 标记 key → 中文 */
export const USES_LABELS: Record<string, string> = {
  horror: '恐惧',
  damage: '伤害',
  secrets: '秘密',
  charges: '充能',
  supplies: '补给',
  ammo: '弹药',
  evidence: '证据',
  resource: '资源',
  tome_hand_slots: '典籍手槽',
  uses: '使用次数',
}

/** 技能类型 → 中文 */
export const SKILL_LABELS: Record<string, string> = {
  willpower: '意志',
  intellect: '智力',
  combat: '战斗',
  agility: '敏捷',
  wild: '万能',
}

export function traitLabel(trait: string): string {
  return TRAIT_LABELS[trait.toLowerCase()] || trait
}

export function traitsLabel(traits: string[] | undefined | null): string {
  if (!traits || !traits.length) return ''
  return traits.map(traitLabel).join(' · ')
}

export function usesLabel(key: string): string {
  return USES_LABELS[key] || key
}

/** 职业/派系 → 官方中文名 */
export const CLASS_LABELS: Record<string, string> = {
  guardian: '守卫者',
  seeker: '探求者',
  rogue: '流浪者',
  mystic: '潜修者',
  survivor: '求生者',
  neutral: '中立',
}

/** 职业 → 玩家俗称（颜色家） */
export const CLASS_NICKNAMES: Record<string, string> = {
  guardian: '蓝家',
  seeker: '黄家',
  rogue: '绿家',
  mystic: '紫家',
  survivor: '红家',
  neutral: '',
}

/** 职业主题色 */
export const CLASS_COLORS: Record<string, string> = {
  guardian: '#2980b9',
  seeker: '#d4a017',
  rogue: '#27ae60',
  mystic: '#8e44ad',
  survivor: '#c0392b',
  neutral: '#888',
}

/** 职业分区展示顺序 */
export const CLASS_ORDER = ['guardian', 'seeker', 'rogue', 'mystic', 'survivor', 'neutral']

/** 职业标签：官方名（俗称），如「潜修者（紫家）」 */
export function classLabel(cls: string): string {
  const name = CLASS_LABELS[cls] || cls
  const nick = CLASS_NICKNAMES[cls]
  return nick ? `${name}（${nick}）` : name
}
