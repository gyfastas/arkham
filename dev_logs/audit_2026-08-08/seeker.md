# Seeker 阵营卡牌审计报告（2026-08-08）

**引擎事实**：`uses` 已从 JSON 加载（2026-08-08 修复，mr_rook_lv0={"secrets":3}、old_book_of_lore_lv3={"secrets":2} 已补，键名与 server/game_session.py 特判一致用复数）；技能卡提交图标由 skill_test.py 按数据自动结算；fast 认 JSON `fast` 字段；upkeep 手牌上限硬编码 8（phase_upkeep.py:13,83）；`INVESTIGATE_ACTION_INITIATED` 可用于限定"调查时"。server/game_session.py 对 old_book_of_lore_lv0、mr_rook_lv0 有特判激活处理器（本批次允许修改这两处）。

## A. 实现性错误

| card_id | 问题 | 卡面 | 实现 | 修法 |
|---|---|---|---|---|
| barricade_lv0 | 实现不符+翻译错误 | 非精英敌人不能移动进入被附加地点；强制-调查员离开该地点时弃屏障 | 阻止生成（official_core.py）且永不移除/离开不弃 | 卡文件内改为监听敌人移动事件拦截+离开弃牌（如需 scenario 侧钩子登记报告）；text_cn 修 |
| expose_weakness_lv1 | 翻译错误+实现错误 | 快速。智力检定(X=敌人战斗力)，每超出1点本阶段下次对其攻击其战斗力-1 | text_cn 编造为发现线索，实现照做 | 按英文重写（检定+减战斗力）；修 text_cn |
| inquiring_mind_lv0 | 翻译错误+实现错误 | 仅当所在地点有线索时可提交（3狂野图标由数据提供） | 实现另给敏捷/智力检定+2，叠加成+5；线索限制无人校验 | 删掉+2 handler；提交限制若引擎无通道则注明；修 text_cn |
| ive_got_a_plan_lv0 | 翻译错误+实现未完成 | Fight，用智力攻击，每持有1线索+1伤害（上限+3） | use_intellect_for_fight 是 pass TODO | 实现事件 fight 流程（智力替代+伤害加成）；修 text_cn |
| seeking_answers_lv0 | 实现未完成 | 调查。成功则改为在连接地点发现1线索 | handler 是 pass TODO | 实现调查事件：成功时改连点发现 |
| seeking_answers_lv2 | 翻译错误+实现错误+数据缺图标 | 调查。成功则在本地点与连接地点间共发现2线索（真卡图标1智2敏） | text_cn 编造；实现任意智力检定超2点自动打出 | 按英文重写为调查事件；补图标；修 text_cn |
| old_book_of_lore_lv0 | 实现错误 | [行动]消耗：选本地点调查员查牌库顶3张抽1张，其余洗入牌库 | py 直接抽顶1张不消耗；session 特判查3选1但其余置底且不消耗 | 统一：消耗+查3选1+其余洗混（修改 session 特判，允许）；text_cn"置于牌库底"改 |
| old_book_of_lore_lv3 | 翻译错误+实现错误+数据已补uses | 使用(2秘密)。查3抽1并洗牌；然后可花1秘密让该调查员立即以-2费用打出该牌（真卡图标1意1智） | text_cn 编造第二段；实现照做；图标空 | 补 icons；第二段改花秘密-2费打出（若交互复杂可注明简化）；其余洗混 |
| medical_texts_lv0 | 翻译错误+实现不可达 | [行动]选本地点调查员检定智力(2)：成功治1伤，失败对其造成1伤 | activate() 是 pass | 实现激活+检定（activations 声明）；修 text_cn |
| encyclopedia_lv2 | 翻译错误+实现不可达 | [行动]消耗：选本地点调查员，所选技能+2至阶段结束 | 无 activations 不可达；activate 不消耗 | 接线激活（行动+消耗）；修 text_cn |
| hyperawareness_lv0 | 实现不可达 | [快速]花1资源：本次检定+1智力或+1敏捷 | boost() 正确但无调用通道 | 接入检定激活通道（参照 timing:"combat" 模式；若无通道注明） |
| strange_solution_lv0 | 实现不可达 | [行动]智力(4)检定，成功弃掉抽2张并记冒险日志 | resolve() 正确但无入口 | 接线激活+检定（activations） |
| laboratory_assistant_lv0 | 实现部分失效 | 手牌上限+2；入场后抽2张 | 抽2 ✓；上限+2无效（upkeep 硬编码8） | 报告注明引擎缺口（手牌上限不按调查员计算），卡文件不改 |
| mr_rook_lv0 | 简化超界（py路径） | 查顶3/6/9任选1张抽取；有弱点也抽；洗牌 | py activate 自动抽第一张非弱点 | 弃用 py 自动选牌路径（保留 session 两段选择流）；确认洗牌 |
| magnifying_glass_lv0 | 简化超界（轻）+数据缺 fast | 快速。调查时+1智力 | 在场对所有智力检定+1 | 用 INVESTIGATE_ACTION_INITIATED 限定调查；JSON 补 "fast": true |
| magnifying_glass_lv1 | 同上+text_cn 残缺 | 快速。调查时+1智力。[快速]若本地点无线索：可收回手牌（可选） | blanket +1；自动收回 | 限定调查；回收若无可选窗口保持自动并注明；补 fast 与 text_cn |
| daisy_walker | 实现 bug×2 | 每回合1个额外行动仅限典籍能力；远古印记+0，成功时每控制1典籍抽1张 | ①同时 +1 actions 和 tome token → 实际5行动；②印记抽牌存 ST.4 ctx.extra 在 ST.6 另一 ctx 读 getattr(ctx,'_extra')（不存在）→ 永远抽不到 | ①去掉 actions_remaining+=1；②典籍计数存调查员状态（如 scenario.vars 或 inv 侧字段）跨事件传递 |
| deduction_lv0 | 数据文本残缺+实现条件缺口（轻） | 官方含 "while investigating a location" | 任何智力检定成功都发线索 | JSON 补全条件（已修 text_cn）；实现用 INVESTIGATE_ACTION_INITIATED 限定调查 |

## B. 纯数据/翻译问题
- cryptic_research_lv4：补 "fast": true
- shortcut_lv0：补 "fast": true
- crack_the_case_lv0：补英文 text + fast；打出时机（地点最后一条线索后）无校验——注明
- preposterous_sketches_lv0：text_cn"抽2张"应抽3张；"地点有线索才能打出"无校验——注明
- preposterous_sketches_lv2：补英文 text；同上加条件注明
- working_a_hunch_lv0：text_cn"发现并消耗"措辞改；漏译快速/回合限制
- expose_weakness_lv1 / magnifying_glass_lv0/lv1：补 "fast": true

## C. 有意的规则选择（不动）
dr_milan_christopher_lv0 按 Taboo 消耗给资源；rex_murphy 按 Taboo 每轮限1次（印记预授权简化保留）。

## 无问题清单
art_student_lv0、research_librarian_lv0、daisys_tote_bag、disc_of_itzamna_lv2、mind_over_matter_lv0、cryptic_research 实现主体、shortcut_lv0 实现主体、crack_the_case_lv0 实现主体、preposterous_sketches 实现主体、dr_milan_christopher_lv0、rex_murphy 能力本体
