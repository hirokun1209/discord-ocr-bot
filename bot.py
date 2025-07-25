import discord
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import re
from datetime import datetime, timedelta
import os

TOKEN = os.getenv("DISCORD_TOKEN")

OCR_CONFIG = "--oem 1 --psm 6"

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

            img_processed = preprocess_image(img)

            text_jpn = pytesseract.image_to_string(img_processed, lang="jpn", config=OCR_CONFIG)
            text_eng = pytesseract.image_to_string(img_processed, lang="eng", config=OCR_CONFIG)

            await message.channel.send(f"📄 日本語OCR結果:\n```\n{text_jpn}\n```")
            await message.channel.send(f"📄 英数字OCR結果:\n```\n{text_eng}\n```")

            # === サーバー番号（最後の1～999を採用） ===
            server_matches = re.findall(r'\[s\d{2,4}\]', text_jpn, re.IGNORECASE)
            valid_servers = []
            for s in server_matches:
                num = int(re.search(r'\d{2,4}', s).group())
                if 1 <= num <= 999:
                    valid_servers.append(num)
            server_id = str(valid_servers[-1]) if valid_servers else "???"

            # === 駐騎場番号（1～12のみ有効） ===
            raw_stations = re.findall(r'駐[騎肝椅馬]\s*場\s*(\d+)', text_jpn)
            station_numbers = [
                n for n in dict.fromkeys(raw_stations)
                if n.isdigit() and 1 <= int(n) <= 12
            ]

            # === 免戦時間抽出 (HH:MM:SS / HH:MM / MM:SS 全対応) ===
            raw_times = re.findall(r'([0-5]?\d:[0-5]\d(?::[0-5]\d)?)', text_eng + text_jpn)
            immune_times = []
            for t in raw_times:
                parts = t.split(':')

                if len(parts) == 3:
                    # HH:MM:SS → そのまま
                    h, m, s = map(int, parts)
                elif len(parts) == 2:
                    first, second = map(int, parts)
                    if first < 6:  
                        # HH:MM (時間<6なら有効)
                        h, m, s = first, second, 0
                    else:
                        # MM:SS と判断 → 時間は0
                        h, m, s = 0, first, second
                    t = f"{h:02}:{m:02}:{s:02}"
                else:
                    continue  # 不正フォーマットは除外

                # 免戦時間は0～6時間だけ有効
                if 0 <= h <= 6:
                    immune_times.append(t)

            # === データ整合性チェック ===
            if len(station_numbers) != len(immune_times):
                await message.channel.send(
                    f"⚠️ データ数不一致\n"
                    f"サーバー番号: {server_id}\n"
                    f"駐騎場番号({len(station_numbers)}件): {', '.join(station_numbers) if station_numbers else 'なし'}\n"
                    f"免戦時間({len(immune_times)}件): {', '.join(immune_times) if immune_times else 'なし'}"
                )
                return

            # === 1対1対応で計算結果作成 ===
            results = []
            for idx, t in enumerate(immune_times):
                station_name = f"越域駐騎場{station_numbers[idx]}"
                h, m, s = map(int, t.split(":"))
                results.append(f"{station_name}({server_id}) +{h:02}:{m:02}:{s:02}")

            if results:
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send(
                    f"サーバー番号: {server_id}\n駐騎場番号なし or 免戦時間なし"
                )

client.run(TOKEN)