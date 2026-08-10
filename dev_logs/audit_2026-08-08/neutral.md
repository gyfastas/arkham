# Neutral 阵营卡牌审计报告（2026-08-08）

**贯穿性问题**：所有"直接伤害/恐惧"写成 inv.damage/horror += N，绕过 DamageEngine._check_defeat，超限不会立即判负——引擎层问题，影响多张弱点卡。本批次不要逐张改，登记即可（后续引擎统一处理）。

**已完成的引擎修复（验证即可）**：rolands_38_special / jennys_twin_45s_lv0 数据已补 uses（ammo:4，jennys 按 FAQ X=4）；final_rhapsody_lv0 / rexs_curse_lv0 的 bind_chaos_bag 生产接线已完成（registry.activate_card 注入）。

## 需要修复

**阻断级**
- **hypochondria** | 触发反转+【数据文本错误】| 卡面：强制-在你受到≥1伤害后受1点直接恐惧 | 实现监听 DAMAGE_DEALT（只对敌人生效）→ 你打敌人≥1伤害时自己吃1恐惧 | 改监听调查员受伤事件（DAMAGE_ASSIGNED，对自己，amount≥1）；补 data 英文 text（"Revelation – Add Hypochondria to your deck... Forced – After you take 1 or more damage: Take 1 direct horror." 以 ArkhamDB 01015 为准核实）
- **jennys_twin_45s_lv0** | 【简化超界】| 卡面：花1弹药是攻击动作的费用（miss 也扣）| 命中才扣 | 若引擎无发起扣费通道，保持命中扣费但 0 弹药禁用攻击能力；报告注明
- **rolands_38_special** | 同上 | 同上 | 同上

**数值/效果与卡面不符**
- **overpower_lv0** | 【翻译错误】+实现走歪 | 真卡01091：Max 1 committed per skill test. If this test is successful, draw 1 card. | text_cn 写成"+1伤害"；生产路径 explicit_effect_selection 使成功时+1伤害而非抽牌；commit_effect_label 错 | text_cn 改"抽取1张牌"；删除+1伤害分支统一为抽牌（注意 skill_test.py 的 effect 卡流程，别把标签写错）
- **charisma_lv3** | 数值错误+【翻译错误】| 真卡02158：1 additional ally slot | bonus=2；text_cn"2个额外盟友槽位" | bonus 改1；text_cn 改"1个"；test_inert_batch.py:275 固化了+2需同步改
- **relic_hunter_lv3** | 同上 | 1 additional accessory slot | bonus=2 | 同上改1
- **knife_lv0** | 实现与卡面不符+【翻译错误】| 真卡01086：[action] Fight +1战斗／[action] 弃刀：Fight +2战斗+1伤害 | 只要刀在场任何战斗检定+1；弃刀能力未实现 | +1限定以刀攻击（ctx.source 判定）；新增弃刀攻击激活（公开方法）；重写 text_cn
- **dark_memory** | 实现与卡面不符 | 卡面：回合结束时在手牌中→展示并受2恐惧，牌留手牌每回合重复触发（无弃牌语句；类型 event 非 treachery）| 触发一次后弃牌注销；放毁灭后未立即检查密谋推进 | 触发后留手不置 spent；放毁灭后调用阈值检查
- **the_necronomicon** | 【数据文本错误×2】+实现缺能力 | 真卡01009 另有 "Treat each [elder_sign] you reveal as a [auto_fail]"；移动恐惧是 [action] 且含 "Then, if no horror, discard it" | data text 缺 elder_sign 句、误写 "Action (Free)"；实现缺 elder_sign→auto_fail | 补 elder_sign 转换效果（CHAOS_TOKEN_RESOLVED 命中 elder_sign 且控制者持此卡在场→force_auto_fail，引擎 skill_test._st4 已支持 ctx.extra["force_auto_fail"]）；修 data 两处文本
- **bulletproof_vest_lv3** | 实现与卡面不符+【翻译错误】| 真卡无文字、asset 自带4生命（承伤 soak）| 实现给调查员+4生命上限 | 本批次简化：保持 soak 语义不可达则改为"无效果+正确文本"，或在引擎允许下把伤害分配到非盟友 asset（损伤大则登记报告）；text_cn"你获得+4生命值"必须改
- **elder_sign_amulet_lv3** | 同上（sanity 方向）| soak 4 horror | +4理智上限 | 同上
- **zoeys_cross_lv0** | 实现超界：多出常驻启动能力 | 卡面只有一个 reaction（敌人与你交战后消耗+1资源→1伤害，经 ZoeySamaras 选择流实现）| 另挂了 activations "combat_damage"（0行动1资源横置→任意交战敌人1伤害） | 移除该 activation
- **cover_up** | 实现条件缺失（轻微）| 当你在你的地点将要发现线索时改弃卡上线索 | 不校验发现地点=所在地点 | 加地点一致性校验

**简化超界（本批次保持现状，报告注明）**
- searching_for_izzie_lv0（独立双行动能力被做成拦截任何成功发现）
- jims_trumpet_lv0（固定治控制者，不能选目标）
- on_the_lam（横置敌人代替取消攻击，影响多人局）

**纯数据/翻译问题**
- **wendys_amulet** | data text/text_cn 缺 "or discard an event from play" 触发 | 补文本；实现补事件从场上弃置的触发
- **flashlight_lv0** | text_cn 多出"消耗手电筒"；实现 activate() 里 exhausted=True 卡面没有；data 英文缺 [action] | 去 exhausted；修 text_cn；补 [action]
- **guts_lv0 / perception_lv0 / manual_dexterity_lv0 / unexpected_courage_lv0** | data text 缺 "Max 1 committed per skill test." | 补文本

## 无问题清单
abandoned_and_alone、chronophobia_lv0、internal_injury_lv0、indebted_lv0、emergency_cache_lv0/lv2、heirloom_of_hyperborea、search_for_the_truth_lv0、smite_the_wicked_lv0、hospital_debts、wracked_by_nightmares_lv0、duke_lv0、kukri_lv0、random_basic_weakness（占位）
