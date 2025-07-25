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

# ===== 分割関数（上1/8＋残り3分割） =====
def split_preview_top_small_bottom3(center_raw):
    w, h = center_raw.size
    parts = []

    # --- 上ブロックは1/8 ---
    top_h = h // 8
    part1 = center_raw.crop((0, 0, w, top_h))
    parts.append(part1)

    # --- 残り7/8を3分割 ---
    remaining_height = h - top_h
    block_h = remaining_height // 3

    for i in range(3):
        y1 = top_h + i * block_h
        y2 = top_h + (i+1) * block_h
        part = center_raw.crop((0, y1, w, y2))
        parts.append(part)

    return parts  # 合計4ブロック

# ===== Discord BOTイベント =====
@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！（上1/8＋下3分割プレビュー版）")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、中央OCR領域を上1/8＋下3分割して確認します…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # === 中央OCR領域 ===
            center_raw = crop_center_area(img)

            # 分割プレビュー（上1/8＋下3分割）
            parts = split_preview_top_small_bottom3(center_raw)
            for idx, p_img in enumerate(parts):
                buf = BytesIO()
                p_img.save(buf, format="PNG")
                buf.seek(0)
                await message.channel.send(
                    f"📸 中央分割プレビュー {idx+1}/4",
                    file=discord.File(buf, f"center_part_{idx+1}.png")
                )

client.run(TOKEN)