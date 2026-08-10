# 大更新计划：卡牌完整性 + 多人联机 + 二循环卡尔克萨之路

> 目标：① 现有卡牌效果与官方 DB 对齐并检查完整 ② 支持 2-4 人联机 ③ 引入卡尔克萨之路全部卡牌/调查员/剧本（含翻译）④ 全量测试 + 实际游玩录制。
> 状态随进展更新。✅=完成 🔨=进行中 ⬜=未开始

## Phase 1 现有卡牌完整性 ✅（2026-08-08 完成）

现状：149 张玩家卡，148 张有实现（`random_basic_weakness` 为占位卡除外）。

- [x] 新增 data↔registry 覆盖度 meta-test（白名单 random_basic_weakness；修 CARDS_ROOT 路径 bug 使 AST 扫描真正生效）
- [x] 修复 `lucky_lv0`（差值≤2 才翻转）/ `lucky_lv2`（改为抽1张牌）
- [x] 修复数据翻译错误：machete/deduction/dynamite_blast 等数十张（详见各阵营审计报告 dev_logs/audit_2026-08-08/）
- [x] 全量卡牌六阵营审计 + 修复（约 60 张卡的问题；实现按官方卡面重写、测试补强）
- [x] 引擎批次：uses 从 JSON 加载（12 张卡补数据）、bind_chaos_bag 生产接线、ResourceSkillBoost 可叠加、ENEMY_DEFEATED 带击败者、_st2_commit 难度通道、leo_de_luca 事件修正、DAMAGE_ASSIGNED/HORROR_ASSIGNED 取消窗口、_st4 cancel_auto_fail、_fight 取消通道、 upkeep 手牌上限按调查员、非盟友 asset 承伤、Barricade 移动拦截（ENEMY_MOVE_BLOCKED）
- [x] 会话层：clarity_of_mind/rite_of_seeking 特判去横置与自弃、old_book_of_lore 洗入牌库、_PASSIVE_CARDS 文案、list_available_cards 支持 "any" 外挂牌选项
- [x] 测试：922 项全绿（含新增行为测试）；grotesque_statue 随机性测试改确定性 seed

**遗留引擎/交互缺口**（登记待做，见各阵营报告「需要主代理处理」）：
- 直接伤害/恐惧（inv.damage += N）绕过击败判定——需统一直接伤害通道
- 打出条件校验通道（crack_the_case / preposterous_sketches "Play only if..."）、inquiring_mind can_commit 接线
- ResourceSkillBoost.spend 的 UI/会话入口（5 张天赋卡花费加值在 UI 无触发通道）
- 卡牌自检定（medical_texts 等）无 ST.2 投入窗口
- jim_culver/ashcan "any" 外挂牌的数量上限校验（当前只放进构筑池）
- 若干玩家选择窗口简化为自动（ward_of_protection、grotesque_statue 二选一等）

## Phase 2 多人联机（2-4 人）✅（2026-08-08 完成）

依据 2026-08-08 联机缺口评估（explore 报告），引擎层基本多人就绪，工作集中在 server 编排层 + scenario + client。

已完成：
- [x] S1 `Room.start_game` 遍历全部已就绪座位；S2 `GameSession.setup(players=[...])` 多调查员（实例 id "player"/"player2"/...）
- [x] S3 回合结构：行动权校验（非当前玩家拒绝）、END_TURN 移交下一位、全员完毕才跑敌人/刷新/神话、神话逐人抽遭遇（pending 队列续跑）
- [x] S4 逐收件人序列化广播（信息隐藏）；`serialize_investigator_public` 接线为 `other_investigators`；`instance_id`/`active_investigator_id`/`your_turn` 字段
- [x] S5 pending 检定/选择按属主路由（RESOLVE_CHOICE/SKILL_TEST_ROLL 只有属主可结算）
- [x] S6 逐调查员败北（线索掉落所在地点、移出行动顺序），全员败北才判负
- [x] C1 scenario "player" 硬编码参数化（_enemy_card_at/_find_nearest_cultist 遍历全体；pending_choice 带属主）
- [x] C2 幕推进全组线索汇集 + 官方 ⊘ 阈值×人数（ActCard.clue_threshold_per_investigator；the_barrier 等用遭遇库官方值）；地点线索 ⊘×人数（CardData.per_investigator，setup 缩放）
- [x] 多人 mulligan（逐人调度/放弃，全员完成才洗回搁置卡）
- [x] UI1 大厅（创建/按ID加入/4座位/ready=setup_game）；UI2 队友面板 TeammatePanel；UI3 回合徽标+行动门控+地图队友标记；弹窗归属过滤
- [x] 附带修复：state_serializer serialize_public_state NameError、SlotDiscardModal 未导入
- [x] 测试：test_multiplayer_session.py 14 项 + scripts/smoke_multiplayer.py（双客户端 socket 全流程）；全量 936 绿；campaign 冒烟通过

延后项（有意）：S7 战役存档多人化（战役仍单人）、S8 断线重连、E2 prey/massive/aloof 交战规则、E3 队友代投。剧本/难度协商以最后 ready 玩家为准（协议限制）。

## Phase 3 卡尔克萨之路数据导入 ✅（2026-08-09 完成）

