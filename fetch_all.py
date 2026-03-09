#!/usr/bin/env python3
"""
ArkhamDB 批量抓取脚本
使用 API 获取卡牌列表，然后抓取详细信息
"""

import requests
import re
import time
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# 配置
BASE_URL = "https://zh.arkhamdb.com/card/"
API_URL = "https://zh.arkhamdb.com/api/public/cards/"
OUTPUT_DIR = Path("/Users/bytedance/.openclaw/workspace/arkham/cards_infos")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# 阵营映射
FACTION_MAP = {
    'guardian': '守护者',
    'seeker': '探求者',
    'rogue': '流浪者',
    'mystic': '神秘学家',
    'survivor': '求生者',
    'neutral': '中立',
    '守护者': '守护者',
    '探求者': '探求者',
    '流浪者': '流浪者',
    '神秘学家': '神秘学家',
    '求生者': '求生者',
    '中立': '中立',
    '潛修者': '神秘学家',  # 繁体中文的 Mystic
}

def sanitize_filename(name):
    """清理文件名中的非法字符"""
    if not name:
        return "unknown"
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    name = name.strip('. ')
    if name.startswith('.') or not name:
        name = '_' + name
    return name

def extract_card_info(html, card_id):
    """从 HTML 中提取卡牌信息"""
    info = {
        "id": card_id,
        "name": "",
        "faction": "未知",
        "type": "",
        "slot": "",
        "traits": [],
        "cost": "",
        "text": "",
        "set": "",
        "set_number": "",
    }
    
    try:
        # 提取卡牌名称
        name_match = re.search(r'<h3[^>]*>.*?<a[^>]*href="https://zh\.arkhamdb\.com/card/\d+"[^>]*>([^<]+)</a>.*?</h3>', html, re.DOTALL)
        if name_match:
            info["name"] = name_match.group(1).strip()
        
        if not info["name"]:
            name_match2 = re.search(r'<h3[^>]*>([^<]+)</h3>', html)
            if name_match2:
                info["name"] = name_match2.group(1).strip()
        
        # 从 border-xxx class 提取阵营
        faction_match = re.search(r'border-(guardian|seeker|rogue|mystic|survivor|neutral)', html, re.I)
        if faction_match:
            info["faction"] = FACTION_MAP.get(faction_match.group(1).lower(), '未知')
        else:
            # 尝试从中文文本获取
            for faction_cn in FACTION_MAP:
                if faction_cn in html and faction_cn in ['守护者', '探求者', '流浪者', '神秘学家', '求生者', '中立']:
                    info["faction"] = FACTION_MAP[faction_cn]
                    break
        
        # 提取费用
        cost_match = re.search(r'费用:\s*(\d+|X)[\.\s]*<', html)
        if cost_match:
            info["cost"] = cost_match.group(1).strip()
        
        # 提取类型
        type_match = re.search(r'<p class="card-type">([^\u003c]+)</p>', html)
        if type_match:
            type_text = type_match.group(1).strip()
            if '。' in type_text:
                parts = [x.strip() for x in type_text.split('。') if x.strip()]
                if parts:
                    info["type"] = parts[0]
                if len(parts) > 1:
                    info["slot"] = parts[1]
            else:
                info["type"] = type_text
        
        # 提取特质
        traits_match = re.search(r'<p class="card-traits">([^\u003c]+)</p>', html)
        if traits_match:
            traits_text = traits_match.group(1).strip()
            if '。' in traits_text:
                info["traits"] = [t.strip() for t in traits_text.split('。') if t.strip()]
            else:
                info["traits"] = [traits_text]
        
        # 提取效果文本
        usage_match = re.search(r'使用\(([^)]+)\)[。\s]*', html)
        if usage_match:
            info["text"] = f"使用({usage_match.group(1)})"
            
            # 查找完整的效果段落
            full_effect = re.search(r'<p>使用\([^)]+\)[。\s]*</p>\s*<p>(.+?)</p>', html, re.DOTALL)
            if full_effect:
                action_html = full_effect.group(1)
                action_text = re.sub(r'<span[^>]*>[^<]*</span>', '', action_html)
                action_text = re.sub(r'<[^>]+>', '', action_text)
                info["text"] += "\n" + action_text.strip()
        
        # 如果没有使用(，尝试提取其他效果
        if not info["text"]:
            fast_match = re.search(r'<p>\s*<span class="icon-[^"]*"[^>]*></span>(.+?)</p>', html, re.DOTALL)
            if fast_match:
                fast_clean = re.sub(r'<[^>]+>', '', fast_match.group(1))
                info["text"] = fast_clean.strip()
        
        # 提取扩展包信息
        set_patterns = [
            r'<div class="card-pack[^"]*">\s*([^<#]+?)\s*#(\d+)',
            r'([\u4e00-\u9fa5·\w\s]{2,30})\s*#(\d+)\s*[。.]*\s*</div>',
        ]
        for pattern in set_patterns:
            set_match = re.search(pattern, html)
            if set_match:
                set_name = set_match.group(1).strip()
                set_name = re.sub(r'<[^>]+>', '', set_name)
                if set_name and 2 < len(set_name) < 50:
                    info["set"] = set_name
                    info["set_number"] = set_match.group(2).strip()
                    break
        
        return info
        
    except Exception as e:
        return info

