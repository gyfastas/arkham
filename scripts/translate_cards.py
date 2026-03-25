#!/usr/bin/env python3
"""Bulk translate card texts to Simplified Chinese."""

import json
from pathlib import Path

# Translation dictionary: card_id -> text_cn
# Skill cards with no English text get empty string
TRANSLATIONS = {
    # Guardian cards
    "evidence_lv0": "<b>快速</b>。在你击败一名敌人后打出。在你的地点发现1条线索。",
    "physical_training_lv0": "花费1资源：本次技能检定+1意志。花费1资源：本次技能检定+1战斗。",
    "guard_dog_lv0": "<b>强制</b> - 在你受到敌人伤害后：对攻击者造成1点伤害。",
    "first_aid_lv0": "消耗急救并花费1资源：治愈你所在地点的一名调查员或盟友2点伤害。",
    "first_aid_lv3": "消耗急救并花费1资源：治愈你所在地点的一名调查员或盟友3点伤害。",
    "machete_lv0": "<b>仅限一次攻击</b>。当你使用弯刀攻击时，你获得+1战斗。如果你在攻击中未受到敌人的伤害，本次攻击造成+1伤害。",
    "beat_cop_lv0": "你获得+1战斗。<b>强制</b> - 当巡警入场时：放置1点伤害在巡警上。<b>反应</b> - 弃置巡警：对一个在你地点的敌人造成1点伤害。",
    "beat_cop_lv2": "你获得+1战斗。<b>反应</b> - 弃置巡警：对一个在你地点的敌人造成2点伤害。",
    "45_automatic_lv0": "使用(4弹药)。消耗.45自动手枪并花费1弹药：<b>攻击</b>。你获得+1战斗，本次攻击造成+1伤害。",
    "shotgun_lv4": "使用(2弹药)。消耗霰弹枪并花费1弹药：<b>攻击</b>。本次攻击造成+2伤害。如果你成功且超过难度2点以上，本次攻击造成额外+1伤害。",
    "dodge_lv0": "<b>快速</b>。在你所在地点的敌人攻击时打出。取消本次攻击。",
    "vicious_blow_lv0": "如果你成功，本次攻击造成+1伤害。",
    "dynamite_blast_lv0": "选择你所在地点或一个连接地点。对该地点的每个敌人和调查员造成3点伤害（包括你自己）。",
    "extra_ammunition_lv1": "你每控制一把占用2个手槽位的武器，手槽位上限+1。<b>反应</b> - 在你打出一张有'使用(弹药)'的支援卡后：在其上放置2弹药。",
    "police_badge_lv2": "你获得+1意志。<b>反应</b> - 弃置警徽：你获得2个额外行动。",
    "ive_had_worse_lv4": "<b>快速</b>。在你将受到3点或更多伤害或恐惧时打出。取消最多3点该伤害或恐惧。",
    "teamwork_lv0": "<b>快速</b>。在调查阶段，选择一名在你所在地点的调查员。该调查员获得1资源或抽取1张牌。",
    "taunt_lv0": "<b>快速</b>。选择你所在地点的每个敌人。与那些敌人交战。",
    "taunt_lv2": "<b>快速</b>。选择你所在地点的每个敌人。与那些敌人交战。然后，立即结算一次敌人攻击。",
    "blackjack_lv0": "你获得+1战斗。如果你在与一个已交战的敌人战斗时成功，本次攻击造成+1伤害。",

    # Seeker cards
    "ive_got_a_plan_lv0": "<b>快速</b>。在进行一次智力检定时打出。你获得+2智力，本次检定造成+1伤害。",
    "disc_of_itzamna_lv2": "<b>反应</b> - 当一个非精英敌人将在你的地点生成时：弃置伊察姆纳圆盘，改为将该敌人弃置（不生成）。",
    "art_student_lv0": "<b>强制</b> - 当艺术生入场时：在你的地点发现1条线索。",
    "preposterous_sketches_lv0": "<b>洞察</b>。如果你所在地点有线索，抽取2张牌。",
    "medical_texts_lv0": "消耗医学教科书：你获得+2智力。",
    "old_book_of_lore_lv0": "消耗智慧古书：查看你牌库顶的3张牌。将其中1张加入手牌，其余以任意顺序置于牌库底。",
    "old_book_of_lore_lv3": "消耗智慧古书：查看你牌库顶的3张牌。将其中1张加入手牌，其余以任意顺序置于牌库底。然后，你可以花费1资源：抽取1张牌。",
    "magnifying_glass_lv0": "你获得+1智力。",
    "magnifying_glass_lv1": "你获得+1智力。",
    "inquiring_mind_lv0": "在进行一次检定以躲避敌人或调查时打出。你获得+2本次技能类型。",
    "expose_weakness_lv1": "选择一个在你地点的敌人。查看该敌人的牌面文字。发现1条线索（如果该敌人是精英，则改为发现2条线索）。",
    "barricade_lv0": "将屏障附加到你所在地点。被附加的地点不能生成非精英敌人。",
    "mind_over_matter_lv0": "在进行一次攻击时打出。本次攻击使用智力代替战斗。",
    "seeking_answers_lv2": "<b>快速</b>。在你成功调查超过难度2点或以上后打出。发现并消耗该地点的一个线索，发现一个相邻地点的线索。",
    "dr_milan_christopher_lv0": "你获得+1智力。<b>反应</b> - 在你成功调查后：获得1资源。",
    "working_a_hunch_lv0": "<b>洞察</b>。发现并消耗你所在地点的一个线索。",
    "research_librarian_lv0": "<b>强制</b> - 当研究馆员入场时：搜索你的牌库，将一张<b>典籍</b>支援卡加入手牌，然后洗牌。",
    "hyperawareness_lv0": "花费1资源：+1智力。花费1资源：+1敏捷。",
    "encyclopedia_lv2": "消耗百科全书并花费1资源：你选择一名调查员。该调查员在你所在地点，获得+2你选择的技能值，直到本阶段结束。",
    "deduction_lv0": "如果你成功超过难度2点或以上，你发现额外1条线索。",
    "cryptic_research_lv4": "抽取3张牌。",
    "strange_solution_lv0": "<b>调查</b>。使用神秘溶液代替智力。如果你成功，改为获得2资源。",
    "preposterous_sketches_lv2": "抽取3张牌。",
    "crack_the_case_lv0": "<b>快速</b>。在你所在地点的最后一个线索被发现后打出。获得3资源。",

    # Rogue cards
    "forty_one_derringer_lv0": ".41短口手枪",
    "forty_one_derringer_lv2": ".41短口手枪",
    "sneak_attack_lv0": "对一个与你交战的敌人造成2点伤害。",
    "elusive_lv0": "<b>快速</b>。与所有敌人脱离交战，移动到一个没有敌人的已揭示地点。",
    "pickpocketing_lv0": "<b>反应</b> - 在你成功躲避一次攻击后：抽取1张牌。",
    "cat_burglar_lv1": "你获得+1敏捷。<b>反应</b> - 在你成功躲避后：消耗飞贼并获得2资源。",
    "you_handle_this_one_lv0": "选择一名调查员。该调查员与你交战一个在你地点的敌人。",
    "backstab_lv0": "<b>攻击</b>。本次攻击使用敏捷代替战斗。你获得+2敏捷，本次攻击造成+1伤害。",
    "opportunist_lv0": "如果你成功，返回机会主义者到你的手中。",
    "leo_de_luca_lv0": "里奥·德·卢卡进场时带有1个行动指示物。每轮你可以花费里奥·德·卢卡上的行动指示物，如同那是你的额外行动。",
    "leo_de_luca_lv1": "里奥·德·卢卡进场时带有2个行动指示物。每轮你可以花费里奥·德·卢卡上的行动指示物，如同那是你的额外行动。",
    "hard_knocks_lv0": "花费1资源：+1战斗。花费1资源：+1敏捷。",
    "switchblade_lv0": "<b>快速</b>。消耗弹簧刀：<b>攻击</b>。你获得+1战斗，本次攻击造成+1伤害。",
    "lockpicks_lv1": "消耗撬锁工具：<b>调查</b>。你获得+3智力。如果这次检定失败，弃置撬锁工具。",
    "burglary_lv0": "<b>调查</b>。使用敏捷代替智力。如果你成功，获得3资源而不是发现线索。",
    "sure_gamble_lv3": "<b>快速</b>。在你揭示一个混沌标记后打出。无视该混沌标记，改为揭示另一个混沌标记。",
    "hot_streak_lv4": "获得10资源。",
    "think_on_your_feet_lv0": "<b>快速</b>。在你抽取一张非弱点诡计卡时打出。躲避该诡计来源的敌人，然后移动到一个连接地点。",
    "hired_muscle_lv1": "你获得+1战斗。",
    "double_or_nothing_lv0": "<b>快速</b>。在你揭示一个混沌标记时打出。将本次技能检定的难度加倍。如果你成功，将获得的任何东西（伤害、线索、资源）加倍。",

    # Survivor cards
    "will_to_survive_lv3": "<b>快速</b>。在你回合开始时打出。直到本回合结束，你每有一个已揭示的混沌标记，你获得+1所有技能。",
    "look_what_i_found_lv0": "<b>快速</b>。在你检定失败后打出。在你所在地点发现2条线索。",
    "aquinnah_lv3": "<b>反应</b> - 当你受到敌人伤害时：弃置安奎娜。取消该伤害，改为对该敌人造成2点伤害。",
    "aquinnah_lv1": "<b>反应</b> - 当你受到敌人伤害时：弃置安奎娜。取消该伤害，改为对该敌人造成1点伤害。",
    "scavenging_lv0": "<b>反应</b> - 在你成功调查并超过难度2点或以上后：弃置拾荒，从你的弃牌堆中将一张<b>道具</b>支援卡加入你的手牌。",
    "stray_cat_lv0": "<b>快速</b>。弃置野猫：自动成功躲避一个与你交战的非精英敌人。",
    "eucatastrophe_lv3": "<b>快速</b>。在你将要被击败时打出。改为弃置你手牌中所有的弱点，恢复所有生命和理智，获得3资源，结束你本回合。",
    "rabbits_foot_lv0": "<b>强制</b> - 在你检定失败后：抽取1张牌。",
    "lucky_lv0": "<b>快速</b>。在你检定失败后打出。获得+2本次技能。",
    "lucky_lv2": "<b>快速</b>。在你检定失败后打出。获得+2本次技能。如果你成功，返回运气好！到你的手中。",
    "18_derringer_lv0": "使用(3弹药）。消耗.18大口径短口手枪并花费1弹药：<b>攻击</b>。你获得+2战斗，本次攻击造成+1伤害。",
    "close_call_lv2": "<b>快速</b>。在你躲避一个敌人后打出。将该敌人洗入遭遇牌堆。",
    "leather_coat_lv0": "你获得+2生命值。",
    "cunning_distraction_lv0": "所有与你交战的敌人失去交战，移动到一个你选择的已揭示地点。",
    "baseball_bat_lv0": "消耗球棒：<b>攻击</b>。你获得+2战斗，本次攻击造成+1伤害。如果这次攻击揭示一个负面混沌标记，弃置球棒。",
    "dig_deep_lv0": "花费1资源：+1意志。花费1资源：+1敏捷。",
    "survival_instinct_lv0": "<b>快速</b>。在你躲避检定失败时打出。改为成功，然后你可以移动到一个连接地点。",
    "bait_and_switch_lv0": "<b>快速</b>。在你与一个敌人交战时打出。对该敌人造成1点伤害，并躲避它。",
    "fire_axe_lv0": "消耗消防斧：<b>攻击</b>。你获得+1战斗，本次攻击造成+1伤害。你可以花费最多2资源，每花费1资源额外+1战斗和+1伤害。",
    "peter_sylvestre_lv0": "你获得+1意志，+1敏捷。",
    "peter_sylvestre_lv2": "你获得+1意志，+1敏捷。在你回合开始时，治愈彼得·西尔维斯特上1点伤害或1点恐惧。",

    # Mystic cards
    "shrivelling_lv0": "使用(4充能）。消耗皱缩术并花费1充能：<b>攻击</b>。本次攻击使用意志代替战斗。你获得+1战斗，本次攻击造成+1伤害。如果这次攻击揭示一个负面混沌标记，受到1点恐惧。",
    "rite_of_seeking_lv0": "使用(3充能）。消耗礼寻术并花费1充能：<b>调查</b>。本次调查使用意志代替智力。你获得+2智力，本次调查发现额外1条线索。如果你成功且超过难度2点以上，发现额外1条线索。",
    "rite_of_seeking_lv2": "使用(3充能）。消耗礼寻术并花费1充能：<b>调查</b>。本次调查使用意志代替智力。你获得+2智力，本次调查发现额外1条线索。",
    "scrying_lv0": "使用(3充能）。消耗探知术并花费1充能：查看一名调查员牌库顶的3张牌。该调查员可以将其中任意张置于其牌库底，其余以任意顺序置于其牌库顶。",
    "scrying_lv3": "使用(3充能）。消耗探知术并花费1充能：查看一名调查员牌库顶的3张牌。该调查员可以将其中任意张置于其牌库底，其余以任意顺序置于其牌库顶。然后，该调查员抽取1张牌。",
    "arcane_studies_lv0": "花费1资源：+1意志。花费1资源：+1智力。",
    "arcane_initiate_lv0": "<b>强制</b> - 在刷新阶段开始时：弃置新晋术士或在其上放置1点恐惧。<b>反应</b> - 在新晋术士进场时或在其上有恐惧放置时：搜索你的牌库，将一张<b>法术</b>支援卡加入手牌，然后洗牌。",
    "blinding_light_lv0": "<b>法术</b>。消耗眩光一闪并花费1充能：<b>躲避</b>。本次躲避使用意志代替敏捷。你获得+3敏捷。如果你成功且超过难度2点以上，返回眩光一闪到你的手中。",
    "blinding_light_lv2": "<b>法术</b>。消耗眩光一闪并花费1充能：<b>躲避</b>。本次躲避使用意志代替敏捷。你获得+4敏捷。",
    "drawn_to_the_flame_lv0": "<b>快速</b>。发现并消耗你所在地点的所有线索。然后，从遭遇牌堆顶抽取一张牌。",
    "grotesque_statue_lv4": "使用(4充能）。<b>快速</b>。在你揭示一个混沌标记时：花费1充能。取消该标记，改为揭示另一个混沌标记。",
    "ward_of_protection_lv0": "<b>快速</b>。在你抽取一张非弱点诡计卡时打出。取消该卡的所有效果，弃置它。然后，受到1点恐惧。",
    "book_of_shadows_lv3": "你每控制一张<b>法术</b>支援卡，你获得+1意志和+1智力。",
    "fearless_lv0": "如果你成功，治愈1点恐惧。",
    "holy_rosary_lv0": "你获得+1意志。",
    "mind_wipe_lv1": "<b>快速</b>。选择你所在地点或一个连接地点的一个非精英敌人。取消该敌人直到本阶段结束的所有文本效果。",
    "forbidden_knowledge_lv0": "禁忌知识进场时带有4个秘密。<b>反应</b> - 在禁忌知识上有秘密时：花费1秘密并受到1点恐惧，获得2资源。",
    "bind_monster_lv2": "<b>法术</b>。使用(3充能）。消耗束缚怪物并花费1充能：<b>交战</b>。自动与一个在你地点的非精英敌人交战。如果你成功且超过难度2点以上，你躲避该敌人。",
    "ritual_candles_lv0": "在你进行技能检定时：你获得+1技能值。",
    "fearless_lv0": "如果你成功，治愈1点恐惧。",

    # Neutral cards - skill cards with empty text
    "guts_lv0": "",  # Skill card
    "emergency_cache_lv0": "获得3资源。",
    "emergency_cache_lv2": "获得3资源，抽取1张牌。",
    "unexpected_courage_lv0": "",  # Skill card
    "perception_lv0": "如果你成功，抽取1张牌。",
    "overpower_lv0": "如果你成功，本次攻击造成+1伤害。",
    "manual_dexterity_lv0": "",  # Skill card
    "knife_lv0": "消耗刀子：<b>攻击</b>。你获得+1战斗。",
    "flashlight_lv0": "消耗手电筒并花费1补给：<b>调查</b>。你所在地点的隐蔽值降低2，直到本次调查结束。",
    "bulletproof_vest_lv3": "你获得+4生命值。",
    "elder_sign_amulet_lv3": "你获得+4理智。",
    "relic_hunter_lv3": "你获得2个额外的饰品槽位。",
    "charisma_lv3": "你获得2个额外的盟友槽位。",
    "kukri_lv0": "消耗库克里刀：<b>攻击</b>。你获得+2战斗。",
}

