import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import os
import asyncio
from datetime import datetime
from typing import Literal
import base64
import requests
import re

# ================= GitHub Sync Configuration =================
GITHUB_TOKEN = "usfh"
GITHUB_REPO = "faresx100/kings-league"

def update_github_data():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None

    with open("data.json", "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "message": "Auto-update data.json from Discord Bot",
        "content": content
    }

    if sha:
        payload["sha"] = sha

    res = requests.put(url, json=payload, headers=headers)

    if res.status_code in [200, 201]:
        print("✅ تم تحديث البيانات على GitHub بنجاح!")
    else:
        print(f"❌ فشل التحديث على GitHub! رمز الخطأ: {res.status_code}")
        print(res.json())

_default_branch_cache = None

def get_github_default_branch():
    """Cached lookup of the repo's default branch, used to build raw.githubusercontent.com URLs."""
    global _default_branch_cache
    if _default_branch_cache:
        return _default_branch_cache
    try:
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
        r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}", headers=headers)
        _default_branch_cache = r.json().get("default_branch", "main") if r.status_code == 200 else "main"
    except Exception:
        _default_branch_cache = "main"
    return _default_branch_cache

def upload_image_to_github(image_bytes, filename):
    """Permanently host an image (e.g. a team logo) inside the GitHub repo under /logos and
    return a raw.githubusercontent.com URL for it. Discord's own attachment URLs are signed
    and expire after a while (this is exactly why team logos kept disappearing), so anything
    that needs to stay valid long-term should be re-hosted here instead of using the Discord
    CDN link directly.
    """
    try:
        path = f"logos/{filename}"
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

        r = requests.get(url, headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None

        payload = {
            "message": f"Upload logo {filename}",
            "content": base64.b64encode(image_bytes).decode("utf-8")
        }
        if sha:
            payload["sha"] = sha

        res = requests.put(url, json=payload, headers=headers)
        if res.status_code in [200, 201]:
            branch = get_github_default_branch()
            return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{branch}/{path}"
        print(f"❌ Failed to upload logo {filename}: {res.status_code} {res.text}")
        return None
    except Exception as e:
        print(f"❌ Error uploading logo {filename}: {e}")
        return None

# ================= CONFIGURATION =================
TOKEN = "sdfjsndj"
GUILD_ID = 1399563718580244692

# Channel IDs
ADMIN_APP_CHANNEL_ID = 1402003214785708114
SIGNING_CHANNEL_ID   = 1401008749581308015
ROSTER_CHANNEL_ID    = 1401009153706823690
FIXTURES_CHANNEL_ID  = 1401013041490956410
RESULT_CHANNEL_ID    = 1401013712147447979
LOANS_CHANNEL_ID     = 1531979357793419304
RELEASE_CHANNEL_ID   = 1531980077863010334

# Role IDs
MANAGER_ROLE_ID    = 1400489346087391263
CO_MANAGER_ROLE_ID = 1400490121240903792

KINGS_LEAGUE_LOGO = "https://cdn.discordapp.com/attachments/1400659033777770546/1532741403782811799/kings_logo.png?ex=6a6df42b&is=6a6ca2ab&hm=ef1048b4a158c5ef3e2a35d9062a6a05dd43b859daf9d98b31442476b566bb35&"
MAX_NEWS_ITEMS = 8
# =================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Helpers for data management
def load_data():
    if not os.path.exists('data.json'):
        return {
            "standings": [], "news": [], "matches": [], "rosters": {},
            "roster_messages": {},
            "last_fixtures": [], "top_scorers": {}, "top_assists": {},
            "man_of_the_match": None,
            "team_of_the_week": {"GK": "N/A", "CB": "N/A", "CM": "N/A", "LST": "N/A", "RST": "N/A"},
            "results": [],
            "leaderboard": []
        }
    with open('data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        if "roster_messages" not in data:
            data["roster_messages"] = {}
        if "results" not in data:
            data["results"] = []
        if "leaderboard" not in data:
            data["leaderboard"] = []
        return data

def save_data(data):
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_website_news(data, title, content, badge="NEWS"):
    if "news" not in data:
        data["news"] = []
    data["news"].insert(0, {
        "title": title,
        "content": content,
        "badge": badge,
        "timestamp": datetime.now().strftime("%H:%M - %b %d")
    })
    if len(data["news"]) > MAX_NEWS_ITEMS:
        data["news"] = data["news"][:MAX_NEWS_ITEMS]

# 🌟 دالة تحديث رسالة الروستر الواحدة لكل فريق (Edit بدلاً من Send جديد)
async def update_roster_channel_message(team_name: str, team_logo: str, data: dict):
    roster_channel = bot.get_channel(ROSTER_CHANNEL_ID)
    if not roster_channel:
        return

    players = data["rosters"].get(team_name, [])
    roster_embed = discord.Embed(
        title=f"🛡 {team_name} Official Roster",
        color=discord.Color.gold()
    )
    roster_text = "\n".join([f"• {p}" for p in players])
    roster_embed.add_field(name=f"Players Registered ({len(players)}/9)", value=roster_text or "No players", inline=False)
    roster_embed.set_thumbnail(url=team_logo)
    roster_embed.set_footer(text="Kings League VRFS • Official Roster Card", icon_url=KINGS_LEAGUE_LOGO)

    msg_id = data.get("roster_messages", {}).get(team_name)
    if msg_id:
        try:
            msg = await roster_channel.fetch_message(msg_id)
            await msg.edit(embed=roster_embed)
            return
        except discord.NotFound:
            pass

    new_msg = await roster_channel.send(embed=roster_embed)
    if "roster_messages" not in data:
        data["roster_messages"] = {}
    data["roster_messages"][team_name] = new_msg.id
    save_data(data)

# Permission & Role Checks
def is_team_leader(interaction: discord.Interaction) -> bool:
    user_role_ids = [r.id for r in interaction.user.roles]
    return (
        MANAGER_ROLE_ID in user_role_ids
        or CO_MANAGER_ROLE_ID in user_role_ids
        or interaction.user.guild_permissions.administrator
    )

def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator

def get_team_role(user: discord.Member) -> discord.Role:
    data = load_data()
    valid_team_names = [t["name"] for t in data.get("standings", [])]
    
    for role in user.roles:
        if role.name in valid_team_names:
            return role
            
    return None

@bot.event
async def on_ready():
    print(f"✅ Kings League Bot is online as {bot.user}!")
    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print("⚡️ All slash commands synced successfully with updated permissions & Role IDs!")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# ==========================================
# 1. PRIVATE DM APPLICATION WORKFLOW (/apply)
# ==========================================

class AdminApproveView(discord.ui.View):
    def __init__(self, applicant_id, co_mention, team_name, team_abbr, logo_url):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.co_mention = co_mention
        self.team_name = team_name
        self.team_abbr = team_abbr
        self.logo_url = logo_url

    @discord.ui.button(label="Approve Team", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only server Administrators can approve teams!", ephemeral=True)
            return

        await interaction.response.defer()

        guild = interaction.guild
        applicant = guild.get_member(self.applicant_id)

        m_role = guild.get_role(MANAGER_ROLE_ID)
        if applicant and m_role:
            await applicant.add_roles(m_role)

        if self.co_mention and self.co_mention.lower() not in ["none", "n/a", "no"]:
            co_id = ''.join(filter(str.isdigit, self.co_mention))
            if co_id:
                co_member = guild.get_member(int(co_id))
                co_role = guild.get_role(CO_MANAGER_ROLE_ID)
                if co_member and co_role:
                    await co_member.add_roles(co_role)

        team_role = await guild.create_role(name=self.team_name, color=discord.Color.blue())
        if applicant:
            await applicant.add_roles(team_role)

        data = load_data()
        data["standings"].append({
            "name": self.team_name,
            "abbr": self.team_abbr,
            "logo": self.logo_url,
            "pts": 0, "mp": 0, "w": 0, "l": 0, "gf": 0, "ga": 0
        })
        data["rosters"][self.team_name] = [applicant.display_name if applicant else "Manager"]
        add_website_news(data, "NEW TEAM JOINED", f"{self.team_name} ({self.team_abbr}) has officially joined Kings League!", "NEW TEAM")
        
        save_data(data)
        update_github_data()

        await update_roster_channel_message(self.team_name, self.logo_url, data)

        button.disabled = True
        button.label = "Approved ✅"
        await interaction.edit_original_response(view=self)
        await interaction.followup.send(f"🎉 Team **{self.team_name}** approved and added to official standings!")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only server Administrators can reject teams!", ephemeral=True)
            return

        button.disabled = True
        button.label = "Rejected ❌"
        await interaction.response.edit_message(view=self)

@bot.tree.command(name="apply", description="Open for EVERYONE: Submit a team registration application via Direct Messages (DM)")
async def apply(interaction: discord.Interaction):
    user = interaction.user

    try:
        dm_channel = await user.create_dm()
        await interaction.response.send_message("📩 Application started! Please check your **Direct Messages (DMs)** to complete registration.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("❌ Could not open DMs! Please enable 'Allow Direct Messages from server members' in your Settings.", ephemeral=True)
        return

    def check(m):
        return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)

    try:
        await dm_channel.send("📋 **KINGS LEAGUE TEAM APPLICATION**\n\n**Step 1/6:** What is your **Full Team Name**? (e.g. Barcelona FC)")
        msg_name = await bot.wait_for('message', check=check, timeout=120.0)
        team_name = msg_name.content

        await dm_channel.send("**Step 2/6:** What is your **Team Abbreviation**? (e.g. BAR)")
        msg_abbr = await bot.wait_for('message', check=check, timeout=120.0)
        team_abbr = msg_abbr.content.upper()

        await dm_channel.send("**Step 3/6:** Do you have a Co-Manager? Please **mention them** (e.g. `@Username`), or type `None` if none.")
        msg_co = await bot.wait_for('message', check=check, timeout=120.0)
        co_mention = msg_co.content

        await dm_channel.send("**Step 4/6:** Please upload/send an image file of your **Official Team Logo**.")
        def check_img(m):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel) and len(m.attachments) > 0

        msg_logo = await bot.wait_for('message', check=check_img, timeout=120.0)
        logo_attachment = msg_logo.attachments[0]
        logo_ext = logo_attachment.filename.rsplit('.', 1)[-1].lower() if '.' in logo_attachment.filename else 'png'
        logo_bytes = await logo_attachment.read()
        hosted_logo_url = upload_image_to_github(logo_bytes, f"{team_abbr.lower()}_{user.id}.{logo_ext}")
        # Fall back to the raw Discord link only if the GitHub upload failed — that link will
        # eventually expire, but it's better than losing the logo entirely.
        logo_url = hosted_logo_url or logo_attachment.url

        await dm_channel.send("**Step 5/6:** Please upload/send an image file of your **Latest Activity Check**.")
        msg_act = await bot.wait_for('message', check=check_img, timeout=120.0)
        activity_url = msg_act.attachments[0].url

        await dm_channel.send("**Step 6/6:** How many total members are in your team right now? (Send a number)")
        def check_num(m):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel) and m.content.isdigit()
        
        msg_num = await bot.wait_for('message', check=check_num, timeout=120.0)
        member_count = msg_num.content

        admin_channel = bot.get_channel(ADMIN_APP_CHANNEL_ID)
        embed = discord.Embed(title="📋 NEW TEAM REGISTRATION APPLICATION", color=discord.Color.gold())
        embed.add_field(name="Applicant Manager", value=user.mention, inline=True)
        embed.add_field(name="Full Team Name", value=team_name, inline=True)
        embed.add_field(name="Abbreviation", value=team_abbr, inline=True)
        embed.add_field(name="Co-Manager Mention", value=co_mention, inline=True)
        embed.add_field(name="Member Count", value=member_count, inline=True)
        embed.set_thumbnail(url=logo_url)
        embed.set_image(url=activity_url)

        view = AdminApproveView(
            applicant_id=user.id,
            co_mention=co_mention,
            team_name=team_name,
            team_abbr=team_abbr,
            logo_url=logo_url
        )
        await admin_channel.send(embed=embed, view=view)
        await dm_channel.send("✅ **Application Submitted!** Staff members will review your request shortly.")

    except asyncio.TimeoutError:
        await dm_channel.send("⏱️ **Application Timed Out.** Please type `/apply` in the server to try again.")
    except Exception as e:
        await dm_channel.send(f"❌ An error occurred during submission: {e}")

# ==========================================
# 2. MANAGER COMMANDS (/sign, /release, /loan)
# ==========================================

class SignConfirmationView(discord.ui.View):
    def __init__(self, manager: discord.Member, player: discord.Member, team_name: str, in_game_name: str, team_role: discord.Role, team_logo: str):
        super().__init__(timeout=120)
        self.manager = manager
        self.player = player
        self.team_name = team_name
        self.in_game_name = in_game_name
        self.team_role = team_role
        self.team_logo = team_logo

    @discord.ui.button(label="Accept Offer", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("This offer is not for you!", ephemeral=True)
            return

        data = load_data()
        current_roster = data["rosters"].get(self.team_name, [])

        if self.in_game_name in current_roster:
            await interaction.response.send_message("❌ You are already registered in this team's roster!", ephemeral=True)
            return

        if len(current_roster) >= 9:
            await interaction.response.send_message("❌ This team roster is full (Maximum 9 players)!", ephemeral=True)
            return

        await interaction.response.defer()

        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)

        await self.player.add_roles(self.team_role)

        if self.team_name not in data["rosters"]:
            data["rosters"][self.team_name] = []
        data["rosters"][self.team_name].append(self.in_game_name)

        add_website_news(data, "PLAYER TRANSFER", f"{self.in_game_name} signed for {self.team_name}!", "SIGNING")
        
        save_data(data)
        update_github_data()

        current_count = len(data["rosters"][self.team_name])

        sign_channel = bot.get_channel(SIGNING_CHANNEL_ID)
        embed = discord.Embed(
            title="📝 OFFICIAL SIGNING",
            description=f"**{self.player.mention}** has officially transferred to **{self.team_name}**!\n\n**Team Roster Count:** `{current_count}/9`",
            color=discord.Color.green()
        )
        embed.set_author(name="Kings League VRFS", icon_url=KINGS_LEAGUE_LOGO)
        embed.set_thumbnail(url=self.team_logo)
        await sign_channel.send(embed=embed)

        await update_roster_channel_message(self.team_name, self.team_logo, data)

        await interaction.followup.send(f"✅ Contract accepted! You joined **{self.team_name}**.")

    @discord.ui.button(label="Decline Offer", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            return
        
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("❌ Contract offer declined.", ephemeral=True)

@bot.tree.command(name="sign", description="For Managers/Co-Managers: Sign a player to your team roster")
@app_commands.describe(
    player="Select the Discord member you want to sign",
    player_in_game_name="Write the in-game display name / gamertag of the player"
)
async def sign(interaction: discord.Interaction, player: discord.Member, player_in_game_name: str):
    if not is_team_leader(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only Managers or Co-Managers can use this command!", ephemeral=True)
        return

    team_role = get_team_role(interaction.user)
    if not team_role:
        await interaction.response.send_message("❌ Team Error: Could not detect your team role!", ephemeral=True)
        return

    data = load_data()
    current_roster = data["rosters"].get(team_role.name, [])

    if len(current_roster) >= 9:
        await interaction.response.send_message("❌ Your team roster is already full (Maximum 9 players)!", ephemeral=True)
        return

    if player_in_game_name in current_roster:
        await interaction.response.send_message("❌ This player is already in your team's roster!", ephemeral=True)
        return

    team_logo = next((t["logo"] for t in data["standings"] if t["name"] == team_role.name), KINGS_LEAGUE_LOGO)

    offer_embed = discord.Embed(
        title="📝 OFFICIAL CONTRACT OFFER",
        description=f"You have received a formal offer to join **{team_role.name}** for Kings League VRFS.",
        color=discord.Color.gold()
    )
    offer_embed.set_author(name=f"{team_role.name} Management", icon_url=team_logo)
    offer_embed.set_thumbnail(url=team_logo)
    offer_embed.add_field(name="Club Name", value=f"**{team_role.name}**", inline=True)
    offer_embed.add_field(name="Submitted By", value=interaction.user.mention, inline=True)
    offer_embed.add_field(name="Registered Gamertag", value=f"`{player_in_game_name}`", inline=False)
    offer_embed.set_footer(text="Kings League VRFS • Select an option below to respond", icon_url=KINGS_LEAGUE_LOGO)

    view = SignConfirmationView(interaction.user, player, team_role.name, player_in_game_name, team_role, team_logo)
    await interaction.response.send_message(f"📨 Transfer offer sent privately to {player.mention}!", ephemeral=True)
    
    try:
        await player.send(embed=offer_embed, view=view)
    except Exception:
        await interaction.followup.send(f"❌ Failed to send DM to {player.mention}. Their DMs might be closed.", ephemeral=True)


@bot.tree.command(name="release", description="For Managers/Co-Managers: Release a player from your team roster")
@app_commands.describe(player="Select the player you want to remove/release from your team")
async def release(interaction: discord.Interaction, player: discord.Member):
    if not is_team_leader(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only Managers or Co-Managers can use this command!", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)

    team_role = get_team_role(interaction.user)
    if not team_role or team_role not in player.roles:
        await interaction.followup.send("❌ Release Error: This player does not belong to your team!", ephemeral=True)
        return

    await player.remove_roles(team_role)

    data = load_data()
    team_logo = next((t["logo"] for t in data["standings"] if t["name"] == team_role.name), KINGS_LEAGUE_LOGO)

    if team_role.name in data["rosters"]:
        data["rosters"][team_role.name] = [p for p in data["rosters"][team_role.name] if player.display_name not in p]

    add_website_news(data, "PLAYER RELEASED", f"{player.display_name} has been released from {team_role.name}.", "RELEASE")
    
    save_data(data)
    update_github_data()

    rel_channel = bot.get_channel(RELEASE_CHANNEL_ID)
    embed = discord.Embed(
        title="🔴 CONTRACT TERMINATED",
        description=f"**{player.mention}** has been released from **{team_role.name}**.",
        color=discord.Color.red()
    )
    embed.set_author(name="Kings League VRFS", icon_url=KINGS_LEAGUE_LOGO)
    embed.set_thumbnail(url=team_logo)
    await rel_channel.send(embed=embed)

    await update_roster_channel_message(team_role.name, team_logo, data)

    await interaction.followup.send(f"✅ Released {player.mention} from **{team_role.name}** successfully.", ephemeral=True)


async def emergency_loan_timer(guild: discord.Guild, player: discord.Member, team_role: discord.Role):
    await asyncio.sleep(2400) # 40 Minutes
    if team_role in player.roles:
        await player.remove_roles(team_role)
        data = load_data()
        if team_role.name in data["rosters"]:
            data["rosters"][team_role.name] = [p for p in data["rosters"][team_role.name] if player.display_name not in p]
        add_website_news(data, "E-LOAN EXPIRED", f"Emergency 40-minute loan for {player.display_name} at {team_role.name} has concluded.", "E-LOAN")
        
        save_data(data)
        update_github_data()

        team_logo = next((t["logo"] for t in data["standings"] if t["name"] == team_role.name), KINGS_LEAGUE_LOGO)
        await update_roster_channel_message(team_role.name, team_logo, data)

@bot.tree.command(name="loan", description="For Managers/Co-Managers: Loan a player (Standard or Emergency 40-min Loan)")
@app_commands.describe(
    loan_type="Choose type: 'Loan' (Standard >=3 matches) or 'E-Loan' (Emergency 40 mins)",
    player="Select the player to borrow/loan to your team",
    duration_or_notes="Write duration or match time (e.g., '3 Matches' or 'Match vs Real Madrid at 9 PM')"
)
async def loan(interaction: discord.Interaction, loan_type: Literal['Loan', 'E-Loan'], player: discord.Member, duration_or_notes: str):
    if not is_team_leader(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only Managers or Co-Managers can use this command!", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    team_role = get_team_role(interaction.user)
    if not team_role:
        await interaction.followup.send("❌ Team Error: Could not detect your team role!", ephemeral=True)
        return

    data = load_data()
    current_roster = data["rosters"].get(team_role.name, [])

    if loan_type == "Loan" and len(current_roster) >= 9:
        await interaction.followup.send("❌ Your team roster is already full (Maximum 9 players)! Emergency Loan (E-Loan) is allowed if full.", ephemeral=True)
        return

    await player.add_roles(team_role)

    if team_role.name not in data["rosters"]:
        data["rosters"][team_role.name] = []
    data["rosters"][team_role.name].append(f"{player.display_name} ({loan_type})")

    add_website_news(data, f"{loan_type.upper()} ARRIVAL", f"{player.display_name} joined {team_role.name} on a {loan_type}! ({duration_or_notes})", "LOAN")
    
    save_data(data)
    update_github_data()

    loan_chan = bot.get_channel(LOANS_CHANNEL_ID)
    embed = discord.Embed(
        title=f"🔄 NEW {loan_type.upper()}",
        description=f"**{player.mention}** joined **{team_role.name}**!\n**Type:** {loan_type}\n**Details:** {duration_or_notes}",
        color=discord.Color.purple()
    )
    embed.set_author(name="Kings League VRFS", icon_url=KINGS_LEAGUE_LOGO)
    await loan_chan.send(embed=embed)

    team_logo = next((t["logo"] for t in data["standings"] if t["name"] == team_role.name), KINGS_LEAGUE_LOGO)
    await update_roster_channel_message(team_role.name, team_logo, data)

    if loan_type == "E-Loan":
        asyncio.create_task(emergency_loan_timer(interaction.guild, player, team_role))
        await interaction.followup.send(f"✅ Emergency Loan (40 mins countdown) active for {player.mention}! (Allowed even if roster is full)", ephemeral=True)
    else:
        await interaction.followup.send(f"✅ Regular Loan logged for {player.mention}!", ephemeral=True)

# ==========================================
# 3. ADMINISTRATOR ONLY COMMANDS
# ==========================================

# Helper: extract display names from mentions with parentheses format
# Format: "@mention (Name) @mention2 (Name2)" -> extracts names in parentheses

def extract_player_pairs(input_str):
    """Extract (discord_id, name) pairs from an input string.
    Example: '<@123> (Hadi) <@456> (ItzARO)' -> [('123', 'Hadi'), ('456', 'ItzARO')]
    Using the Discord ID (not just the typed name) as the key means the same
    player is always recognized across matches, even if the name in parentheses
    is typed slightly differently next time.
    """
    pairs = re.findall(r'<@!?(\d+)>\s*\(([^)]+)\)', input_str)
    return [(pid, name.strip()) for pid, name in pairs if name.strip()]

def resolve_team_for_player(data, player_name, team1_name, team2_name):
    """Look up which team's roster a player belongs to, by name (case-insensitive)."""
    t1_roster = {p.strip().lower() for p in data.get("rosters", {}).get(team1_name, [])}
    t2_roster = {p.strip().lower() for p in data.get("rosters", {}).get(team2_name, [])}
    key = player_name.strip().lower()
    if key in t1_roster:
        return 1
    if key in t2_roster:
        return 2
    return None

def update_leaderboard(data, scorer_pairs, assist_pairs, clean_sheet_pairs):
    """Update leaderboard: Goal=2pts, Assist=1pt, CleanSheet=5pts.
    Each *_pairs argument is a list of (discord_id, name) tuples. Players are matched
    primarily by discord_id so repeated mentions of the same player always update the
    same leaderboard row instead of creating a new one. Legacy rows saved before IDs
    were tracked are matched by name (case-insensitive) and get healed with an id
    the first time that player is mentioned again.
    """
    if "leaderboard" not in data:
        data["leaderboard"] = []

    def get_or_create(pid, name):
        name = name.strip()
        if pid:
            for p in data["leaderboard"]:
                if p.get("id") == pid:
                    p["name"] = name
                    return p
        for p in data["leaderboard"]:
            if not p.get("id") and p["name"].strip().lower() == name.lower():
                if pid:
                    p["id"] = pid
                return p
        new_p = {"id": pid, "name": name, "goals": 0, "assists": 0, "clean_sheets": 0, "points": 0}
        data["leaderboard"].append(new_p)
        return new_p

    def recalc(p):
        p["points"] = (p.get("goals", 0) * 2) + (p.get("assists", 0) * 1) + (p.get("clean_sheets", 0) * 5)

    for pid, name in scorer_pairs:
        p = get_or_create(pid, name)
        p["goals"] = p.get("goals", 0) + 1
        recalc(p)

    for pid, name in assist_pairs:
        p = get_or_create(pid, name)
        p["assists"] = p.get("assists", 0) + 1
        recalc(p)

    for pid, name in clean_sheet_pairs:
        p = get_or_create(pid, name)
        p["clean_sheets"] = p.get("clean_sheets", 0) + 1
        recalc(p)

    # Regenerate top_scorers / top_assists straight from the leaderboard so the website
    # always shows real player names (never raw Discord mentions) and stays in sync.
    data["top_scorers"] = {p["name"]: p["goals"] for p in data["leaderboard"] if p.get("goals", 0) > 0}
    data["top_assists"] = {p["name"]: p["assists"] for p in data["leaderboard"] if p.get("assists", 0) > 0}

def build_congrats_embed(name, goals, assists, team1_name, team2_name, score1, score2):
    """Professional congratulations DM sent to players who scored or assisted."""
    contributions = []
    if goals > 0:
        contributions.append(f"{goals} goal{'s' if goals != 1 else ''}")
    if assists > 0:
        contributions.append(f"{assists} assist{'s' if assists != 1 else ''}")
    contribution_text = " and ".join(contributions)

    embed = discord.Embed(
        title="Match Performance",
        description=(
            f"Well played in **{team1_name} {score1} - {score2} {team2_name}**.\n\n"
            f"You're credited with **{contribution_text}** in this match, and your "
            f"stats have been updated on the Kings League leaderboard."
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Kings League VRFS", icon_url=KINGS_LEAGUE_LOGO)
    return embed


@bot.tree.command(name="result", description="ADMIN ONLY: Submit match scores and update website standings & stats")
@app_commands.describe(
    team1="Select the first team role",
    score1="Goals scored by Team 1",
    team2="Select the second team role",
    score2="Goals scored by Team 2",
    team1_scorers="Mention scorers for Team 1 with names in parentheses: @Player (Name) @Player (Name)",
    team2_scorers="Mention scorers for Team 2 with names in parentheses: @Player (Name) @Player (Name)",
    team1_assists="Mention assists for Team 1 with names in parentheses: @Player (Name)",
    team2_assists="Mention assists for Team 2 with names in parentheses: @Player (Name)",
    cb_clean_sheets="Mention CB clean sheets with names in parentheses: @Player (Name)",
    gk_clean_sheets="Mention GK clean sheets with names in parentheses: @Player (Name)",
    possession="Possession stats (e.g. 'Team1 60% - 40% Team2')"
)
async def result(
    interaction: discord.Interaction,
    team1: discord.Role, score1: int,
    team2: discord.Role, score2: int,
    team1_scorers: str = "", team2_scorers: str = "",
    team1_assists: str = "", team2_assists: str = "",
    cb_clean_sheets: str = "", gk_clean_sheets: str = "",
    possession: str = ""
):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can record match results!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    data = load_data()

    for t in data["standings"]:
        if t["name"] == team1.name:
            t["mp"] += 1; t["gf"] += score1; t["ga"] += score2
            if score1 > score2: t["w"] += 1; t["pts"] += 3
            elif score1 == score2: t["pts"] += 1
            else: t["l"] += 1
        elif t["name"] == team2.name:
            t["mp"] += 1; t["gf"] += score2; t["ga"] += score1
            if score2 > score1: t["w"] += 1; t["pts"] += 3
            elif score1 == score2: t["pts"] += 1
            else: t["l"] += 1

    data["standings"].sort(key=lambda x: (x["pts"], x["gf"] - x["ga"]), reverse=True)

    # Extract (discord_id, name) pairs per team, already split by team from the command inputs
    team1_scorer_pairs = extract_player_pairs(team1_scorers)
    team2_scorer_pairs = extract_player_pairs(team2_scorers)
    team1_assist_pairs = extract_player_pairs(team1_assists)
    team2_assist_pairs = extract_player_pairs(team2_assists)

    # Clean sheets are entered by position (CB/GK); figure out which team each player
    # belongs to via the roster, falling back to the score if a name isn't found on either roster
    cb_pairs = [(pid, name, "CB") for pid, name in extract_player_pairs(cb_clean_sheets)]
    gk_pairs = [(pid, name, "GK") for pid, name in extract_player_pairs(gk_clean_sheets)]
    team1_cs_tagged, team2_cs_tagged = [], []
    for pid, name, pos in cb_pairs + gk_pairs:
        team_num = resolve_team_for_player(data, name, team1.name, team2.name)
        if team_num is None:
            if score2 == 0 and score1 != 0:
                team_num = 1
            elif score1 == 0 and score2 != 0:
                team_num = 2
            else:
                team_num = 1
        (team1_cs_tagged if team_num == 1 else team2_cs_tagged).append((pid, name, pos))

    # Update leaderboard / top_scorers / top_assists (matched by Discord ID, so a player's
    # numbers always keep updating instead of a new entry being created)
    all_scorer_pairs = team1_scorer_pairs + team2_scorer_pairs
    all_assist_pairs = team1_assist_pairs + team2_assist_pairs
    all_cs_pairs = [(pid, name) for pid, name, _ in team1_cs_tagged + team2_cs_tagged]
    update_leaderboard(data, all_scorer_pairs, all_assist_pairs, all_cs_pairs)

    # Save result for website Results page
    t1_info = next((i for i in data["standings"] if i["name"] == team1.name), {"abbr": team1.name[:3].upper(), "logo": KINGS_LEAGUE_LOGO})
    t2_info = next((i for i in data["standings"] if i["name"] == team2.name), {"abbr": team2.name[:3].upper(), "logo": KINGS_LEAGUE_LOGO})
    t1_abbr = t1_info.get("abbr", team1.name[:3].upper())
    t2_abbr = t2_info.get("abbr", team2.name[:3].upper())

    team1_scorer_names = [name for _, name in team1_scorer_pairs]
    team2_scorer_names = [name for _, name in team2_scorer_pairs]
    team1_assist_names = [name for _, name in team1_assist_pairs]
    team2_assist_names = [name for _, name in team2_assist_pairs]
    team1_cs_names = [f"{name} ({pos})" for _, name, pos in team1_cs_tagged]
    team2_cs_names = [f"{name} ({pos})" for _, name, pos in team2_cs_tagged]

    result_entry = {
        "header": f"{team1.name} vs {team2.name}",
        "t1_full": team1.name,
        "t2_full": team2.name,
        "t1_name": t1_abbr,
        "t1_logo": t1_info.get("logo", KINGS_LEAGUE_LOGO),
        "t2_name": t2_abbr,
        "t2_logo": t2_info.get("logo", KINGS_LEAGUE_LOGO),
        "score1": score1,
        "score2": score2,
        "team1_scorers": team1_scorer_names,
        "team2_scorers": team2_scorer_names,
        "team1_assists": team1_assist_names,
        "team2_assists": team2_assist_names,
        "team1_clean_sheets": team1_cs_names,
        "team2_clean_sheets": team2_cs_names,
        "possession": possession,
        "timestamp": datetime.now().strftime("%H:%M - %b %d")
    }
    if "results" not in data:
        data["results"] = []
    data["results"].insert(0, result_entry)

    # Mark the matching fixture as finished with the final score, so the fixtures list
    # on the website reflects it instead of staying stuck on "UPCOMING"
    for m in data.get("matches", []):
        if {m.get("t1_name"), m.get("t2_name")} == {t1_abbr, t2_abbr} and m.get("status") != "FINISHED":
            if m.get("t1_name") == t1_abbr:
                m["score1"], m["score2"] = score1, score2
            else:
                m["score1"], m["score2"] = score2, score1
            m["status"] = "FINISHED"
            break

    # Send embed to Discord results channel, grouped team-by-team
    res_chan = bot.get_channel(RESULT_CHANNEL_ID)
    embed = discord.Embed(title="⚽ MATCH RESULT", color=discord.Color.gold())
    embed.description = f"**{team1.name}**  `{score1} - {score2}`  **{team2.name}**"

    def team_field_lines(scorer_names, assist_names, cs_names):
        lines = []
        if scorer_names:
            lines.append("⚽ **Scorers:** " + ", ".join(scorer_names))
        if assist_names:
            lines.append("🅰️ **Assists:** " + ", ".join(assist_names))
        if cs_names:
            lines.append("🛡️ **Clean Sheets:** " + ", ".join(cs_names))
        return "\n".join(lines) if lines else "—"

    embed.add_field(name=f"🔵 {team1.name}", value=team_field_lines(team1_scorer_names, team1_assist_names, team1_cs_names), inline=False)
    embed.add_field(name=f"🔴 {team2.name}", value=team_field_lines(team2_scorer_names, team2_assist_names, team2_cs_names), inline=False)
    if possession:
        embed.add_field(name="Possession", value=possession, inline=False)
    embed.set_footer(text="Kings League VRFS • Official Result", icon_url=KINGS_LEAGUE_LOGO)
    if res_chan:
        await res_chan.send(embed=embed)

    save_data(data)
    update_github_data()

    # DM every player who scored or assisted with a professional congratulations message
    contributions = {}
    for pid, name in all_scorer_pairs:
        c = contributions.setdefault(pid, {"name": name, "goals": 0, "assists": 0})
        c["goals"] += 1
    for pid, name in all_assist_pairs:
        c = contributions.setdefault(pid, {"name": name, "goals": 0, "assists": 0})
        c["assists"] += 1

    dm_sent = 0
    for pid, stats in contributions.items():
        try:
            member = interaction.guild.get_member(int(pid)) if interaction.guild else None
            if member is None and interaction.guild:
                member = await interaction.guild.fetch_member(int(pid))
            if member:
                dm_embed = build_congrats_embed(stats["name"], stats["goals"], stats["assists"], team1.name, team2.name, score1, score2)
                await member.send(embed=dm_embed)
                dm_sent += 1
        except Exception as e:
            print(f"Could not DM player {pid} ({stats['name']}): {e}")

    await interaction.followup.send(f"✅ Result recorded, website updated, and {dm_sent} player DM(s) sent!", ephemeral=True)


@bot.tree.command(name="fixtures", description="ADMIN ONLY: Generate new match fixtures without repeating last round")
@app_commands.describe(
    team1="Select Team Role 1", team2="Select Team Role 2",
    team3="Select Team Role 3", team4="Select Team Role 4",
    team5="Select Team Role 5", team6="Select Team Role 6"
)
async def fixtures(interaction: discord.Interaction, team1: discord.Role, team2: discord.Role, team3: discord.Role, team4: discord.Role, team5: discord.Role, team6: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can generate fixtures!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    teams = [team1, team2, team3, team4, team5, team6]
    data = load_data()

    pairs = []
    for _ in range(20):
        shuffled = teams.copy()
        random.shuffle(shuffled)
        candidate = [(shuffled[0], shuffled[1]), (shuffled[2], shuffled[3]), (shuffled[4], shuffled[5])]
        last = data.get("last_fixtures", [])
        if not any({p1.name, p2.name} in [set(lp) for lp in last] for p1, p2 in candidate):
            pairs = candidate
            break
    if not pairs: pairs = candidate

    data["last_fixtures"] = [[p1.name, p2.name] for p1, p2 in pairs]

    web_matches = []
    embed = discord.Embed(title="KINGS LEAGUE FIXTURES", color=discord.Color.gold())
    embed.set_thumbnail(url=KINGS_LEAGUE_LOGO)

    for idx, (t1, t2) in enumerate(pairs, 1):
        t1_info = next((i for i in data["standings"] if i["name"] == t1.name), {"abbr": t1.name[:3].upper(), "logo": KINGS_LEAGUE_LOGO})
        t2_info = next((i for i in data["standings"] if i["name"] == t2.name), {"abbr": t2.name[:3].upper(), "logo": KINGS_LEAGUE_LOGO})

        embed.add_field(name=f"Match {idx}", value=f"**{t1.name}** VS **{t2.name}**", inline=False)
        web_matches.append({
            "header": f"Match {idx}", "t1_name": t1_info["abbr"], "t1_logo": t1_info["logo"],
            "t2_name": t2_info["abbr"], "t2_logo": t2_info["logo"], "status": "UPCOMING"
        })

    data["matches"] = web_matches

    save_data(data)
    update_github_data()

    fix_chan = bot.get_channel(FIXTURES_CHANNEL_ID)
    await fix_chan.send(embed=embed)
    await interaction.followup.send("✅ Fixtures generated and sent!", ephemeral=True)


@bot.tree.command(name="man_of_the_match", description="ADMIN ONLY: Set Man of the Match and display on the website")
@app_commands.describe(
    player="Select the player awarded Man of the Match",
    performance_reason="Write why they won (e.g., 'Scored 3 goals & 1 assist vs Barca')"
)
async def man_of_the_match(interaction: discord.Interaction, player: discord.Member, performance_reason: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can set Man of the Match!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    data = load_data()
    data["man_of_the_match"] = {"name": player.display_name, "avatar": player.display_avatar.url, "details": performance_reason}
    add_website_news(data, "MAN OF THE MATCH", f"{player.display_name} awarded Man of the Match! ({performance_reason})", "MOTM")
    
    save_data(data)
    update_github_data()
    
    await interaction.followup.send(f"🌟 Set Man of the Match to {player.mention}!", ephemeral=True)


@bot.tree.command(name="team_of_the_week", description="ADMIN ONLY: Update Team of the Week (5 lineup positions) on website")
@app_commands.describe(
    gk="Select Goalkeeper player",
    cb="Select Center Back player",
    cm="Select Central Midfielder player",
    lst="Select Left Striker player",
    rst="Select Right Striker player"
)
async def team_of_the_week(interaction: discord.Interaction, gk: discord.Member, cb: discord.Member, cm: discord.Member, lst: discord.Member, rst: discord.Member):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can set Team of the Week!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    data = load_data()
    data["team_of_the_week"] = {
        "GK": gk.display_name, "CB": cb.display_name, "CM": cm.display_name, "LST": lst.display_name, "RST": rst.display_name
    }
    add_website_news(data, "TEAM OF THE WEEK", "The official Team of the Week lineup has been updated!", "TOTW")
    
    save_data(data)
    update_github_data()
    
    await interaction.followup.send("⭐️ Team of the Week updated on website!", ephemeral=True)


@bot.tree.command(name="set_team_logo", description="ADMIN ONLY: Upload/replace a team's logo (fixes expired/broken logos)")
@app_commands.describe(team="Select the team role", logo="Upload the new logo image file")
async def set_team_logo(interaction: discord.Interaction, team: discord.Role, logo: discord.Attachment):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can update team logos!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if not (logo.content_type and logo.content_type.startswith("image/")):
        await interaction.followup.send("❌ Please upload a valid image file.", ephemeral=True)
        return

    data = load_data()
    team_info = next((t for t in data["standings"] if t["name"] == team.name), None)
    if not team_info:
        await interaction.followup.send(f"❌ No team found matching role **{team.name}**.", ephemeral=True)
        return

    ext = logo.filename.rsplit('.', 1)[-1].lower() if '.' in logo.filename else 'png'
    logo_bytes = await logo.read()
    hosted_url = upload_image_to_github(logo_bytes, f"{team_info.get('abbr', team.name[:3]).lower()}_{team.id}.{ext}")

    if not hosted_url:
        await interaction.followup.send("❌ Failed to upload the logo. Please try again in a moment.", ephemeral=True)
        return

    team_info["logo"] = hosted_url
    # Keep matches/fixtures in sync too, since they store their own copy of each team's logo
    for m in data.get("matches", []):
        if m.get("t1_name") == team_info.get("abbr"):
            m["t1_logo"] = hosted_url
        if m.get("t2_name") == team_info.get("abbr"):
            m["t2_logo"] = hosted_url

    save_data(data)
    update_github_data()
    await update_roster_channel_message(team.name, hosted_url, data)

    await interaction.followup.send(f"✅ Logo updated for **{team.name}**! It's now permanently hosted and won't expire again.", ephemeral=True)


@bot.tree.command(name="restart", description="ADMIN ONLY: Reset all league data and website records")
async def restart(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can reset league data!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    save_data({
        "standings": [], "news": [], "matches": [], "rosters": {},
        "roster_messages": {},
        "last_fixtures": [], "top_scorers": {}, "top_assists": {},
        "man_of_the_match": None,
        "team_of_the_week": {"GK": "N/A", "CB": "N/A", "CM": "N/A", "LST": "N/A", "RST": "N/A"},
        "results": [],
        "leaderboard": []
    })
    
    update_github_data()
    
    await interaction.followup.send("🔄 Data completely reset!", ephemeral=True)

bot.run(TOKEN)
