import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
import os
from flask import Flask
from threading import Thread

# --- ตั้งค่า Bot ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # สำคัญ: ต้องเปิดใน Developer Portal
        intents.members = True          # สำหรับการจัดการสมาชิกและการส่ง DM
        super().__init__(command_prefix="!", intents=intents)
        self.antispam_enabled = False
        self.user_messages = {} # {user_id: [timestamps]}
        self.warn_count = {}   # {user_id: count}

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced Slash Commands เรียบร้อย!")

bot = MyBot()

# --- Slash Command: /เปิด ---
@bot.tree.command(name="เปิด", description="เปิดระบบป้องกันสแปม")
async def open_antispam(interaction: discord.Interaction):
    bot.antispam_enabled = True
    await interaction.response.send_message("🛡️ **ระบบป้องกันสแปม:** เปิดใช้งานแล้ว! (ตรวจจับ 5 ข้อความรัวๆ)")

# --- ระบบตรวจจับข้อความ ---
@bot.event
async def on_message(message):
    if not bot.antispam_enabled or message.author.bot or not message.guild:
        return

    user_id = message.author.id
    now = datetime.datetime.now().timestamp()

    # ตรวจสอบความถี่ข้อความ
    if user_id not in bot.user_messages:
        bot.user_messages[user_id] = []
    
    bot.user_messages[user_id].append(now)
    # กรองเอาเฉพาะข้อความที่ส่งภายใน 5 วินาทีล่าสุด
    bot.user_messages[user_id] = [t for t in bot.user_messages[user_id] if now - t < 5]

    if len(bot.user_messages[user_id]) >= 5:
        # 1. ลบข้อความสแปม
        try:
            await message.delete()
        except:
            pass

        # 2. นับจำนวนการเตือน
        count = bot.warn_count.get(user_id, 0) + 1
        bot.warn_count[user_id] = count

        if count >= 3:
            # 3. ลงโทษ: หมดเวลา (Timeout) 5 นาที
            duration = datetime.timedelta(minutes=5)
            try:
                await message.author.timeout(duration, reason="สแปมข้อความเกิน 3 ครั้ง")
                
                # 4. ส่ง DM หาคนสแปม
                try:
                    await message.author.send(f"⚠️ คุณถูกระงับการพิมพ์ในเซิร์ฟเวอร์ {message.guild.name} เป็นเวลา 5 นาที เนื่องจากสแปมข้อความ")
                except:
                    pass # กรณีปิด DM

                # รีเซ็ตค่าหลังโดนลงโทษ
                bot.warn_count[user_id] = 0
                bot.user_messages[user_id] = []
            except Exception as e:
                print(f"Error: {e}")
        else:
            # 5. เตือนพร้อม Tag @
            warning = await message.channel.send(f"⚠️ {message.author.mention} **หยุดสแปม!** เตือนครั้งที่ {count}/3 (ถ้าครบ 3 ครั้งจะโดน Timeout 5 นาที)")
            await asyncio.sleep(3)
            await warning.delete() # ลบคำเตือนทิ้งเพื่อไม่ให้แชทรกรุงรัง

    await bot.process_commands(message)

# --- ส่วนของ Render.com (Keep Alive) ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- เริ่มรันบอท ---
if __name__ == "__main__":
    keep_alive()
    token = os.environ.get('TOKEN') # ใส่ Token ใน Environment Variable ของ Render
    bot.run(token)
              
