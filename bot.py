import discord
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import re
from datetime import datetime, timedelta
import os

TOKEN = os.getenv("DISCORD_TOKEN")

# OCR設定（精度重視）
OCR_CONFIG = "--oem 1 --psm 6"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def preprocess_image(img: Image.Image) -> Image.Image:
    """OCR前に画像補正（グレースケール＋コントラスト強調＋二値化）"""
    img = img.convert("L")  # グレースケール
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)  # コントラストUP
    img = img.filter(ImageFilter.SHARPEN)  # シャープ化
    img = img.point(lambda x: 0 if x < 128 else 255, '1')  # 二値化
    return img

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
        await message.channel.send("📥 画像を受け取りました、OCR補正中です…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # OCR前補正
            img_processed = preprocess_image(img)

            # 日本語OCR（駐騎場番号・サーバー番号用）
            text_jpn = pytesseract.image_to_string(img_processed, lang="jpn", config=OCR_CONFIG)
            # 英数字OCR（時間抽出用）
            text_eng = pytesseract.image_to_string(img_processed, lang="eng", config=OCR_CONFIG)

            # デバッグ結果
            await message.channel.send(f"📄 日本語OCR結果:\n```\n{text_jpn}\n```")
            await message.channel.send(f"📄 英数字OCR結果:\n```\n{text_eng}\n```")

            # === サーバー番号抽出 ===
            server_matches = re.findall(r'\[s\d{3,4}\]', text_jpn, re.IGNORECASE)
            if server_matches:
                # ✅ 最初に出たサーバー番号を採用（例: [s245] → 245）
                first_server = server_matches[0]
                server_id = re.search(r'\d{3,4}', first_server).group()[-3:]
            else:
                server_id = "???"

            # === 駐騎場番号抽出（重複削除） ===
            station_numbers = re.findall(r'駐[騎肝椅馬]\s*場\s*(\d+)', text_jpn)
            station_numbers = list(dict.fromkeys(station_numbers))  # 重複削除

            # === 免戦時間・基準時間抽出 ===
            time_matches = re.findall(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text_eng + text_jpn)

            # 時間が無ければ駐騎場だけ返す
            if not time_matches:
                await message.channel.send(
                    f"サーバー番号: {server_id}\n"
                    f"駐騎場番号: {', '.join(station_numbers) if station_numbers else 'なし'}\n"
                    f"⚠️ 基準時間が見つかりません"
                )
                continue

            # 時間が1つだけなら基準時間のみ通知
            if len(time_matches) == 1:
                await message.channel.send(
                    f"サーバー番号: {server_id}\n"
                    f"駐騎場番号: {', '.join(station_numbers) if station_numbers else 'なし'}\n"
                    f"⏰ 基準時間のみ検出: {time_matches[0]}"
                )
                continue

            # 最初の時間は基準時間
            base_time_str = time_matches[0]
            base_time = datetime.strptime(base_time_str, "%H:%M:%S")
            immune_times = time_matches[1:]  # 残りは免戦時間

            # 駐騎場番号が1つしかない場合 → すべて同じ番号で出す
            if len(station_numbers) == 1 and len(immune_times) > 1:
                station_numbers = [station_numbers[0]] * len(immune_times)

            # 駐騎場番号が足りない場合 → 順番割当で補う
            while len(station_numbers) < len(immune_times):
                station_numbers.append(str(len(station_numbers) + 1))

            # 計算結果
            results = []
            for idx, t in enumerate(immune_times):
                station_name = f"越域駐騎場{station_numbers[idx]}"
                h, m, s = map(int, t.split(":"))
                delta = timedelta(hours=h, minutes=m, seconds=s)
                new_time = (base_time + delta).time()
                results.append(f"{station_name}({server_id}) {new_time}")

            if results:
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send(
                    f"サーバー番号: {server_id}\n"
                    f"駐騎場番号: {', '.join(station_numbers) if station_numbers else 'なし'}\n"
                    f"⏰ 基準時間: {base_time_str}（免戦時間なし）"
                )

client.run(TOKEN)