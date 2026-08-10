# Guardian 阵营卡牌审计报告（2026-08-08）

**关键的引擎级事实**（多条问题的根源）：
- `DAMAGE_DEALT` 只在对敌人造成伤害时发出（backend/engine/damage.py:104）；调查员/盟友受伤发 `DAMAGE_ASSIGNED`/`HORROR_ASSIGNED`；`HORROR_DEALT` 全引擎从未发出。
- `SKILL_VALUE_DETERMINED` 的 extra 不含 `weapon_card_id`；`SKILL_TEST_SUCCESSFUL` 的 `enemy_id` 恒为 None。用 `ctx.source` 判定武器（参照 machete 的 source fallback 写法）。
- 引擎不负责扣弹药；`ENEMY_DEFEATED` 现已携带击败者 investigator_id 与 extra.card_id（2026-08-08 已修）。

## 需要修复

| card_id | 问题类型 | 卡面怎么说 | 实现怎么做 | 建议修法 |
|---|---|---|---|---|
| evidence_lv0 | 实现永不触发（致命） | Fast. Play after you defeat an enemy. Discover 1 clue. | 监听 ENEMY_DEFEATED 且要求 ctx.extra["card_id"]=="evidence_lv0"——事件 extra 是敌人的 card_id，永不等价 | 改监听 CARD_PLAYED+card_id 匹配（dynamite_blast 模式），打出窗口由会话层控制 |
| guard_dog_lv0 | 实现永不触发+对象错；【翻译错误】 | 敌人攻击对看门狗造成伤害时：反击攻击者1点 | 监听 DAMAGE_DEALT（只对敌人）→ 永不触发；未检查伤害是否分配给狗 | 在调查员受伤分配流程检测 target==本卡再反击（DAMAGE_ASSIGNED 路线）；text_cn"在你受到敌人伤害后"主体错误，应为"当敌人攻击对看门狗造成伤害后" |
| ive_had_worse_lv4 | 实现全面错误且有害；【翻译错误】 | 你被造成伤害/恐惧时打出：取消最多5点，并获得等量资源 | 监听 DAMAGE_DEALT/HORROR_DEALT → 你对敌人造成≥3伤害时误触发，自动打出减掉自己输出；取消3点（非5）、无≥3条件、不给资源 | 若无取消窗口则改为：监听 DAMAGE_ASSIGNED/HORROR_ASSIGNED（对自己）并在伤害结算后补偿资源+减伤记录，或标记为需要引擎取消窗口并在报告中说明；text_cn 的"≥3点才能打出、取消3点"全系编造 |
| shotgun_lv4 | 效果完全不符；【翻译错误】；数据英文轻微残缺 | +3战斗；伤害=成功超出点数（下限1上限5） | 无+3战斗；命中+2伤害、超2点再+1（因 ctx 无 enemy_id 永不生效）；弹药只命中才扣 | 重写：SKILL_VALUE_DETERMINED 给+3（限定本枪攻击，用 ctx.source 判定），伤害 min(max(succeed_by,1),5)；数据英文补 "Spend 1 ammo"；text_cn 重写 |
| first_aid_lv0 | 效果不符；【翻译错误】 | Uses (3 supplies). 花1补给：治同地点调查员1伤害或1恐惧 | 无补给机制，横置+1资源治2点伤害，不能治恐惧、无地点限制 | 按卡面重做（3补给、治1、可选伤害/恐惧，uses 已补进数据 {"supplies":3}——注意如数据键名不一致需对齐）；text_cn 同步 |
| first_aid_lv3 | 效果不符；【翻译错误】 | Uses (4 supplies). 花1补给：治1伤害和1恐惧（调查员或盟友） | 继承 lv0 | 同上重做；text_cn 同步 |
| beat_cop_lv2 | 实现复制 lv0 完全错误；【翻译错误】 | 横置巡警并对它造成1伤害：对同地点敌人造成1伤害 | 与 lv0 逐字相同：弃置巡警造成1伤害 | 重写为横置+自伤1点的激活能力；text_cn"弃置…造成2点伤害"双错 |
| beat_cop_lv0 | 目标范围收窄；【翻译错误】 | 对你所在地点的一个敌人造成1伤害 | 只允许打交战敌人 | 放宽为同地点敌人；text_cn 编造"入场放置1伤害"应删 |
| extra_ammunition_lv1 | 数值错误；【翻译错误】 | 在同地点任意调查员控制的 Firearm 上放3弹药 | 放2弹药；不校验 Firearm | 改3弹药+Firearm traits 校验；text_cn 是另一张卡的文本，整段重翻 |
| police_badge_lv2 | 能力缺失 | [fast] 同地点调查员回合中弃置：该调查员本回合+2行动 | 只有+1意志 | 补弃置激活能力（公开方法即可） |
| blackjack_lv0 | 加成永不生效 | [action] Fight，+1战斗；对与他人交战的敌人失手不误伤 | combat_bonus 要求 ctx.extra["weapon_card_id"]（引擎从不设置）→ +1永不生效 | 改用 ctx.source 判定（参照 machete fallback）；误伤保护引擎天然成立（简化合理） |
| 45_automatic_lv0 | 弹药流程偏差 | 弹药是发动成本：打不中也扣；无弹药不能用 | 只在命中时扣弹药；0弹药仍能攻击 | 若引擎无发起扣费通道，保持命中扣费但 0 弹药禁用攻击能力；在报告中说明 |
| dodge_lv0 | 【简化超界】+目标收窄；数据英文残缺 | 敌人在你地点攻击任一调查员时打出（玩家自选时机） | 敌人攻击你时不经询问自动打出 | 保持自动触发（本次不接 UI 选择），但文档注释标明；数据英文补 "an investigator at your location" |
| taunt_lv0 / taunt_lv2 | 【简化超界】 | 与任意数量（玩家选择）同地点敌人交战 | 自动交战全部未交战敌人 | 保持现状（需 UI 选择流），报告注明 |
| zoey_samaras | 远古印记+1伤害永不生效 | 印记：+1；攻击中检定成功则+1伤害 | 标记写在 CHAOS_TOKEN_RESOLVED ctx.extra，却在 SKILL_TEST_SUCCESSFUL 新 ctx 检查且 enemy_id 恒 None → 死代码 | 通过 source/战斗上下文在成功事件直接判定 |
| teamwork_lv0 | 次要规则偏差 | 交易改变控制权，所有权不变 | 连 owner_id 一起改 | 保留原 owner_id，只改 controller_id |
| physical_training_lv0 | 已随引擎修复 | 每次检定可多次支付叠加 | _armed_skill 单槽 | ResourceSkillBoost 已改计数制（2026-08-08），验证即可 |

**数据文本轻微残缺**（顺手补全）：dodge_lv0 英文漏地点范围；beat_cop_lv2 英文漏 "at your location"；ive_had_worse_lv4 英文漏打出窗口；shotgun_lv4 英文漏 "Spend 1 ammo"；first_aid_lv0/lv3 英文漏 "无补给则弃置"；extra_ammunition_lv1 英文漏目标限定；police_badge_lv2 英文漏时机窗口。45_automatic_lv0 text_cn 多出"消耗（横置）手枪"（次要）；police_badge_lv2 text_cn "你获得"窄化为"该调查员"。

## 无问题清单
- machete_lv0、vicious_blow_lv0、dynamite_blast_lv0、roland_banks

## 总评
对应 guardian 测试多为 skeleton 占位（test_guard_dog、test_ive_had_worse、test_first_aid 只断言 card_id）——修复时必须把行为测试补上。