def update_card_translations():
    base = Path("data/player_cards")
    updated = 0
    not_in_dict = []

    for p in base.rglob("*.json"):
        if p.name == "schema.json":
            continue

        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            card_id = data.get("id", p.stem)
            card_type = data.get("type", "")

            # Check if card is in our translation dict
            if card_id in TRANSLATIONS:
                text_cn = TRANSLATIONS[card_id]
                current = data.get("text_cn", None)

                # Update if missing or empty
                if current is None or (isinstance(current, str) and current.strip() == ""):
                    data["text_cn"] = text_cn
                    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    updated += 1
                    print(f"✓ {card_id}")
            else:
                # Check if card needs translation but not in dict
                text = data.get("text", "")
                text_cn = data.get("text_cn", "")

                # Skip skill cards with empty English text
                if text == "" and card_type == "skill":
                    if text_cn == "":
                        # Already correctly empty
                        pass
                    elif text_cn is None:
                        data["text_cn"] = ""
                        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                        updated += 1
                elif text and (not text_cn or text_cn.strip() == ""):
                    if card_id not in not_in_dict:
                        not_in_dict.append(card_id)

        except Exception as e:
            print(f"Error processing {p}: {e}")

    print(f"\n=== Updated: {updated} cards ===")

    if not_in_dict:
        print(f"\n=== Not in translation dict ({len(not_in_dict)} cards) ===")
        for cid in sorted(not_in_dict):
            print(f"  - {cid}")

if __name__ == "__main__":
    update_card_translations()
