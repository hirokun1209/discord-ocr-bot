import discord
from PIL import Image
from io import BytesIO
import os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===== 中央領域切り出し =====
def crop_center_area(img):
    w,h = img.size
    # 中央領域は35%〜65%のまま固定
    return img.crop((w*0.05, h*0.35, w*0.55, h*0.65))

# ===== 分割関数（1枚目小さめ(1/6)、残りは大きめ(1/4)で統一） =====
def split_preview_mixed_correct(center_raw):
    w, h = center_raw.size
    parts = []

    # --- Part1 = 小さめ(1/6) ---
    part1_h = h // 6
    part1 = center_raw.crop((0, 0, w, part1_h))
    parts.append(part1)

    # --- Part2〜4 = 大きめ(1/4) ---
    part_big_h = h // 4

    y_start = part1_h
    for _ in range(3):
        y_end = y_start + part_big_h
        part = center_raw.crop((0, y_start, w, min(y_end, h)))
        parts.append(part)
        y_start = y_end

    return parts  # 合計4枚

# ===== Discord BOTイベント =====
@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！（1枚目小さめ・2枚目以降大きめプレビュー版）")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、中央OCR領域を分割します…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # === 中央OCR領域 ===
            center_raw = crop_center_area(img)

            # 分割プレビュー（1枚目小さめ＋残り大きめ統一）
            parts = split_preview_mixed_correct(center_raw)
            for idx, p_img in enumerate(parts):
                buf = BytesIO()
                p_img.save(buf, format="PNG")
                buf.seek(0)
                await message.channel.send(
                    f"📸 中央分割プレビュー {idx+1}/4",
                    file=discord.File(buf, f"center_part_{idx+1}.png")
                )

client.run(TOKEN)