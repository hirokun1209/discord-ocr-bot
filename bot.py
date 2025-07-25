import os
import discord
from PIL import Image

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === サーバー番号は完璧なので現状維持 ===
server_box = (420, 970, 870, 1040)

# === 駐騎場は右に20px、下に5px調整 ===
base_y = 1095            # 5px下げる
row_height = 310         # 行間はそのまま
num_box_x = (270, 610)   # 右に20pxずらす
time_box_x = (690, 1190) # 右に20pxずらす

def crop_debug_images(img_path):
    img = Image.open(img_path)
    img_w, img_h = img.size
    print(f"画像サイズ: {img_w} x {img_h}")

    cropped_paths = []

    # ✅ サーバー番号はそのまま
    server_crop_path = "/tmp/debug_server.png"
    img.crop(server_box).save(server_crop_path)

    # ✅ 駐騎場3行を右20・下5補正で切り出す
    for i in range(3):
        y1 = base_y + i * row_height
        y2 = y1 + 110

        num_crop_path = f"/tmp/debug_num_{i+1}.png"
        time_crop_path = f"/tmp/debug_time_{i+1}.png"

        img.crop((num_box_x[0], y1, num_box_x[1], y2)).save(num_crop_path)
        img.crop((time_box_x[0], y1, time_box_x[1], y2)).save(time_crop_path)

        cropped_paths.append((num_crop_path, time_crop_path))

    return server_crop_path, cropped_paths

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        await message.channel.send("✅ 画像を受け取りました！駐騎場を右に20px・下に5px調整して切り出します…")
        
        for attachment in message.attachments:
            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)

            server_img, crops = crop_debug_images(file_path)

            # サーバー番号画像（変更なし）
            await message.channel.send("サーバー番号の切り出し結果", file=discord.File(server_img))

            # 駐騎場3行分（右20px・下5px補正）
            for idx, (num_img, time_img) in enumerate(crops, start=1):
                await message.channel.send(
                    f"行{idx} の切り出し結果（駐騎場番号 / 免戦時間）",
                    files=[
                        discord.File(num_img, filename=f"行{idx}_番号.png"),
                        discord.File(time_img, filename=f"行{idx}_時間.png")
                    ]
                )

client.run(TOKEN)