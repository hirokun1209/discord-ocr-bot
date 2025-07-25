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

# ===== 前処理 =====
def preprocess_image(img: Image.Image) -> Image.Image:
    # OCR精度向上のため拡大+補正
    img = img.resize((img.width * 4, img.height * 4))
    img = img.convert("L")  # グレースケール
    img = img.filter(ImageFilter.MedianFilter(size=3))  # ノイズ除去
    img = ImageEnhance.Contrast(img).enhance(3.0)       # コントラスト強化
    img = img.point(lambda p: 255 if p > 150 else 0)    # 2値化
    img = img.filter(ImageFilter.SHARPEN)               # シャープ化
    return img

# ===== 画面位置切り出し =====
def crop_top_right(img):
    w,h = img.size
    return img.crop((w*0.70, h*0.05, w*0.99, h*0.15))

def crop_center_area(img):
    w,h = img.size
    # ←ここを左右広げる（前:0.1~0.5 → 今回:0.05~0.55）
    return img.crop((w*0.05, h*0.35, w*0.55, h*0.70))

# ===== OCR呼び出し =====
def ocr_text(img: Image.Image, psm=4) -> str:
    # psm4 → ブロック解析優先（ゲームUI向け）
    config = f"--oem 3 --psm {psm}"
    return pytesseract.image_to_string(img, lang="jpn+eng", config=config)

# ===== 誤検出補正ロジック =====
def clean_text(text: str) -> str:
    replacements = {
        "駒場": "駐騎場",
        "駐駒場": "駐騎場",
        "駐聴場": "駐騎場",
        "駐脱場": "駐騎場",
        "駐場": "駐騎場",      # 騎が抜けたパターン補正
        "駐域場": "駐騎場",    # OCR誤認補正
        "束駐": "越域駐",
        "Ai束": "越域駐",
        "越域駐駒場": "越域駐騎場",
        "駐騎場O": "駐騎場0",  # O→0補正
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

# ===== データ抽出 =====
def extract_base_time(text):
    m = re.search(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text)
    return m.group(1) if m else None

def extract_server_id(text):
    m = re.search(r'\[s?(\d{2,4})\]', text, re.IGNORECASE)
    return m.group(1) if m else None

def extract_station_numbers(text: str):
    nums = re.findall(r'駐.*?場\s*(\d+)', text)
    valid = []
    for n in nums:
        if n.isdigit():
            num = int(n)
            if 1 <= num <= 12:  # 1～12だけ有効
                valid.append(str(num))
    return valid

def extract_times(text: str):
    return re.findall(r'([0-5]?\d:[0-5]\d(?::[0-5]\d)?)', text)

# ===== Discord BOTイベント =====
@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！（補正＆領域拡大＆psm4版）")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、解析中…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # === 基準時間 ===
            base_img = preprocess_image(crop_top_right(img))
            base_text = ocr_text(base_img, psm=7)  # 1行用
            base_time = extract_base_time(base_text)

            # === 中央OCR ===
            center_img = preprocess_image(crop_center_area(img))
            center_text_raw = ocr_text(center_img, psm=4)  # ブロック解析
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