# Mystic 阵营卡牌审计报告（2026-08-08）

**系统性问题（已修复，验证即可）**：所有 mystic 数据 JSON 曾缺 `uses` 字段导致 7 张卡 0 充能无法发动。2026-08-08 已补数据并对齐键名（charges）：
clarity_of_mind_lv0=3、scrying_lv0=3、scrying_lv3=3、shrivelling_lv0=4、rite_of_seeking_lv0/lv2=3、grotesque_statue_lv4=4。

**注意**：server/game_session.py 对 clarity_of_mind_lv0、rite_of_seeking_lv0 有特判激活处理器（会错误地 exhaust 卡牌——官方卡面无横置要求）。本批次允许修改 server/game_session.py 中这两处特判：去掉 `ci.exhausted = True`（clarity_of_mind、rite_of_seeking 均无 exhaust 费用）。

## 需要修复

| card_id | 问题类型 | 卡面（真实文本） | 实现 | 建议修法 |
|---|---|---|---|---|
| arcane_initiate_lv0 | 实现与卡面不符+【翻译错误】 | 01063: 强制-进场后放1 doom；【快速】横置：搜牌库顶3张找法术，抽取，洗牌 | 跟随错误中文：刷新阶段放 horror；自动搜整个牌库；无横置 | 进场放 inst.doom；改 activations 横置发动、只搜顶3张；text_cn 重翻 |
| blinding_light_lv0 | 实现与卡面不符+【翻译错误】+数据残缺 | 01066: 躲避用意志代敏捷；成功对刚躲避的敌人造成1伤害；若揭示 skull/cultist/tablet/elder_thing/auto_fail，本回合失去1行动 | 意志+3 替换；成功超2点回手牌；无伤害、无负面条款 | 重写：无+3、无回手；成功1伤害+坏标记失去1行动。text_cn 张冠李戴需重翻；data text 漏坏标记条款 |
| blinding_light_lv2 | 同上 | 01069: 同上但2伤害；坏标记→失去1行动并受1恐惧 | 意志+4，无伤害无条款 | 同上重写；text_cn 重翻 |
| book_of_shadows_lv3 | 实现与卡面不符+【翻译错误】 | 01070: +1奥秘槽；【行动】横置：给你控制的一张法术加1充能 | 每控制一张法术+1意志+1智力（编造） | 实现奥秘槽扩展（参考 slots.py/SlotManager）+横置充能 action；删技能加值。text_cn 重翻 |
| scrying_lv0 | 实现超界+【翻译错误】 | 01061: 【行动】横置+1充能：看任一调查员牌库或遭遇牌堆顶3张，任意顺序放回顶（无置底） | 可置底、不能选遭遇牌堆 | 去掉置底；支持遭遇牌堆目标；重排若无可选 UI 则保持顺序+注释简化。text_cn 修"置于牌库底" |
| scrying_lv3 | 同上+数据残缺 | 03236: 【快速】横置+1充能：看顶3张任意放回顶；若有 Terror 或 Omen 卡受1恐惧（无抽牌无置底） | lv0 行为+抽1张（编造） | 去抽牌去置底、加恐惧条款。text_cn 重翻；data text 补恐惧条款 |
| rite_of_seeking_lv2 | 实现缺条款+【数据文本错误】 | 51007(rtdwl): 意志代智力、+2、成功多1线索；坏标记惩罚仍在（失去剩余行动并结束回合） | bad_token_penalty=False 关闭惩罚 | 打开惩罚（继承 lv0 逻辑）；data text/text_cn 补该条款 |
| shrivelling_lv0 | 数值错误+多余 Exhaust+【翻译错误】 | 01060: 意志代战斗、+1伤害（无技能加值）、无需横置；坏标记受1恐惧 | 多给+1技能值；activate() 错误横置 | 去+1、去 exhausted=True。text_cn "+1战斗"误译，删 |
| forbidden_knowledge_lv0 | 数值错误+【翻译错误】 | 01058: 【快速】横置+受1恐惧：移1秘密到资源池作为1个资源；无秘密时弃置 | 给2资源；不横置；无抽空弃置 | 2→1资源；补横置与无秘密自弃。text_cn 改1 |
| drawn_to_the_flame_lv0 | 效果缺失+【翻译错误】 | 01064: 先抽遭遇牌堆顶1张，然后在所在地点发现2线索 | 只发现2线索，没抽遭遇牌 | 补遭遇牌抽取（ENCOUNTER_CARD_DRAWN 流程，先抽后发现）。text_cn 重翻 |
| ritual_candles_lv0 | 实现为空壳 | 02029: 你进行检定揭示 skull/cultist/tablet/elder_thing 后：本次检定+1技能值（多枚可叠加） | 事件体只有 pass | 监听 CHAOS_TOKEN_RESOLVED，命中四符号时对当前检定+1（注意只在你自己的检定：investigator_id 匹配控制者） |
| arcane_studies_lv0 | 已随引擎修复 | 每花1资源叠+1，可重复 | 单槽覆盖 | ResourceSkillBoost 已改计数制，验证即可 |
| grotesque_statue_lv4 | 【简化超界】 | 01071: 揭示时花1充能：改为揭示2枚由你选1枚；无充能时弃置 | 随机从 STANDARD_BAG 抽1枚替换（随机代替二选一，袋构成也错）；无自弃 | 用 game.chaos_bag（经 bind_chaos_bag 注入，现已接线）连抽2枚；若无可选 UI 则取对玩家较有利者并注释简化；补无充能自弃 |
| bind_monster_lv2 | 【简化超界】 | 02031: 被叠加敌人要准备时检定意志(3)：成功才不准备，失败弃置本卡 | prevent_ready 无条件重横置 | 保持现状（需检定回调流），报告注明 |
| ward_of_protection_lv0 | 【简化超界】 | 01065: 你抽非弱点诡计时可打出（可选不打出） | 自动强制打出 | 保持现状，报告注明 |
| agnes_baker | 【简化超界】 | 01004: 恐惧放置后触发；对所在地点一名敌人（玩家选）1伤害 |  allies 吸收也触发；自动选第一个敌人 | 触发条件改为 Agnes 实际 horror 增量>0；目标选择保持自动+vars 覆盖（现状可接受），报告注明 |
| mind_wipe_lv1 | 时点简化+【翻译错误】（轻） | 01068: 快速，阶段开始后打出；选你所在地点非精英敌人 | 未限时点；自动选首个 | 补"阶段开始后"时机关口（若引擎支持）；text_cn 删"或一个连接地点" |
| jim_culver | 数据缺失（轻） | 02004 deck_options: mystic 0-5 + neutral 0-5 + 任意阵营0级至多5张 | data/investigators/jim_culver.json 缺5张0级外挂位 | 补 deck_requirements（注意该文件在 data/investigators/，允许修改） |
| rite_of_seeking_lv0 | 多余 Exhaust | 02028: 【行动】花1充能：调查（不要求横置） | activate() 附加 exhausted=True | 去掉 exhausted=True（含 session 特判） |

## 无问题清单
- fearless_lv0、holy_rosary_lv0

## 注意
对应行为测试（test_arcane_initiate、test_blinding_light*、test_scrying*、test_forbidden_knowledge 等）目前锁定的是错误行为，修实现时需同步更新。
