# Survivor 阵营卡牌审计报告（2026-08-08）

**引擎事实**：武器加成判定用 `ctx.source`（machete fallback 写法），不要读 ctx.extra["weapon_card_id"]（引擎从不设置）；`SKILL_TEST_SUCCESSFUL` ctx 有 modified_skill/difficulty 可算 margin，bonus_damage 通道 `ctx.extra["bonus_damage"]`；`DAMAGE_DEALT` 只对敌人，调查员受伤走 `DAMAGE_ASSIGNED`/`HORROR_ASSIGNED`。

**已修复（验证即可）**：lucky_lv0 已改为差值≤2 才翻转（差值>2 仍打出消耗），lucky_lv2 见下方仍需修。

## 需要修复

1. **aquinnah_lv1 / aquinnah_lv3** | 实现错误（监听错事件永不触发）+【翻译错误】+lv3【数据文本错误】
   - 卡面（01082/01691）：敌人攻击你时，横置 Aquinnah 并对她造成1恐惧：把该敌人的伤害值改对你所在地点的另一个敌人（lv3 任意敌人）造成；你仍承受恐惧部分。
   - 实现：挂 DAMAGE_DEALT 永不触发；按错误中文：弃置、取消全部、反弹攻击者固定1/2点、无恐惧代价。
   - 修法：改挂调查员受伤流程（DAMAGE_ASSIGNED/HORROR_ASSIGNED 路线，找攻击来源）；费用=横置+给 Aquinnah 1恐惧；数值取 enemy_data.enemy_damage；目标默认同地点第一个其他敌人+注明简化。重写 CN。data EN lv3 "damage and horror to another enemy" 改 "damage to any enemy"。
2. **eucatastrophe_lv3** | 实现成另一张卡+【翻译错误】
   - 卡面：快速。当某混沌标记将使你的技能值降为0（含自动失败）时打出：取消该标记并视为远古印记。
   - 实现：按错误CN做成取消击败+弃弱点+回满+3资源。
   - 修法：整体重写为标记取消（参照 wendy_adams.py 的 CHAOS_TOKEN_RESOLVED 修正模式：modified 技能值为0或 auto_fail 时把标记改为 elder_sign 语义：modify_amount 修正+清 auto_fail 需要引擎支持则注明）。CN 全文重写。
3. **will_to_survive_lv3** | 实现错误+【数据文本错误】+【翻译错误】
   - 卡面（01085）：快速，只能在你的回合打出；直到你的回合结束，你的技能检定不揭示混沌标记。
   - 实现：按错误CN做成全技能+1；过期在任一调查员回合结束清除所有人。
   - 修法：改为"本回合你的检定跳过混沌标记揭示"（引擎 _st3_reveal 若无跳过通道：可用 scenario.vars 标记 + 卡内 CHAOS_TOKEN_REVEALED 监听把 token 强制替换为 0 修正并注释简化，或登记引擎缺口）；过期挂自己回合结束；修 data EN（"end of the round"→"end of your turn"，补 "Play only during your turn"）与 CN。
4. **survival_instinct_lv0** | 实现错误+【翻译错误】+【简化超界】
   - 卡面：本次躲避检定成功后，躲避者可立即与每个其他交战敌人脱离，并可移动到连接地点。
   - 实现：失败转成功+强制移动；未实现脱离。
   - 修法：挂 SKILL_TEST_SUCCESSFUL（agility 且 committed 含本卡）：脱离其他交战敌人；移动默认第一连接地点+注明简化。CN 重写。
5. **cunning_distraction_lv0** | 实现错误+【翻译错误】+【数据文本错误】（轻）
   - 卡面（01078）：Evade. 自动躲避你所在地点的所有敌人（原地横置脱离，不移动）。
   - 实现：只处理与你交战的敌人并移动到连接地点。
   - 修法：对当前地点所有敌人自动躲避（exhaust+脱离），删除移动。data EN 补 "Evade."；CN 重写。
6. **fire_axe_lv0** | 实现错误
   - 卡面：无基础加成；资源池为0时本次攻击+1伤害；攻击中花1资源+2战斗（每攻击限3次）。
   - 实现：在场所有战斗检定无条件+1；真实能力缺失。
   - 修法：删幽灵+1；实现"0资源+1伤害"（DAMAGE_DEALT 对敌人时检查资源池与 source）；ResourceSkillBoost 式 spend（+2/资源，每攻击限3次——_shared.py 已改计数制，加 per-attack 上限）。
