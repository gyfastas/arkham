# Rogue 阵营卡牌审计报告（2026-08-08）

**总体模式**：大量 text_cn 与 text（英文=真卡）矛盾，实现照错误中文写；若干实现读了引擎从不提供的 EventContext 字段，测试靠手工构造假 ctx 掩盖。

**已完成的引擎修复（验证即可）**：leo_de_luca_lv0/lv1 已改挂 INVESTIGATOR_TURN_BEGINS（测试已同步）；hard_knocks_lv0 的叠加问题已随 ResourceSkillBoost 计数制修复；double_or_nothing 所需引擎通道 `_st2_commit` 已传入并回读 ctx.difficulty（2026-08-08）；liquid_courage_lv0 数据已补 uses {"supplies":4}（impl 键名已对齐 supplies）；lockpicks_lv1 数据已有 {"supply":3}。

## 需要修复

| card_id | 问题类型 | 卡面怎么说 | 实现怎么做 | 建议修法 |
|---|---|---|---|---|
| backstab_lv0 | 实现错误+【翻译错误】 | 01051：敏捷代替战斗，+2伤害，无技能加值 | 替换敏捷时额外+2技能值，伤害只+1 | substitute_agility 去+2；bonus_damage 改+2；CN 删+2敏捷改"+2伤害" |
| burglary_lv0 | 实现错误+【翻译错误】 | 01045：消耗 Burglary：调查；成功改拿3资源。无敏捷代智力 | 照错误CN加敏捷代智力；activate() 不 exhaust | 删 substitute_agility；activate() 加 inst.exhausted=True；CN 删敏捷条款 |
| cat_burglar_lv1 | 实现错误+【数据文本错误】+【翻译错误】 | 真卡01055：+1敏捷；[行动]消耗：脱离每个与你交战的敌人并移至相连地点，不触发借机攻击 | ①+1敏捷处理器读 ctx.extra["skill_type"]/写 ctx.extra["skill_value"]——永不生效；②主动能力未实现 | 改用 ctx.skill_type == Skill.AGILITY + modify_amount(1)；activations 补主动能力；EN 补 "each enemy"+不触发借机攻击；CN 重写 |
| double_or_nothing_lv0 | 实现错误 | 02026：难度加倍；成功则胜利效果结算两次 | 难度加倍不生效（引擎通道现已补）；双倍结算只简化为"调查多拿1线索" | 难度加倍接通 ctx.difficulty；双倍结算至少补战斗 bonus_damage 通道；其余注明简化 |
| elusive_lv0 | 【简化超界】（轻） | 01050：Fast 仅限你的回合；脱离所有敌人并移至任意无敌人的已揭示地点 | 只在连接地点选、不检查 revealed | fallback 遍历 revealed 且无敌人的地点；EN 补 "Play only during your turn" |
| forty_one_derringer_lv0 | 实现错误+【翻译错误】 | 01047：花1弹药攻击，+2战斗，成功2点以上+1伤害 | margin 伤害缺失；clue_on_defeat 编造且死代码；_hit flag 时序死代码；弹药命中才扣 | margin 伤害在 SKILL_TEST_SUCCESSFUL 检查 margin≥2 写 ctx.extra["bonus_damage"]=1；删 clue 效果；CN 重写；弹药时机注明简化 |
| forty_one_derringer_lv2 | 实现错误+【翻译错误】 | 03234：成功1点以上+1伤害；每回合一次成功3点以上+1额外行动 | margin 阈值错（2）；缺额外行动 | margin=1；补"每回合一次 margin≥3 → actions_remaining+=1"；EN 补 "Once per turn"；CN 重写 |
| hired_muscle_lv1 | 【简化超界】（轻） | 02027：补给阶段结束必须选择付1资源或弃置 | 自动扣 | 保持自动付 fallback，报告注明；CN "丟棄1資源"改"支付" |
| liquid_courage_lv0 | 已修复数据 | 02024：Uses (4 supplies) | 已实现 | 验证目标满恐惧时仍可发动做检定（轻） |
| lockpicks_lv1 | 【数据文本错误】+【翻译错误】+实现错误 | 01687/03031：Uses(3 supplies)无补给则弃置；消耗：调查，敏捷值加到技能值；未成功2点以上移除1补给 | 数据EN写"花1补给、敏捷代替智力"；CN第三套（+3智力、失败弃置）；实现照CN | 三方统一按真卡重写：modify_amount(inv.get_skill(AGILITY))；激活只 exhaust 不花补给；失败且 margin<2 移除1补给；补给空则弃置 |
| opportunist_lv0 | 实现错误+【翻译错误】 | 01053：成功3点以上才回手 | 任意成功即回手 | 加 margin>=3（SKILL_TEST_SUCCESSFUL ctx 有 modified_skill/difficulty）；CN 补条件 |
| pickpocketing_lv0 | 实现错误+【翻译错误】 | 01046：躲避敌人后，消耗 Pickpocketing：抽1 | 不做 exhaust → 无限次 | 触发前检查 not exhausted，触发后 exhausted=True；CN 改"消耗扒窃" |
| sneak_attack_lv0 | 实现错误+【翻译错误】 | 01052：对你地点一个疲惫敌人造成2伤害 | 不校验疲惫/同地点；CARD_PLAYED extra 传不了 target → 正常路径无效果 | 若引擎不支持目标透传：实现为默认选同地点首个疲惫敌人+校验，注明简化；CN 重写 |
| sure_gamble_lv3 | 实现错误+【翻译错误】 | 01056：你揭示负修正标记后打出，把该标记"-"翻成"+" | 照错误CN无视并重抽：效果不对、从 STANDARD_BAG 抽、对任意标记自动触发会自动坑玩家 | 按 EN 重写：仅负修正标记（auto_fail 除外）触发，modify_amount(abs(ctx.amount)-ctx.amount) 翻号；CN 重写 |
| switchblade_lv0 | 实现错误+【翻译错误】 | 01044：Fast 攻击，成功2点以上+1伤害。没有+1战斗 | +1战斗编造且读 weapon_card_id 死代码；+1伤害无条件 | 删 combat_bonus；SKILL_TEST_SUCCESSFUL margin≥2 → ctx.extra["bonus_damage"]=1；CN 重写 |
| think_on_your_feet_lv0 | 【简化超界】（轻） | 02025：移至玩家自选连接地点 | 永远自动选第一个 | 保持现状注明 |
| you_handle_this_one_lv0 | 实现不完整+【翻译错误】 | 04028：你抽到非peril遭遇卡后打出，改由另一调查员视为抽到，你拿1资源 | 重定向是 pass 骨架 | 单人局无意义：保持+1资源，文本修正，注明多人待做；CN 重写；数据图标应 intellect+agility（现只有 agility） |

## 测试失真注意
test_cat_burglar.py 手工构造了引擎中永不出现的 ctx（extra["skill_type"]）——修卡时同步改测试。

## 无问题清单
hot_streak_lv4、jenny_barnes（调查员）、skids_otoole（调查员）、leo_de_luca_lv0/lv1（已修）