def fetch_card(card_id):
    """抓取单个卡牌"""
    url = f"{BASE_URL}{card_id}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            if "card not found" in response.text.lower() or '没有找到卡牌' in response.text:
                return None
            return extract_card_info(response.text, card_id)
        return None
    except Exception as e:
        return None

def save_card_md(info):
    """保存卡牌信息到 markdown 文件"""
    if not info or not info.get("name"):
        return False
    
    faction = info.get("faction", "未知")
    faction_dir = OUTPUT_DIR / faction
    faction_dir.mkdir(parents=True, exist_ok=True)
    
    safe_name = sanitize_filename(info["name"])
    if not safe_name:
        safe_name = f"card_{info['id']}"
    filepath = faction_dir / f"{safe_name}.md"
    
    traits_text = '\n'.join(f'- {t}' for t in info['traits']) if info['traits'] else '- 无'
    
    md_content = f"""# {info['name']}

## 基本信息

- **ID**: {info['id']}
- **阵营**: {info['faction']}
- **类型**: {info['type']}
- **装备槽**: {info['slot'] if info['slot'] else '无'}
- **费用**: {info['cost'] if info['cost'] else '-'}

## 特质

{traits_text}

## 效果

{info['text'] if info['text'] else '无特殊效果'}

## 来源

- **扩展包**: {info['set'] if info['set'] else '未知'}
- **编号**: {info['set_number'] if info['set_number'] else '-'}
- **ArkhamDB**: https://zh.arkhamdb.com/card/{info['id']}

---
*自动抓取于 {time.strftime('%Y-%m-%d %H:%M:%S')}*
"""
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        return True
    except Exception as e:
        print(f"保存失败 {filepath}: {e}")
        return False

def main():
    print("获取卡牌列表...")
    
    # 获取 API 数据
    resp = requests.get(API_URL, headers=HEADERS, timeout=30)
    cards = resp.json()
    print(f"共 {len(cards)} 张卡牌")
    
    # 按阵营分组
    factions = {}
    for c in cards:
        faction = c.get('faction_name', 'Unknown')
        if faction not in factions:
            factions[faction] = []
        factions[faction].append(c)
    
    for f, cs in sorted(factions.items()):
        print(f"  {f}: {len(cs)} 张")
    
    # 批量抓取
    total = len(cards)
    success = 0
    fail = 0
    
    # 过滤掉 encounter 卡牌（可选）
    player_cards = [c for c in cards if c.get('type_code') not in ['enemy', 'location', 'story', 'scenario']]
    print(f"\n开始抓取 {len(player_cards)} 张玩家卡牌...")
    
    for i, card in enumerate(player_cards):
        card_id = card.get('code')
        if not card_id:
            continue
        
        info = fetch_card(card_id)
        
        if info and info.get("name"):
            # 优先使用 API 提供的名称
            if not info["name"]:
                info["name"] = card.get('name', card_id)
            if info["faction"] == "未知":
                info["faction"] = FACTION_MAP.get(card.get('faction_name', ''), '未知')
            if save_card_md(info):
                success += 1
        else:
            fail += 1
        
        # 进度
        if (i + 1) % 50 == 0:
            print(f"  进度: {i+1}/{len(player_cards)} (成功: {success})")
        
        # 限速
        if (i + 1) % 10 == 0:
            time.sleep(0.5)
    
    print(f"\n完成! 成功: {success}, 失败: {fail}")

if __name__ == "__main__":
    main()