7. **baseball_bat_lv0** | 实现错误+【翻译错误】（部分）
   - 卡面：+2战斗、+1伤害；仅当揭示 skull 或 auto_fail 时攻击结算后弃置。
   - 实现：combat_bonus 读 weapon_card_id 死代码；弃置 token 集合多算 cultist/tablet/elder_thing；时机在 resolve 时。
   - 修法：combat_bonus 用 ctx.source fallback；token 集合 {SKULL, AUTO_FAIL}；弃置延迟到 SKILL_TEST_ENDS。CN 修。
8. **18_derringer_lv0** | 实现错误（弹药经济）+【翻译错误】
   - 卡面（60505）：使用(2弹药)。[action]花1弹药：攻击+2战斗+1伤害；若失败放1弹药回枪（净耗0）。
   - 实现：成功才扣弹药；失败无条件+1弹药（净赚1）；0弹药仍可攻击。
   - 修法：发动时扣1弹药（无弹药禁止用作武器）；失败返还至多回到上限2。test_18_derringer.py::test_refund_ammo_on_fail 断言 2→3 是错的，同步改。CN 修（"3弹药"错、漏失败回弹药）。
9. **leather_coat_lv0** | 实现错误+【翻译错误】
   - 卡面：无能力——2生命的护甲资产（soak，data 已有 health:2）。
   - 实现：继承 BulletproofVest 给调查员+2生命上限。
   - 修法：实现应为空效果（加入 _ALLOWED_INERT 白名单并写清 docstring：soak 由引擎资产伤害分配处理）；CN 改描述性说明。
10. **scavenging_lv0** | 实现错误+【简化超界】+【翻译错误】
    - 卡面：成功调查且超出≥2后，横置拾荒：选择弃牌堆一张 Item 入手（可重复用）。
    - 实现：横置写成弃置；自动拿第一张；未限定调查。
    - 修法：弃置→横置（exhaust 检查+置位）；自动选第一张+注明简化；限定调查（INVESTIGATE_ACTION_INITIATED）。CN 修。
11. **rabbits_foot_lv0** | 实现错误+【翻译错误】
    - 卡面：失败后横置兔脚：抽1（每轮至多一次——横置天然限次）。
    - 实现：无横置检查，每次失败都抽。
    - 修法：加 exhausted 检查与置位；CN 改"反应"并补横置。
12. **peter_sylvestre_lv0** | 实现不完整
    - 卡面：+1敏捷；回合结束后治愈自身1恐惧。
    - 实现：漏治愈反应（lv2 文件里有现成的照抄）。
13. **lucky_lv2** | 实现错误+【翻译错误】
    - 卡面：+2技能值，抽1张牌（无论成败）。
    - 实现：按错误CN做成"成功则回手"。
    - 修法：改为无条件抽1张，删除 return_on_success（注意 lucky_lv0 父类已有 bonus/margin 逻辑，lv2 子类加抽牌即可）；CN 重写。test_lucky.py 里 test_lv2_returns_to_hand_only_on_success 需同步改为抽牌断言。
14. **close_call_lv2** | 实现错误+【简化超界】+【翻译错误】
    - 卡面（01083）：非弱点非精英敌人在你所在地点被躲避后打出（允许他人躲避触发）。
    - 实现：无精英检查；自动打出自动扣2资源。
    - 修法：加 is_elite_enemy+non-weakness 检查；自动打出保持+注明简化。CN 补"非精英"。
15. **look_what_i_found_lv0** | 实现错误+【简化超界】+【翻译错误】
    - 卡面：调查检定失败且差值≤2时打出。
    - 实现：任何检定失败都自动打出扣2资源。
    - 修法：限定 intellect+difficulty-modified_skill<=2；自动打出保持+注明。CN 补两条件。
16. **dig_deep_lv0** | 已随引擎修复（_armed 计数制）| 验证即可。

**纯数据问题**
17. **stray_cat_lv0** | 【数据文本错误】| 官方01076：[fast] Discard: 自动躲避你所在地点一个非精英敌人 | data EN 漏 [fast] 且窄化 "engaged with you" | data EN 补 [fast]、目标改 "at your location"；实现放宽到所在地点非精英敌人；JSON 补 "fast": true。

## 无问题清单
bait_and_switch_lv0、peter_sylvestre_lv2、wendy_adams、ashcan_pete（data/investigators/ashcan_pete.json 缺"至多5张任意职业0级卡"deck 选项——登记不阻塞）

## 测试注意
test_18_derringer.py（弹药2→3）、test_lucky.py lv2 回手断言把错误固化了，修复时同步改。
