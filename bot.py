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

            # === サーバー番号抽出（1〜999だけ有効） ===
            server_matches = re.findall(r'\[s\d{2,4}\]', text_jpn, re.IGNORECASE)
            valid_servers = []
            for s in server_matches:
                num = int(re.search(r'\d{2,4}', s).group())
                # サーバー番号は1〜999まで有効（4桁は除外）
                if 1 <= num <= 999:
                    valid_servers.append(num)

            if valid_servers:
                server_id = str(valid_servers[-1])  # ✅ 最後の有効な3桁番号
            else:
                server_id = "???"

            # === 駐騎場番号抽出（1〜12のみ許可 & 重複削除） ===
            raw_stations = re.findall(r'駐[騎肝椅馬]\s*場\s*(\d+)', text_jpn)
            station_numbers = [
                n for n in dict.fromkeys(raw_stations)
                if n.isdigit() and 1 <= int(n) <= 12
            ]

            # === 時間抽出 ===
            raw_times = re.findall(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text_eng + text_jpn)
            # 免戦時間は最大06:00:00まで許可
            immune_times = [
                t for t in raw_times
                if t and 0 <= int(t.split(':')[0]) <= 6
            ]

            # 免戦時間が駐騎場番号と一致しなければエラー
            if len(station_numbers) != len(immune_times):
                await message.channel.send(
                    f"⚠️ データ数不一致\n"
                    f"サーバー番号: {server_id}\n"
                    f"駐騎場番号({len(station_numbers)}件): {', '.join(station_numbers) if station_numbers else 'なし'}\n"
                    f"免戦時間({len(immune_times)}件): {', '.join(immune_times) if immune_times else 'なし'}"
                )
                return

            # 基準時間が必要ならユーザー指定が前提なのでここでは免戦時間のみ対応
            results = []
            for idx, t in enumerate(immune_times):
                station_name = f"越域駐騎場{station_numbers[idx]}"
                h, m, s = map(int, t.split(":"))
                # 基準時間が無いので免戦時間そのまま表示（ユーザー指定モードでもOK）
                results.append(f"{station_name}({server_id}) +{h:02}:{m:02}:{s:02}")

            if results:
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send(
                    f"サーバー番号: {server_id}\n駐騎場番号なし or 免戦時間なし"
                )

client.run(TOKEN)