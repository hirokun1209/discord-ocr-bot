import discord
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import re, os
from datetime import datetime, timedelta

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===== 基本前処理 =====
def preprocess_image(img: Image.Image) -> Image.Image:
    img = img.resize((img.width * 4, img.height * 4))
    img = img.convert("L")  # グレースケール
    img = img.filter(ImageFilter.MedianFilter(size=3))  # ノイズ除去
    img = ImageEnhance.Contrast(img).enhance(3.0)       # コントラスト強化
    img = img.point(lambda p: 255 if p > 150 else 0)    # 2値化
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)     # エッジ強調追加
    img = img.filter(ImageFilter.SHARPEN)               # シャープ化
    return img

# ===== 画面位置切り出し =====
def crop_top_right(img):
    w,h = img.size
    return img.crop((w*0.70, h*0.05, w*0.99, h*0.15))

def crop_center_area(img):
    w,h = img.size
    # 中央領域は狭めたまま（35%〜65%）
    return img.crop((w*0.05, h*0.35, w*0.55, h*0.65))

# ===== 中央OCR領域を分割プレビュー =====
def split_preview(center_raw, parts=6):
    w, h = center_raw.size
    h_part = h // parts
    images = []
    for i in range(parts):
        y1 = i * h_part
        y2 = (i+1) * h_part
        part_img = center_raw.crop((0, y1, w, y2))
        images.append(part_img)
    return images

# ===== OCR共通 =====
def ocr_text(img: Image.Image, psm=4) -> str:
    config = f"--oem 3 --psm {psm}"
    return pytesseract.image_to_string(img, lang="jpn+eng", config=config)

# ===== 時間専用OCR（数字限定モード） =====
def ocr_time_line(img: Image.Image) -> str:
    config = "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789:"
    return pytesseract.image_to_string(img, lang="eng", config=config)

# ===== 誤検出補正 =====
def clean_text(text: str) -> str:
    replacements = {
        "駒場": "駐騎場",
        "駐駒場": "駐騎場",
        "駐聴場": "駐騎場",
        "駐脱場": "駐騎場",
        "駐場": "駐騎場",
        "駐域場": "駐騎場",
        "束駐": "越域駐",
        "Ai束": "越域駐",
        "越域駐駒場": "越域駐騎場",
        "駐騎場O": "駐騎場0",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

# ===== 時間フォーマット補正 =====
def normalize_time_format(line: str):
    line = line.replace("O","0").replace("o","0").replace("B","8")
    m = re.search(r'(\d{6})', line)
    if m:
        raw = m.group(1)
        return f"{raw[0:2]}:{raw[2:4]}:{raw[4:6]}"
    m2 = re.search(r'([0-2]?\d:[0-5]\d:[0-5]\d)', line)
    if m2:
        return m2.group(1)
    return None

# ===== Discord BOTイベント =====
@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！（6分割プレビュー版）")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、中央OCR領域を6分割して確認します…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # === 中央OCR領域 ===
            center_raw = crop_center_area(img)

            # 6分割プレビュー
            parts = split_preview(center_raw, parts=6)
            for idx, p_img in enumerate(parts):
                buf = BytesIO()
                p_img.save(buf, format="PNG")
                buf.seek(0)
                await message.channel.send(f"📸 中央分割プレビュー {idx+1}/6", file=discord.File(buf, f"center_part_{idx+1}.png"))

            # デバッグ用にOCRも試す
            center_img = preprocess_image(center_raw)
            center_text_raw = ocr_text(center_img, psm=4)
            await message.channel.send(f"📄 中央OCR結果(全体):\n```\n{center_text_raw}\n```")

client.run(TOKEN)