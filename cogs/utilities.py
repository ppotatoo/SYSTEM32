import discord
from discord.ext import commands
import datetime
from utils.default import qembed
import humanize
import json
import random
import string
from utils.permissions import mng_msg


class DeletedMessage:
    __slots__ = ('author', 'content', 'channel', 'guild', 'created_at', 'deleted_at', 'del_embed', 'attachment')

    def __init__(self, message):
        self.author = message.author
        self.content = message.content
        self.guild = message.guild
        self.created_at = message.created_at
        self.deleted_at = datetime.datetime.utcnow()
        if message.embeds:
            self.del_embed = message.embeds[0]
        if message.attachments:
            self.attachment = message.attachments[0].proxy_url
        else:
            self.attachment = None
            

class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def deleted_message_for(self, index: int, channel_id: int):
        try:
            if index > len(self.bot.deleted_messages[channel_id]):
                return None
        except KeyError:
            return None

        if len(self.bot.deleted_messages[channel_id]) > 500:
            dele = len(self.bot.deleted_messages[channel_id]) - 500
            for number in range(dele):
                del self.bot.deleted_messages[channel_id][number]


        readable_order = list(reversed(self.bot.deleted_messages[channel_id]))
        try:
            result = readable_order[index]
        except KeyError:
            return None
        else:
            return result

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        b = [479359598730674186]
        if message.author.id in b:
            return
        self.bot.deleted_messages[message.channel.id].append(DeletedMessage(message))


    @commands.guild_only()
    @commands.is_owner()
    @commands.command(help='Views up to the last 500 deleted messages')
    async def snipe(self, ctx, index: int = 1, channel: discord.TextChannel = None):
        if channel and channel.is_nsfw():
            return await qembed(ctx, 'no sorry')
        if not channel:
            channel = ctx.channel
        try:
            msg = self.deleted_message_for(index - 1, channel.id)
            try:
                await ctx.send(embed=msg.del_embed)
                content = 'Bot deleted an embed which was sent above.' if not msg.content else msg.content
            except AttributeError:
                content = msg.content
        except IndexError:
            return await qembed(ctx, 'Nothing to snipe!')
        snipe = discord.Embed(title='Content:', description=content, color=self.bot.embed_color,
                              timestamp=ctx.message.created_at)
        if msg.attachment:
            snipe.add_field(name='Attachment', value=msg.attachment, inline=False)
        snipe.add_field(name='Message Stats:', value=
                            f"**Created At:** {humanize.naturaldelta(msg.created_at - datetime.datetime.utcnow())} ago\n"
                            f"**Deleted At:** {humanize.naturaldelta(msg.deleted_at - datetime.datetime.utcnow())} ago\n"
                            f"**Index:** {index} / {len(self.bot.deleted_messages[channel.id])}", inline=False)
        snipe.set_author(name=f'{str(msg.author)} said in #{channel.name}:', icon_url=str(msg.author.avatar_url))
        snipe.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=snipe)
        
    @commands.command(help='Posts text to https://mystb.in', aliases=['paste'])
    async def mystbin(self, ctx, *, text=None):
        if ctx.message.reference:
            if ctx.message.reference.cached_message:
                if (
                    ctx.message.reference.cached_message.attachments
                    and ctx.message.reference.cached_message.attachments[
                        0
                    ].filename.endswith((".txt", ".py", ".json", ".html", ".csv"))
                ):
                    message = await ctx.message.reference.cached_message.attachments[0].read()
                    message = message.decode("utf-8")
                    return await qembed(ctx, await ctx.mystbin(message) + "." + ctx.message.reference.cached_message.attachments[0].filename.split(".")[1])
            else:
                message = await self.bot.get_channel(ctx.message.reference.channel_id).fetch_message(ctx.message.reference.message_id)
                if message.attachments and message.attachments.filename.endswith(
                    (".txt", ".py", ".json", ".html", ".csv")
                ):
                    message_ = await message.attachments[0].read()
                    message_ = message_.decode("utf-8")
                    return await qembed(ctx, await ctx.mystbin(message_) + "." + message.attachments[0].filename.split(".")[1])

        if text is None:
            message = ctx.message.attachments[0]
            if message:
                syntax = message.filename.split(".")[1]
                if message.filename.endswith((".txt", ".py", ".json", ".html", ".csv")):
                    message = await message.read()
                    message = message.decode("utf-8")
                    return await qembed(ctx, await ctx.mystbin(message) + "." + syntax)

        await qembed(ctx, await ctx.mystbin(text))
        
    # from pb https://github.com/PB4162/PB-Bot
    @commands.command(aliases=["rawmessage", "rawmsg"])
    async def raw_message(self, ctx, *, message: discord.Message = None):
        """
        Get the raw info for a message.
        `message` - The message.
        """
        if ctx.message.reference:
            message = ctx.message.reference
            message = await ctx.fetch_message(message.message_id)
            
        message = message or ctx.message

        try:
            msg = await self.bot.http.get_message(ctx.channel.id, message.id)
        except discord.NotFound:
            return await qembed(ctx, "Sorry, I couldn't find that message.")

        raw = json.dumps(msg, indent=4)
        if len(raw) > 1989:
            return await qembed(ctx, 'Sorry, the message was too long')
        await qembed(ctx, f"```json\n{raw}```")

    @commands.command(help='Randomly generates a password')
    async def password(self, ctx, length=16):
        lower = string.ascii_lowercase
        upper = string.ascii_uppercase
        num = string.digits
        symbols = string.punctuation

        all = lower + upper + num + symbols

        temp = random.sample(all,length)

        password = "".join(temp)
        embed = discord.Embed(description=f'{length} digit random password: `{password.replace("`", random.choice(num))}`', color=self.bot.embed_color, timestamp=ctx.message.created_at)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar_url)
        await ctx.author.send(embed=embed)
        await qembed(ctx, f'Messaged you with the password, {ctx.author.mention}')

def setup(bot):
    bot.add_cog(Utilities(bot))
