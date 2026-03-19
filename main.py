import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
import os
import yt_dlp
from flask import Flask
from threading import Thread

# ---------- ตั้งค่าระบบรันบนเว็บไซต์ (Render) ----------
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ---------- เริ่มต้นโค้ดบอทของแทน ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True # เพิ่มสิทธิ์สำหรับเข้าห้องเสียง

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.antispam_enabled = False
        self.user_messages = {}
        self.warn_count = {}

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Sync Slash Commands และเข้าระบบแล้วในชื่อ {self.user}")

bot = MyBot()

# ตั้งค่าสำหรับเล่นเพลง (ปรับปรุงเพื่อให้หาไฟล์ FFmpeg ที่โหลดมาเจอ)
YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True'}
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
    'options': '-vn',
    'executable': './ffmpeg/ffmpeg' # <--- เพิ่มบรรทัดนี้เพื่อให้รันบน Render ได้
}

# เก็บค่าการตั้งค่าห้องต้อนรับ/ลาออก
welcome_settings = {}

# ---------- 7. ระบบเพลง (เพิ่มเข้าไปใหม่) ----------
@bot.tree.command(name="play", description="เปิดเพลงจาก YouTube")
@app_commands.describe(url="ใส่ลิงก์เพลงจาก YouTube")
async def play(interaction: discord.Interaction, url: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ คุณต้องเข้าห้องเสียงก่อน!", ephemeral=True)

    await interaction.response.defer() # ป้องกันบอทค้างขณะโหลดเพลง
    
    channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client

    if not vc:
        vc = await channel.connect()
    else:
        await vc.move_to(channel)
    
    if vc.is_playing():
        vc.stop()

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            url2 = info['url']
            # ใช้ PyNaCl เบื้องหลังในการจัดการ Voice
            source = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)
            vc.play(source)
            await interaction.followup.send(f"🎶 กำลังเล่นเพลง: **{info['title']}**")
        except Exception as e:
            await interaction.followup.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.tree.command(name="stop", description="หยุดเพลงและออกจากห้องเสียง")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
        await interaction.response.send_message("👋 หยุดเพลงและออกจากห้องเสียงแล้ว")
    else:
        await interaction.response.send_message("❌ บอทไม่ได้อยู่ในห้องเสียง", ephemeral=True)

# ---------- ระบบสแปม (โค้ดเดิมของแทน) ----------
@bot.tree.command(name="เปิด", description="เปิดระบบป้องกันสแปม")
async def open_antispam(interaction: discord.Interaction):
    bot.antispam_enabled = True
    await interaction.response.send_message("🛡️ **ระบบป้องกันสแปม:** เปิดใช้งานแล้ว! (5 ข้อความรัวๆ / เตือน 3 ครั้ง / Timeout 5 นาที)")

@bot.event
async def on_message(message):
    if bot.antispam_enabled and not message.author.bot and message.guild:
        user_id = message.author.id
        now = datetime.datetime.now().timestamp()
        if user_id not in bot.user_messages:
            bot.user_messages[user_id] = []
        bot.user_messages[user_id].append(now)
        bot.user_messages[user_id] = [t for t in bot.user_messages[user_id] if now - t < 5]

        if len(bot.user_messages[user_id]) >= 5:
            try: await message.delete()
            except: pass
            count = bot.warn_count.get(user_id, 0) + 1
            bot.warn_count[user_id] = count
            if count >= 3:
                duration = datetime.timedelta(minutes=5)
                try:
                    await message.author.timeout(duration, reason="สแปมข้อความเกินกำหนด")
                    try: await message.author.send(f"⚠️ คุณถูกระงับการพิมพ์ในเซิร์ฟเวอร์ {message.guild.name} เป็นเวลา 5 นาที เนื่องจากสแปม")
                    except: pass
                    bot.warn_count[user_id] = 0
                    bot.user_messages[user_id] = []
                except: pass
            else:
                warning = await message.channel.send(f"⚠️ {message.author.mention} **หยุดสแปม!** เตือนครั้งที่ {count}/3")
                await asyncio.sleep(3)
                await warning.delete()
    await bot.process_commands(message)

# ---------- 1. ระบบรายงานปัญหา (โค้ดเดิมของแทน) ----------
class ReportModal(discord.ui.Modal, title="รายงานปัญหาในเซิร์ฟเวอร์"):
    problem = discord.ui.TextInput(label="พิมพ์ปัญหาของคุณที่นี่", style=discord.TextStyle.long)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        owner = interaction.guild.owner
        try:
            await owner.send(f"📢 **มีรายงานใหม่จาก {interaction.user}**\n```{self.problem.value}```")
            await interaction.followup.send("✅ รายงานสำเร็จ!", ephemeral=True)
        except:
            await interaction.followup.send("❌ ส่งไม่สำเร็จ", ephemeral=True)

