"""
🛒📸 A8.net アフィリエイト広告 → Instagram 自動投稿スクリプト
GitHub Actions で定期実行されます。

A8.netには「すべての広告を自動取得できる」公開APIが存在しないため、
事前に a8_products.json に登録しておいた提携プログラム（商品・サービス）
の中から1件を順番（またはランダム）に選び、画像＋キャプションを生成して
Instagramに投稿します。

⚠️ 重要：2023年10月よりステマ規制（景品表示法）が施行されているため、
   キャプションには必ず「#PR」「#広告」等を表示します。
   また、A8.netおよび各プログラムの利用規約でSNS投稿が許可されているか
   事前に必ずご確認ください。
"""

import os
import re
import sys
import json
import random
from pathlib import Path

import ig_utils
from ig_utils import (
    IMGBB_API_KEY,
    check_credentials, upload_to_imgbb, download_image_as_pil,
    post_to_instagram,
)
from PIL import Image, ImageDraw, ImageFont


if not check_credentials():
    sys.exit(1)


# ================================================================
# ⚙️  設定
# ================================================================

# 商品リストファイル（A8.netの提携プログラムを登録しておく）
PRODUCTS_FILE = os.environ.get('A8_PRODUCTS_FILE', 'a8_products.json')

# 投稿状況の記録ファイル（順番投稿の場合に「次はどれを投稿するか」を保存）
STATE_FILE = os.environ.get('A8_STATE_FILE', 'a8_state.json')

# 投稿モード
#   sequential（デフォルト）→ 登録順に1件ずつ、最後まで行ったら最初に戻る
#   random                  → 毎回ランダムに1件選ぶ
A8_POST_MODE = os.environ.get('A8_POST_MODE', 'sequential').lower()

# ステマ規制対応：必ずキャプションに含める表示
AD_DISCLOSURE = '#PR #広告'

W, H = 1080, 1080
FONT_DIR = '/usr/share/fonts/opentype/noto'
FONT_BLACK   = f'{FONT_DIR}/NotoSansCJK-Black.ttc'
FONT_BOLD    = f'{FONT_DIR}/NotoSansCJK-Bold.ttc'
FONT_REGULAR = f'{FONT_DIR}/NotoSansCJK-Regular.ttc'


# ================================================================
# 🔧 画像生成（広告バナーが無い場合のフォールバックカード）
# ================================================================

_EMOJI_PATTERN = re.compile(
    '['
    '\U0001F000-\U0001FFFF'
    '\U00002600-\U000027BF'
    '\U00002190-\U000021FF'
    '\U00002B00-\U00002BFF'
    '\U0000FE00-\U0000FE0F'
    ']+', flags=re.UNICODE)


def for_image(text):
    """フォントに存在しない絵文字等を画像描画用に取り除く。"""
    return _EMOJI_PATTERN.sub('', text or '').strip()


def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def wrap_text(draw, text, font, max_width, max_lines=None):
    lines, line = [], ''
    for ch in text:
        test = line + ch
        if text_width(draw, test, font) > max_width and line:
            lines.append(line)
            line = ch
        else:
            line = test
    if line:
        lines.append(line)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while text_width(draw, last + '…', font) > max_width and len(last) > 1:
            last = last[:-1]
        lines[-1] = last + '…'
    return lines


def draw_centered_text(draw, text, font, center_x, y, fill):
    w = text_width(draw, text, font)
    draw.text((center_x - w / 2, y), text, font=font, fill=fill)


def generate_ad_card(product):
    """商品画像が用意できない場合に表示する、テキストベースの広告カードを生成する。"""
    img = Image.new('RGB', (W, H), '#1f2937')
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 14], fill='#f59e0b')
    draw.rectangle([0, H - 14, W, H], fill='#f59e0b')

    badge_font = get_font(FONT_BOLD, 32)
    draw.rectangle([60, 60, 250, 116], fill='#f59e0b')
    draw_centered_text(draw, 'PR ／ 広告', badge_font, 155, 70, '#1f2937')

    title_font = get_font(FONT_BLACK, 58)
    copy_font  = get_font(FONT_REGULAR, 36)

    title_lines = wrap_text(draw, for_image(product.get('title', '')), title_font, W - 120, max_lines=4)
    y = 200
    for ln in title_lines:
        draw.text((60, y), ln, font=title_font, fill='#ffffff')
        y += 76

    y += 30
    draw.rectangle([60, y, W - 60, y + 4], fill='#f59e0b')
    y += 50

    copy_lines = wrap_text(draw, for_image(product.get('copy', '')), copy_font, W - 120, max_lines=8)
    for ln in copy_lines:
        draw.text((60, y), ln, font=copy_font, fill='#cbd5e1')
        y += 50

    footer_font = get_font(FONT_REGULAR, 28)
    draw_centered_text(draw, for_image('詳細はプロフィールのリンクから'), footer_font, W / 2, H - 70, '#94a3b8')

    return img


