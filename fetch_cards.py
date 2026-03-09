#!/usr/bin/env python3
"""
ArkhamDB 卡牌数据抓取脚本
抓取 https://zh.arkhamdb.com/card/{id} 的卡牌信息
按阵营/名字.md 格式存储
"""

import requests
import re
import os
import time
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

# 配置
BASE_URL = "https://zh.arkhamdb.com/card/"
OUTPUT_DIR = Path("/Users/bytedance/.openclaw/workspace/arkham/cards_infos")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 阵营映射
FACTION_MAP = {
    'guardian': '守护者',
    'seeker': '探求者',
    'rogue': '流浪者',
    'mystic': '神秘学家',
    'survivor': '求生者',
    'neutral': '中立'
}

def sanitize_filename(name):
    """清理文件名中的非法字符"""
    invalid_chars = '<>"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    name = name.strip('. ')
    # 如果名字以 . 开头，添加前缀
    if name.startswith('.'):
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
        
        # 提取费用
        cost_match = re.search(r'费用:\s*(\d+|X)[\.\s]*<', html)
        if cost_match:
            info["cost"] = cost_match.group(1).strip()
        
        # 提取类型 - 从 card-type class
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
        
        # 提取特质 - 从 card-traits class，并拆分为列表
        traits_match = re.search(r'<p class="card-traits">([^\u003c]+)</p>', html)
        if traits_match:
            traits_text = traits_match.group(1).strip()
            if '。' in traits_text:
                info["traits"] = [t.strip() for t in traits_text.split('。') if t.strip()]
            else:
                info["traits"] = [traits_text]
        
        # 提取卡牌效果文本
        # 查找使用(...)及其后续内容
        usage_match = re.search(r'使用\(([^)]+)\)[。\s]*', html)
        if usage_match:
            info["text"] = f"使用({usage_match.group(1)})"
            
            # 查找完整的效果段落（包含使用(...)和Action效果）
            full_effect = re.search(r'<p>使用\([^)]+\)[。\s]*</p>\s*<p>(.+?)</p>', html, re.DOTALL)
            if full_effect:
                action_html = full_effect.group(1)
                # 提取图标后面的文本
                action_text = re.sub(r'<span[^>]*>[^<]*</span>', '', action_html)
                action_text = re.sub(r'<[^>]+>', '', action_text)
                info["text"] += "\n" + action_text.strip()
            else:
                # 尝试在一个 <p> 里的情况
                single_p = re.search(r'<p>使用\([^)]+\)[。\s]*<span[^>]*>[^<]*</span>(.+?)</p>', html, re.DOTALL)
                if single_p:
                    action_text = re.sub(r'<[^>]+>', '', single_p.group(1))
                    info["text"] += "\n" + action_text.strip()
        
        # 如果没有使用(，尝试提取其他效果
        if not info["text"]:
            # 提取 Fast/Reaction 效果
            fast_match = re.search(r'<p>\s*<span class="icon-[^"]*"[^>]*></span>(.+?)</p>', html, re.DOTALL)
            if fast_match:
                fast_clean = re.sub(r'<[^>]+>', '', fast_match.group(1))
                info["text"] = fast_clean.strip()
        
        # 提取扩展包信息 - 从类似 "斯特拉·克拉克 #5" 的格式
        # 查找在特定位置的文本
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
        print(f"提取卡牌 {card_id} 信息时出错: {e}")
        import traceback
        traceback.print_exc()
        return info

def fetch_card(card_id):
    """抓取单个卡牌"""
    url = f"{BASE_URL}{card_id}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            # 检查是否是错误页面
            if "card not found" in response.text.lower() or '没有找到卡牌' in response.text:
                return None
            # 检查是否是搜索页面（表示卡牌不存在）
            if '<form' in response.text and '60505' not in response.text and str(card_id) not in response.text[:5000]:
                return None
            return extract_card_info(response.text, card_id)
        return None
    except Exception as e:
        print(f"抓取卡牌 {card_id} 失败: {e}")
        return None

def save_card_md(info):
    """保存卡牌信息到 markdown 文件"""
    if not info or not info.get("name"):
        return False
    
    # 确定阵营目录
    faction = info.get("faction", "未知")
    faction_dir = OUTPUT_DIR / faction
    faction_dir.mkdir(parents=True, exist_ok=True)
    
    # 文件名
    safe_name = sanitize_filename(info["name"])
    if not safe_name:
        safe_name = f"card_{info['id']}"
    filepath = faction_dir / f"{safe_name}.md"
    
    # 生成特质文本
    traits_text = '\n'.join(f'- {t}' for t in info['traits']) if info['traits'] else '- 无'
    
    # 生成 markdown 内容
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
        print(f"✓ 已保存: {faction}/{safe_name}.md")
        return True
    except Exception as e:
        print(f"✗ 保存失败 {filepath}: {e}")
        return False

def discover_card_range():
    """探测卡牌 ID 范围"""
    test_ids = [1, 10, 50, 100, 200, 500, 1000, 2000, 3000, 4000, 5000, 
                6000, 7000, 8000, 9000, 10000, 15000, 20000, 30000, 40000, 50000]
    valid_ranges = []
    
    for card_id in test_ids:
        info = fetch_card(card_id)
        if info and info.get("name"):
            print(f"ID {card_id}: {info['name']} ({info['faction']})")
            valid_ranges.append(card_id)
        time.sleep(0.3)
    
    return valid_ranges

def batch_fetch(start_id, end_id, max_workers=5):
    """批量抓取卡牌"""
    print(f"开始批量抓取: {start_id} - {end_id}")
    
    success_count = 0
    fail_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_card, cid): cid for cid in range(start_id, end_id + 1)}
        
        for future in as_completed(futures):
            card_id = futures[future]
            try:
                info = future.result()
                if info and info.get("name"):
                    if save_card_md(info):
                        success_count += 1
                    else:
                        fail_count += 1
                else:
                    fail_count += 1
                    if card_id % 100 == 0:  # 每100个显示一次
                        print(f"  ID {card_id}: 未找到")
                
                # 进度显示
                total_processed = success_count + fail_count
                if total_processed % 50 == 0:
                    print(f"  进度: {total_processed}/{end_id - start_id + 1} (成功: {success_count})")
                    
            except Exception as e:
                print(f"✗ ID {card_id}: {e}")
                fail_count += 1
    
    print(f"\n完成! 成功: {success_count}, 失败: {fail_count}")
    return success_count, fail_count

def main():
    import argparse
    parser = argparse.ArgumentParser(description='ArkhamDB 卡牌抓取工具')
    parser.add_argument('--discover', action='store_true', help='探测卡牌 ID 范围')
    parser.add_argument('--start', type=int, default=1, help='起始 ID')
    parser.add_argument('--end', type=int, default=1000, help='结束 ID')
    parser.add_argument('--workers', type=int, default=3, help='并发数')
    parser.add_argument('--id', type=int, help='抓取单个卡牌 ID')
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.discover:
        print("探测卡牌 ID 范围...")
        discover_card_range()
    elif args.id:
        print(f"抓取单个卡牌: {args.id}")
        info = fetch_card(args.id)
        if info:
            print(json.dumps(info, ensure_ascii=False, indent=2))
            save_card_md(info)
        else:
            print("未找到卡牌")
    else:
        batch_fetch(args.start, args.end, args.workers)

if __name__ == "__main__":
    main()
