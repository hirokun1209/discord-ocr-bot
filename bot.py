import discord
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import re
from datetime import datetime, timedelta
import os

TOKEN = os.getenv("DISCORD_TOKEN")

OCR_CONFIG = "--oem 3 --psm 7"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def preprocess_image(img: Image.Image) -> Image.Image:
    """OCR前に画像拡大＋補正"""
    img = img.resize((img.width * 2, img.height * 2))  # 2倍拡大で小さい文字も読みやすく
    img = img.convert("L")  # グレースケール化
    img = ImageEnhance.Contrast(img).enhance(2.0)  # コントラスト強調
    img = img.filter(ImageFilter.SHARPEN)  # シャープ化
    return img

def crop_top_right(img: Image.Image) -> Image.Image:
    """右上(基準時間) → ピンポイントで高さ7〜13%"""
    w, h = img.size
    return img.crop((w * 0.75, h * 0.07, w * 0.98, h * 0.13))

def crop_center_area(img: Image.Image) -> Image.Image:
    """中央OCR → 下を狭めて高さ35〜70%"""
    w, h = img.size
    return img.crop((w * 0.1, h * 0.35, w * 0.9, h * 0.70))

def clean_ocr_text(text: str) -> str:
    """OCR結果の不要文字補正"""
    text = text.replace("を奪取しました", "")
    text = text.replace("奪取撃破数", "")
    text = text.replace("警備撃破数", "")
    text = text.replace("駐脱場", "駐騎場")
    text = text.replace("駐聴場", "駐騎場")
    return text

def extract_base_time(text: str) -> str:
    """基準時間(HH:MM:SS)を抽出"""
    m = re.search(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text)
    return m.group(1) if m else None

def extract_server_id(text: str) -> str:
    """サーバー番号(最後の1〜999を採用)"""
    server_matches = re.findall(r'\[s\d{2,4}\]', text, re.IGNORECASE)
    valid_servers = []
    for s in server_matches:
        num = int(re.search(r'\d{2,4}', s).group())
        if 1 <= num <= 999:
            valid_servers.append(num)
    return str(valid_servers[-1]) if valid_servers else "???"

def extract_station_numbers(text: str):
    """駐騎場番号（1〜12のみ有効）"""
    raw_stations = re.findall(r'駐騎場\s*(\d+)', text)
    return [n for n in dict.fromkeys(raw_stations) if 1 <= int(n) <= 12]

def extract_times(text: str):
    """免戦時間（HH:MM:SS / HH:MM / MM:SS対応、6時間以内だけ有効）"""
    raw_times = re.findall(r'([0-5]?\d:[0-5]\d(?::[0-5]\d)?)', text)
    immune_times = []
    for t in raw_times:
        parts = t.split(':')
        if len(parts) == 3:
            h, m, s = map(int, parts)
        elif len(parts) == 2:
            first, second = map(int, parts)
            if first < 6:
                # HH:MM → 秒補完
                h, m, s = first, second, 0
            else:
                # MM:SS → 時間0補完
                h, m, s = 0, first, second
            t = f"{h:02}:{m:02}:{s:02}"
        else:
            continue
        if 0 <= h <= 6:
            immune_times.append(t)
    return immune_times

@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、OCRデバッグ中…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # === 基準時間OCR（右上ピンポイント） ===
            base_img = preprocess_image(crop_top_right(img))
            base_img.save("/tmp/debug_base.png")
            await message.channel.send(file=discord.File("/tmp/debug_base.png", "base_debug.png"))
            base_text = pytesseract.image_to_string(base_img, lang="eng", config="--psm 7")
            base_time = extract_base_time(base_text)

            # === 中央OCR（駐騎場情報 下を狭めた版） ===
            center_img = preprocess_image(crop_center_area(img))
            center_img.save("/tmp/debug_center.png")
            await message.channel.send(file=discord.File("/tmp/debug_center.png", "center_debug.png"))
            center_text = clean_ocr_text(
                pytesseract.image_to_string(center_img, lang="jpn", config=OCR_CONFIG)
            )

            await message.channel.send(f"⏫ 基準時間OCR:\n```\n{base_text}\n```")
            await message.channel.send(f"📄 中央OCR結果:\n```\n{center_text}\n```")

            # サーバー番号 / 駐騎場番号 / 免戦時間抽出
            server_id = extract_server_id(center_text)
            station_numbers = extract_station_numbers(center_text)
            immune_times = extract_times(center_text)

            if not base_time:
                await message.channel.send("⚠️ 基準時間が右上から読み取れませんでした")
                return

            if len(station_numbers) != len(immune_times):
                await message.channel.send(
                    f"⚠️ データ数不一致\n"
                    f"基準時間: {base_time}\n"
                    f"サーバー番号: {server_id}\n"
                    f"駐騎場番号({len(station_numbers)}件): {', '.join(station_numbers) if station_numbers else 'なし'}\n"
                    f"免戦時間({len(immune_times)}件): {', '.join(immune_times) if immune_times else 'なし'}"
                )
                return

            # === 基準時間 + 免戦時間 計算 ===
            base_dt = datetime.strptime(base_time, "%H:%M:%S")
            results = []
            for idx, t in enumerate(immune_times):
                station_name = f"越域駐騎場{station_numbers[idx]}"
                h, m, s = map(int, t.split(":"))
                end_dt = (base_dt + timedelta(hours=h, minutes=m, seconds=s)).time()
                results.append(f"{station_name}({server_id}) {end_dt.strftime('%H:%M:%S')}")

            if results:
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send(
                    f"基準時間: {base_time}\nサーバー番号: {server_id}\n⚠️ 有効な駐騎場番号 or 免戦時間なし"
                )

client.run(TOKEN)