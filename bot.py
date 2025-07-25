import discord
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import re
import os

TOKEN = os.getenv("DISCORD_TOKEN")

OCR_CONFIG = "--oem 3 --psm 6"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def preprocess_image(img: Image.Image) -> Image.Image:
    """OCR前に画像補正（グレースケール＋コントラスト強調＋二値化）"""
    img = img.convert("L")
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda x: 0 if x < 128 else 255, '1')
    return img

def crop_center_area(img: Image.Image) -> Image.Image:
    """画面中央付近（高さ40～70%）だけ切り出す"""
    w, h = img.size
    return img.crop((w * 0.1, h * 0.4, w * 0.9, h * 0.7))

def clean_ocr_text(text: str) -> str:
    """不要な文章を削除"""
    text = text.replace("を奪取しました", "")
    text = text.replace("奪取撃破数", "")
    text = text.replace("警備撃破数", "")
    text = text.replace("駐脱場", "駐騎場")
    text = text.replace("駐聴場", "駐騎場")
    return text

def extract_server_id(text: str) -> str:
    """サーバー番号は最後の1～999を採用"""
    server_matches = re.findall(r'\[s\d{2,4}\]', text, re.IGNORECASE)
    valid_servers = []
    for s in server_matches:
        num = int(re.search(r'\d{2,4}', s).group())
        if 1 <= num <= 999:
            valid_servers.append(num)
    return str(valid_servers[-1]) if valid_servers else "???"

def extract_station_numbers(text: str):
    """駐騎場番号（1～12のみ有効）"""
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
        await message.channel.send("📥 画像を受け取りました、中央OCR処理中…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # 画面中央だけ切り出し
            center_img = crop_center_area(preprocess_image(img))

            # OCR実行
            text = pytesseract.image_to_string(center_img, lang="jpn", config=OCR_CONFIG)
            text = clean_ocr_text(text)
            await message.channel.send(f"📄 中央OCR結果:\n```\n{text}\n```")

            # サーバー番号 / 駐騎場番号 / 免戦時間抽出
            server_id = extract_server_id(text)
            station_numbers = extract_station_numbers(text)
            immune_times = extract_times(text)

            # データ数が一致しない場合は警告
            if len(station_numbers) != len(immune_times):
                await message.channel.send(
                    f"⚠️ データ数不一致\n"
                    f"サーバー番号: {server_id}\n"
                    f"駐騎場番号({len(station_numbers)}件): {', '.join(station_numbers) if station_numbers else 'なし'}\n"
                    f"免戦時間({len(immune_times)}件): {', '.join(immune_times) if immune_times else 'なし'}"
                )
                return

            # 正常なら1対1で結果生成
            results = []
            for idx, t in enumerate(immune_times):
                station_name = f"越域駐騎場{station_numbers[idx]}"
                results.append(f"{station_name}({server_id}) +{t}")

            if results:
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send(f"サーバー番号: {server_id}\n⚠️ 有効な駐騎場番号 or 時間なし")

client.run(TOKEN)