# ================================================================
# 🖼️  画像URLの解決
# ================================================================

def is_valid_image_url(url):
    if not url or not url.startswith('http'):
        return False
    return any(ext in url.lower() for ext in ('.jpg', '.jpeg', '.png', '.gif', 'image/jpeg', 'image/png'))


def get_image_url(product):
    image_url = (product.get('image_url') or '').strip()

    if image_url:
        pil = download_image_as_pil(image_url, timeout=30)
        if pil:
            if IMGBB_API_KEY:
                url = upload_to_imgbb(pil)
                if url:
                    print('  ✅ 商品画像をimgbbに再アップロードしました。')
                    return url
            elif is_valid_image_url(image_url):
                print('  🖼️  指定の画像URLをそのまま使用します。')
                return image_url
        elif is_valid_image_url(image_url):
            # ダウンロードできなかったがURL形式は静的画像っぽいので、そのまま試す
            print('  ⚠️  画像のダウンロードに失敗。URLをそのまま使用します。')
            return image_url

    # 画像が無い／取得できない場合はテキストベースの広告カードを生成
    print('  🎨 商品画像が無いため、広告カードを自動生成します。')
    card = generate_ad_card(product)
    if not IMGBB_API_KEY:
        print('  ❌ IMGBB_API_KEY が未設定のため、生成したカードをアップロードできません。')
        return None
    url = upload_to_imgbb(card)
    if url:
        print('  ✅ 広告カードをimgbbにアップロードしました。')
    return url


# ================================================================
# ✏️  キャプション生成
# ================================================================

def build_caption(product):
    title    = product.get('title', '').strip()
    copy     = product.get('copy', '').strip()
    url      = product.get('affiliate_url', '').strip()
    hashtags = product.get('hashtags', '').strip()

    lines = [f'🛍️ {title}']
    if copy:
        lines.append('')
        lines.append(copy)

    lines.append('')
    if url:
        lines.append(f'🔗 {url}')
        lines.append('（リンクが開けない場合はプロフィールのリンクからもご覧いただけます）')
        lines.append('')

    tag_line = hashtags
    if '#PR' not in hashtags and '広告' not in hashtags:
        tag_line = (AD_DISCLOSURE + ' ' + hashtags).strip()
    lines.append(tag_line)

    return '\n'.join(lines)


# ================================================================
# 📂 商品リスト・投稿状態の読み込み／保存
# ================================================================

def load_products():
    path = Path(PRODUCTS_FILE)
    if not path.exists():
        print(f'❌ 商品リストファイルが見つかりません: {PRODUCTS_FILE}')
        return []
    try:
        with open(path, encoding='utf-8') as f:
            products = json.load(f)
    except Exception as e:
        print(f'❌ 商品リストの読み込みに失敗しました: {e}')
        return []
    if not isinstance(products, list):
        print('❌ 商品リストはJSON配列形式で記述してください。')
        return []
    return products


def load_state():
    path = Path(STATE_FILE)
    if path.exists():
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'last_index': -1}


def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def select_product(products, state):
    if A8_POST_MODE == 'random':
        idx = random.randrange(len(products))
    else:
        idx = (state.get('last_index', -1) + 1) % len(products)
    return idx, products[idx]


# ================================================================
# 🚀 メイン実行
# ================================================================

def main():
    products = load_products()
    if not products:
        print('❌ 投稿可能な商品がありません。a8_products.json を確認してください。')
        sys.exit(1)

    state = load_state()
    idx, product = select_product(products, state)

    print(f'🛍️  選択された商品 [{idx + 1}/{len(products)}]: {product.get("title", "")}')

    image_url = get_image_url(product)
    if not image_url:
        print('❌ 画像URLを準備できませんでした。投稿を中止します。')
        sys.exit(1)

    caption = build_caption(product)

    print('\n📤 Instagramへ投稿中...')
    post_id = post_to_instagram(image_url, caption)

    if post_id and A8_POST_MODE != 'random':
        state['last_index'] = idx
        save_state(state)
        print(f'💾 投稿状態を保存しました（次回は {(idx + 1) % len(products) + 1}/{len(products)} 番目）')

    if not post_id:
        sys.exit(1)


if __name__ == '__main__':
    main()
