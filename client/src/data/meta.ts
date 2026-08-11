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
  {
    label: '卡尔克萨',
    investigators: [
      { id: 'mark_harrigan', name_cn: '马克·哈里根', name_hant: '馬克·哈里根', class: 'guardian' },
      { id: 'minh_thi_phan', name_cn: '潘明', name_hant: '潘明', class: 'seeker' },
      { id: 'sefina_rousseau', name_cn: '赛菲娜·卢梭', name_hant: '賽菲娜·盧梭', class: 'rogue' },
      { id: 'akachi_onyele', name_cn: '阿喀琦·奥耶莉', name_hant: '阿喀琦·奧耶莉', class: 'mystic' },
      { id: 'william_yorick', name_cn: '威廉·约里克', name_hant: '威廉·約里克', class: 'survivor' },
      { id: 'lola_hayes', name_cn: '萝拉·海耶斯', name_hant: '蘿拉·海耶斯', class: 'neutral' },
    ],
  },
  {
    label: '遗忘时代',
    investigators: [
      { id: 'leo_anderson', name_cn: '里奥·安德森', name_hant: '里奧·安德森', class: 'guardian' },
      { id: 'ursula_downs', name_cn: '厄休拉·唐斯', name_hant: '厄休拉·唐斯', class: 'seeker' },
      { id: 'finn_edwards', name_cn: '芬恩·爱德华兹', name_hant: '芬恩·愛德華茲', class: 'rogue' },
      { id: 'father_mateo', name_cn: '马泰奥神父', name_hant: '馬泰奧神父', class: 'mystic' },
      { id: 'calvin_wright', name_cn: '加尔文·怀特', name_hant: '加爾文·懷特', class: 'survivor' },
    ],
  },
  {
    label: '万象祭环',
    investigators: [
      { id: 'carolyn_fern', name_cn: '卡罗琳·弗恩', name_hant: '卡羅琳·弗恩', class: 'guardian' },
      { id: 'joe_diamond', name_cn: '乔·戴蒙德', name_hant: '喬·戴蒙德', class: 'seeker' },
      { id: 'preston_fairmont', name_cn: '普雷斯顿·费尔蒙特', name_hant: '普雷斯頓·費爾蒙特', class: 'rogue' },
      { id: 'diana_stanley', name_cn: '黛安娜·史丹利', name_hant: '黛安娜·史丹利', class: 'mystic' },
      { id: 'rita_young', name_cn: '丽塔·杨', name_hant: '麗塔·楊', class: 'survivor' },
      { id: 'marie_lambeau', name_cn: '玛丽·朗博', name_hant: '瑪麗·朗博', class: 'mystic' },
    ],
  },
  {
    label: '食梦者',
    investigators: [
      { id: 'tommy_muldoon', name_cn: '托米·马尔登', name_hant: '托米·馬爾登', class: 'guardian' },
      { id: 'mandy_thompson', name_cn: '曼蒂·汤普森', name_hant: '曼蒂·湯普森', class: 'seeker' },
      { id: 'tony_morgan', name_cn: '托尼·摩尔根', name_hant: '托尼·摩爾根', class: 'rogue' },
      { id: 'luke_robinson', name_cn: '卢克·罗宾逊', name_hant: '盧克·羅賓遜', class: 'mystic' },
      { id: 'patrice_hathaway', name_cn: '派翠斯·海瑟薇', name_hant: '派翠斯·海瑟薇', class: 'survivor' },
    ],
  },
  {
    label: '印斯茅斯',
    investigators: [
      { id: 'sister_mary', name_cn: '玛丽修女', name_hant: '瑪麗修女', class: 'guardian' },
      { id: 'amanda_sharpe', name_cn: '阿曼达·夏普', name_hant: '阿曼達‧夏普', class: 'seeker' },
      { id: 'trish_scarborough', name_cn: '特里希·斯卡波罗', name_hant: '特里希‧斯卡波羅', class: 'rogue' },
      { id: 'dexter_drake', name_cn: '戴克斯特·德雷克', name_hant: '戴克斯特‧德雷克', class: 'mystic' },
      { id: 'silas_marsh', name_cn: '赛拉斯·马什', name_hant: '賽拉斯‧馬什', class: 'survivor' },
    ],
  },
  {
    label: '地极秘境',
    investigators: [
      { id: 'daniela_reyes', name_cn: '丹妮拉·雷耶丝', name_hant: '丹妮拉·雷耶絲', class: 'guardian' },
      { id: 'norman_withers', name_cn: '诺曼·威瑟斯', name_hant: '諾曼·威瑟斯', class: 'seeker' },
      { id: 'monterey_jack', name_cn: '蒙特雷·杰克', name_hant: '蒙特雷·傑克', class: 'rogue' },
      { id: 'lily_chen', name_cn: '陈丽丽', name_hant: '陳麗麗', class: 'mystic' },
      { id: 'bob_jenkins', name_cn: '鲍勃·詹金斯', name_hant: '鮑勃·詹金斯', class: 'survivor' },
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
  {
    id: 'path_to_carcosa',
    name_cn: '卡尔克萨之路',
    name_hant: '卡爾克薩之路',
    chapters: [
      { id: 'curtain_call', name_cn: '谢幕', name_hant: '謝幕' },
      { id: 'the_last_king', name_cn: '最后的王者', name_hant: '最後的王者' },
      { id: 'echoes_of_the_past', name_cn: '往事回声', name_hant: '往事回聲' },
      { id: 'the_unspeakable_oath', name_cn: '邪秽誓约', name_hant: '邪穢誓約' },
      { id: 'a_phantom_of_truth', name_cn: '真相幻影', name_hant: '真相幻影' },
      { id: 'the_pallid_mask', name_cn: '苍白面具', name_hant: '蒼白面具' },
      { id: 'black_stars_rise', name_cn: '黑星升起', name_hant: '黑星升起' },
      { id: 'dim_carcosa', name_cn: '卡城幽影', name_hant: '卡城幽影' },
    ],
  },
  {
    id: 'the_forgotten_age',
    name_cn: '遗忘时代',
    name_hant: '遺忘時代',
    chapters: [
      { id: 'wilds', name_cn: '荒野无情', name_hant: '荒野無情' },
      { id: 'eztli', name_cn: '埃兹特里的末日', name_hant: '埃茲特里的末日' },
      { id: 'threads_of_fate', name_cn: '命运丝线', name_hant: '命運絲線' },
      { id: 'the_boundary_beyond', name_cn: '彼界之外', name_hant: '彼界之外' },
      { id: 'heart_of_the_elders', name_cn: '长者之心', name_hant: '長者之心' },
      { id: 'the_city_of_archives', name_cn: '档案之城', name_hant: '檔案之城' },
      { id: 'the_depths_of_yoth', name_cn: '约斯深渊', name_hant: '約斯深淵' },
      { id: 'shattered_aeons', name_cn: '破碎纪元', name_hant: '破碎紀元' },
    ],
  },
  {
    id: 'the_circle_undone',
    name_cn: '万象祭环',
    name_hant: '萬象祭環',
    chapters: [
      { id: 'the_witching_hour', name_cn: '女巫时刻', name_hant: '女巫時刻' },
      { id: 'at_deaths_doorstep', name_cn: '死亡门前', name_hant: '死亡門前' },
      { id: 'the_secret_name', name_cn: '秘密之名', name_hant: '秘密之名' },
      { id: 'the_wages_of_sin', name_cn: '罪孽代价', name_hant: '罪孽代價' },
      { id: 'for_the_greater_good', name_cn: '大义', name_hant: '大義' },
      { id: 'union_and_disillusion', name_cn: '联合与幻灭', name_hant: '聯合與幻滅' },
      { id: 'in_the_clutches_of_chaos', name_cn: '混沌魔掌', name_hant: '混沌魔掌' },
      { id: 'before_the_black_throne', name_cn: '黑王座前', name_hant: '黑王座前' },
    ],
  },
  {
    id: 'the_dream_eaters',
    name_cn: '食梦者',
    name_hant: '食夢者',
    chapters: [
      { id: 'beyond_the_gates_of_sleep', name_cn: '梦眠之门', name_hant: '夢眠之門' },
      { id: 'waking_nightmare', name_cn: '惊醒梦魇', name_hant: '驚醒夢魘' },
      { id: 'the_search_for_kadath', name_cn: '寻找卡达斯', name_hant: '尋找卡達斯' },
      { id: 'a_thousand_shapes_of_horror', name_cn: '千面恐惧', name_hant: '千面恐懼' },
      { id: 'dark_side_of_the_moon', name_cn: '月之暗面', name_hant: '月之暗面' },
      { id: 'point_of_no_return', name_cn: '不归点', name_hant: '不歸點' },
      { id: 'where_gods_dwell', name_cn: '众神栖所', name_hant: '眾神棲所' },
      { id: 'weaver_of_the_cosmos', name_cn: '宇宙织者', name_hant: '宇宙織者' },
    ],
  },
  {
    id: 'innsmouth_conspiracy',
    name_cn: '印斯茅斯阴谋',
    name_hant: '印斯茅斯陰謀',
    chapters: [
      { id: 'the_vanishing_of_elina_harper', name_cn: '艾琳娜·哈珀失踪案', name_hant: '艾琳娜·哈珀失蹤案' },
      { id: 'in_too_deep', name_cn: '深陷其中', name_hant: '深陷其中' },
      { id: 'the_pit_of_despair', name_cn: '绝望之渊', name_hant: '絕望之淵' },
      { id: 'devil_reef', name_cn: '恶魔礁', name_hant: '惡魔礁' },
      { id: 'horror_in_high_gear', name_cn: '极速恐惧', name_hant: '極速恐懼' },
      { id: 'a_light_in_the_fog', name_cn: '雾中之光', name_hant: '霧中之光' },
      { id: 'the_lair_of_dagon', name_cn: '达贡巢穴', name_hant: '達貢巢穴' },
      { id: 'into_the_maelstrom', name_cn: '深入漩涡', name_hant: '深入漩渦' },
    ],
  },
  {
    id: 'edge_of_the_earth',
    name_cn: '地极秘境',
    name_hant: '地極秘境',
    chapters: [
      { id: 'ice_and_death_part_1', name_cn: '冰与死 I', name_hant: '冰與死 I' },
      { id: 'ice_and_death_part_2', name_cn: '冰与死 II', name_hant: '冰與死 II' },
      { id: 'ice_and_death_part_3', name_cn: '冰与死 III', name_hant: '冰與死 III' },
      { id: 'to_the_forbidden_peaks', name_cn: '前往禁峰', name_hant: '前往禁峰' },
      { id: 'city_of_the_elder_things', name_cn: '古神之城', name_hant: '古神之城' },
      { id: 'endless_night', name_cn: '无尽长夜', name_hant: '無盡長夜' },
      { id: 'fatal_mirage', name_cn: '致命蜃景', name_hant: '致命蜃景' },
      { id: 'the_heart_of_madness_part_1', name_cn: '疯狂之心 I', name_hant: '瘋狂之心 I' },
      { id: 'final_night', name_cn: '终夜', name_hant: '終夜' },
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
