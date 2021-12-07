from discord.ext import commands

client = commands.Bot(command_prefix='!server ')

ops = ['zach#3244', 'gigawhattt#1102', 'rockncole#2771']

class DiscordManager:

    def __init__(self, api_token, manager):
        self.token = api_token
        self.manager = manager

    def get_client(self):
        return client

    def start(self):
        self.run_client()

    async def stop(self):
        if client:
            await client.close()

    def run_client(self):
        @client.event
        async def on_ready():
            self.manager.log('Discord bot client is ready')

        @client.command(name='ping')
        async def ping(ctx):
            await ctx.send('Bing Bong')
            
        @client.command(name='start')
        async def start_cmd(ctx):
            await ctx.send('I\'m starting up the Minecraft server now...')
            ret = await self.command_handler(ctx, 'start')
            if ret:
                await ctx.send('I\'ve successfully started the Minecraft Server for you')

        @client.command(name='stop')
        async def stop_cmd(ctx):
            await ctx.send('Alright, shutting down the Minecraft Server...')
            ret = await self.command_handler(ctx, 'stop')
            if ret:
                await ctx.send('I\'ve successfully shut down the Minecraft Server for you')

        @client.command(name='restart')
        async def restart_cmd(ctx):
            await ctx.send('Nothin\' liked a good ole switch off and on!')
            ret = await self.command_handler(ctx, 'stop')
            if ret:
                await ctx.send('I\'ve successfully restarted the Minecraft Server for you')

        @client.command(name='backup')
        async def backup_cmd(ctx):
            await ctx.send('Be right back, taking a snapshot of your Minecraft Server...')
            ret = await self.command_handler(ctx, 'backup-now')
            if ret:
                await ctx.send('I\'ve successfully taken a new backup of your Minecraft Server')

        @client.command(name='restore')
        async def restore_cmd(ctx):
            await ctx.send('Restore coming right up! I\'m reverting back to last the snapshot...')
            ret = await self.command_handler(ctx, 'restore')
            if ret:
                await ctx.send('I\'ve successfully reverted to the last backup of your Minecraft Server')

        @client.event
        async def on_message(message):
            # Do not remove this
            await client.process_commands(message)
        
        client.run(self.token)

    async def command_handler(self, ctx, command):
        user_id = '{}#{}'.format(ctx.author.name, ctx.author.discriminator)
        ret = False
        if user_id not in ops:
            await ctx.send('Woah there! Only admins can execute that command. You\'re just a filthy peasant!')
            return ret

        try:
            await self.manager.command_handler(command)
            ret = True
        except Exception as ex:
            await ctx.send('Wahhh! I run into a boo boo: {}'.format(
                ex.message if hasattr(ex, 'message') else str(ex)))

        return ret
