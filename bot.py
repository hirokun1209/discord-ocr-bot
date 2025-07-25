import discord, pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import re, os
from datetime import datetime, timedelta

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===== 前処理 =====
def preprocess_image(img: Image.Image) -> Image.Image:
    # 4倍拡大
    img = img.resize((img.width * 4, img.height * 4))
    # グレースケール
    img = img.convert("L")
    # ノイズ軽減
    img = img.filter(ImageFilter.MedianFilter(size=3))
    # コントラスト強化
    img = ImageEnhance.Contrast(img).enhance(3.0)
    # 白黒2値化
    img = img.point(lambda p: 255 if p > 150 else 0)
    # シャープ化
    img = img.filter(ImageFilter.SHARPEN)
    return img

# ===== 位置切り出し =====
def crop_top_right(img):
    w,h = img.size
    return img.crop((w*0.70, h*0.05, w*0.99, h*0.15))

def crop_center_area(img):
    w,h = img.size
    return img.crop((w*0.1, h*0.35, w*0.5, h*0.70))

# ===== OCR & 抽出 =====
def ocr_text(img: Image.Image, psm=11) -> str:
    config = f"--oem 3 --psm {psm}"
    return pytesseract.image_to_string(img, lang="jpn+eng", config=config)

def clean_text(text):
    return text.replace("駐聴場","駐騎場").replace("駐脱場","駐騎場")

def extract_base_time(text):
    m = re.search(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text)
    return m.group(1) if m else None

def extract_server_id(text):
    m = re.search(r'\[s?(\d{2,4})\]', text, re.IGNORECASE)
    return m.group(1) if m else None

def extract_station_numbers(text):
    return re.findall(r'駐騎場\s*(\d+)', text)

def extract_times(text):
    return re.findall(r'([0-5]?\d:[0-5]\d(?::[0-5]\d)?)', text)

@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！（Tesseract軽量版）")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、解析中…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # === 基準時間 ===
            base_img = preprocess_image(crop_top_right(img))
            base_text = ocr_text(base_img, psm=7)  # 1行想定
            base_time = extract_base_time(base_text)

            # === 中央OCR ===
            center_img = preprocess_image(crop_center_area(img))
            center_text_raw = ocr_text(center_img, psm=11) # スパーステキストモード
            center_text = clean_text(center_text_raw)

            # デバッグ出力
            await message.channel.send(f"⏫ 基準時間OCR:\n```\n{base_text}\n```")
            await message.channel.send(f"📄 中央OCR結果:\n```\n{center_text_raw}\n```")

            server_id = extract_server_id(center_text)
            station_numbers = extract_station_numbers(center_text)
            immune_times = extract_times(center_text)

            if not base_time:
                await message.channel.send("⚠️ 基準時間が読めませんでした")
                return

            if not server_id:
                await message.channel.send("⚠️ サーバー番号が読めませんでした")
                return

            if len(station_numbers) != len(immune_times):
                await message.channel.send(
                    f"⚠️ データ数不一致\n"
                    f"基準時間: {base_time}\n"
                    f"サーバー: {server_id}\n"
                    f"駐騎場: {station_numbers}\n"
                    f"免戦: {immune_times}"
                )
                return

            base_dt = datetime.strptime(base_time,"%H:%M:%S")
            results=[]
            for i,t in enumerate(immune_times):
                hms = list(map(int, t.split(":")))
                while len(hms)<3: hms.append(0)
                end_dt = (base_dt + timedelta(hours=hms[0], minutes=hms[1], seconds=hms[2])).time()
                results.append(f"越域駐騎場{station_numbers[i]}({server_id}) {end_dt.strftime('%H:%M:%S')}")

            await message.channel.send("\n".join(results) if results else "⚠️ 読み取り結果なし")

client.run(TOKEN)