- [x] 抓取管线改造：`skills/import-campaign/scripts/fetch_carcosa.py`（ptcp/ptcc 参数化、back_text/back_text_cn、uses 解析、hand_x2 槽位）
- [x] `data/encounter_cards/path_to_carcosa.json`（248 张，含 dim_carcosa a 面地点补抓）
- [x] 玩家卡 108 张（含 archaic_glyphs 双 lv3 撞名拆分：guiding_stones/prophecy_foretold）
- [x] 6 调查员：ArkhamDB `deck_options`/`deck_requirements` 结构化落地（Mark 战术0级、Minh/Sefina/Yorick 副职0-2、Lola 全阵营0-3+35张、Sefina 33张）；signature/weakness 自动关联；deck size 33/35 引擎已支持
- [x] `data/chaos_bags.json` path_to_carcosa（四符号齐全 skull×2+cultist+tablet+elder_thing；easy16/std17/hard18/expert19；注：zzorba 数据包的袋组成与官方指南不符，未采用）
- [x] 8 个剧本 JSON：连接图标由卡面图视觉读取并双向复核（/tmp/ptc_cards 拼图）；遭遇组/初始地点/搁置/start_location 照官方战役指南（zzorba 结构化数据）
- [x] `data/campaigns/path_to_carcosa.json`
- [x] 简体翻译：玩家卡+调查员+剧本名 OpenCC t2s + 项目术语表（遭遇卡保留繁体，与敦威治一致）
- [x] 接线：`load_encounter_db_for_campaign` carcosa 分支（core+carcosa merge）、`campaign_name_cn`、client meta.ts（CAMPAIGNS+INVESTIGATOR_GROUPS 卡尔克萨组）
- [x] 撞名检查：ptc∩core={frozen_in_fear(同卡重印), the_ritual_begins(异卡同名)}——merge 按战役隔离，无功能影响，已记录
- [x] 覆盖度 meta-test 对 ptc 暂时豁免（Phase 4 实现后移除豁免）
- [x] 验证：curtain_call 可完整初始化（10 地点/18 遭遇/17 标记标准袋）；936 测试绿；双冒烟通过

**移交 Phase 4 的引擎缺口**：`initial_locations`/`set_aside` 未在 apply_scenario_to_game 生效（当前全地点入场）、doorway 揭示机制、Hidden 关键词、Doubt/Conviction 战役轨道、Act 多版本选择。

## Phase 4 卡尔克萨机制实现 🔨

- [x] 引擎缺口（4A）：`initial_locations`/`set_aside` 生效、遭遇牌堆按 meta.quantity 多份、Hidden 关键词解析、LocationState.horror（地点恐惧）
- [x] 8 剧本 × 4 符号 × 难易两面 token 效果（4B）：`_carcosa_token_effects`，23 项测试（test_carcosa_tokens.py）；数值经官方参考卡文本 + zzorba 结构化数据双向核实
- [x] ~108 玩家卡 + 6 调查员实现（4C）：六阵营+调查员并行实现，1509 测试全绿；data↔impl 覆盖度 100%（豁免已移除）；数据修正（uses 键 typo、fast 字段、archaic_glyphs 撞名拆分、41_derringer 去重）
- [x] 遭遇卡效果（4D）：carcosa_encounters.py（40 张诡计全量，63 项测试 test_carcosa_encounters.py）；resolve_encounter_card 接线（choice 透传）
- [x] 战役机制（4D 部分）：CampaignState.doubt/conviction 字段+持久化；剧本 vars 注入；苍白面具混乱袋规则（移除三符号+加回2个选定符号）；结局 mark_doubt/mark_conviction 结算
- [ ] 遗留引擎缺口（见各实现报告）：ENEMY_SPAWNED 事件、遭遇抽取"将要抽"窗口、卡效果入场资产的实现注册、提交校验钩子（can_commit 接线）、放逐区、Lola 角色限制校验、Sefina 禁换牌
- [x] 6 调查员预设牌组（data/preset_decks/，官方张数 30/33/35）

## Phase 5 游玩测试与录制 ✅（2026-08-10 完成）

- [x] Playwright 环境（chromium 于 .tools/ms-playwright，PLAYWRIGHT_BROWSERS_PATH 隔离）
- [x] 修复录制脚本：hash 路由（/#/quick）、开局调度弹窗、技能轮盘（投掷→动画→确认）、SPA 路由回退、参数化剧本/调查员
- [x] 修复 LobbyView 剧本列表缺卡尔克萨（改复用 meta.ts CAMPAIGNS/INVESTIGATOR_GROUPS）；连接列表过滤未入场地点；战役牌组张数按调查员（33/35）
- [x] 单人卡尔克萨录制：playtest_ptc_curtain_call_2026-08-10.webm（马克×谢幕 6 轮，webm+截图）
- [x] 双人联机录制：playtest_mp_p1/p2_2026-08-10.webm（双视角 2 轮，房间/回合轮换/线索缩放/越权拒绝实况）
- [x] 产物入 docs/playtest/，过程记录 dev_logs/
- [x] 最终全量验证：1572 pytest 绿 + 双冒烟 + 前端构建

## 总结

目标全部落地：① 既有 149 卡审计修复（约 60 卡问题，引擎+数据+翻译）② 2-4 人联机（回合/权限/逐人结算/大厅/队友面板，双冒烟+双视角录像实证）③ 卡尔克萨之路全量（248 遭遇卡、108 玩家卡、6 调查员、8 剧本、混乱袋、token 双面效果、遭遇效果、战役轨道、简体翻译）④ 1572 测试全绿 + 真实游玩录像（单人卡尔克萨 + 双人联机）。

## 关键原则（CLAUDE.md 开发原则）

实现逻辑检查透、与官方 DB 对齐（含 back_text 难度分面）、功能一致性（引擎/UI/接口/存档一致）。