class ReportButton(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📩 รายงานปัญหา", style=discord.ButtonStyle.danger)
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal())

@bot.tree.command(name="report", description="ตั้ง UI รายงานปัญหาในห้องที่เลือก")
async def report_command(interaction: discord.Interaction, channel: discord.TextChannel):
    await channel.send("📣 หากพบปัญหาในเซิร์ฟเวอร์ กดปุ่มด้านล่างเพื่อรายงาน", view=ReportButton())
    await interaction.response.send_message("✅ ตั้ง UI รายงานปัญหาเรียบร้อย!", ephemeral=True)

# ---------- 2. ระบบยืนยันตัวตน (โค้ดเดิมของแทน) ----------
class VerifyModal(discord.ui.Modal, title="ยืนยันตัวตน"):
    name = discord.ui.TextInput(label="กรอกชื่อของคุณ", style=discord.TextStyle.short)
    def __init__(self, verify_channel, success_channel, role):
        super().__init__()
        self.verify_channel, self.success_channel, self.role = verify_channel, success_channel, role
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.success_channel.send(f"✅ {interaction.user.mention} ยืนยันตัวตนสำเร็จ! (ชื่อ: {self.name.value})")
            if self.role: await interaction.user.add_roles(self.role)
            await interaction.followup.send("🎉 ยืนยันตัวตนเรียบร้อย!", ephemeral=True)
        except: await interaction.followup.send("❌ บอทไม่มีสิทธิ์ให้ยศ", ephemeral=True)

class VerifyButton(discord.ui.View):
    def __init__(self, vc, sc, r):
        super().__init__(timeout=None)
        self.vc, self.sc, self.r = vc, sc, r
    @discord.ui.button(label="✅ ยืนยันตัวตน", style=discord.ButtonStyle.success)
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerifyModal(self.vc, self.sc, self.r))

@bot.tree.command(name="verify", description="ตั้งระบบยืนยันตัวตน")
async def verify_command(interaction: discord.Interaction, verify_channel: discord.TextChannel, success_channel: discord.TextChannel, role: discord.Role):
    await verify_channel.send("👤 กดยืนยันตัวตนด้านล่างเพื่อเริ่ม", view=VerifyButton(verify_channel, success_channel, role))
    await interaction.response.send_message("✅ ตั้งระบบยืนยันตัวตนเรียบร้อย!", ephemeral=True)

# ---------- 3, 4, 5, 6 (โค้ดเดิมของแทน) ----------
@bot.tree.command(name="send_message")
async def send_message(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(message)
    await interaction.response.send_message("✅ ส่งเรียบร้อย!", ephemeral=True)

@bot.tree.command(name="dm_all")
async def dm_all(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("📨 กำลังส่ง...", ephemeral=True)
    count = 0
    async for member in interaction.guild.fetch_members(limit=None):
        if not member.bot:
            try: await member.send(message); count += 1
            except: pass
    await interaction.followup.send(f"✅ ส่งถึง {count} คนแล้ว!", ephemeral=True)

@bot.tree.command(name="dm_one")
async def dm_one(interaction: discord.Interaction, member: discord.Member, message: str):
    try: await member.send(message); await interaction.response.send_message("✅ ส่งแล้ว!", ephemeral=True)
    except: await interaction.response.send_message("❌ ส่งไม่ได้", ephemeral=True)

@bot.tree.command(name="setup_welcome")
async def setup_welcome(interaction: discord.Interaction, join_channel: discord.TextChannel, leave_channel: discord.TextChannel):
    welcome_settings[interaction.guild.id] = {"join": join_channel.id, "leave": leave_channel.id}
    await interaction.response.send_message("✅ ตั้งค่าเรียบร้อย!", ephemeral=True)

@bot.event
async def on_member_join(member):
    data = welcome_settings.get(member.guild.id)
    if data:
        ch = member.guild.get_channel(data["join"])
        if ch: await ch.send(f"👋 ยินดีต้อนรับ {member.mention}!")

@bot.event
async def on_member_remove(member):
    data = welcome_settings.get(member.guild.id)
    if data:
        ch = member.guild.get_channel(data["leave"])
        if ch: await ch.send(f"😢 {member} ออกไปแล้ว")

# ---------- เริ่มรันระบบ ----------
if __name__ == "__main__":
    keep_alive()
    token = os.environ.get('TOKEN')
    if token: bot.run(token)
    else: print("❌ ไม่พบ TOKEN!")
