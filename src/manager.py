import asyncio
import os
import subprocess
from datetime import datetime
from threading import Timer
import logging
from logging import handlers
from pathlib import Path
import sys
import traceback
from threading import Thread
from .utils import get_with_default
from .backup import BackupManager
from .discord import DiscordManager


class ManagerState:
    INACTIVE = 0
    RUNNING = 1
    STOPPING = 2
    QUITING = 3


class MinecraftManager:

    required_fields = [
        'server_path', 'log_path', 'backup_dir', 'backup_frequency',
        'min_java_memory', 'max_java_memory'
    ]

    def __init__(self, server_path, **kwargs):
        self.state = ManagerState.INACTIVE
        self.current_dir = os.getcwd()
        self.server_path = server_path
        self.log_path = get_with_default(kwargs, 'log_path', default='./minecraft-manager.log')
        self.backup_dir = get_with_default(kwargs, 'backup_dir', default='./backups')
        self.excluded_files = get_with_default(kwargs, 'excluded_files', default='')
        self.excluded_file_types = get_with_default(kwargs, 'excluded_file_types', default='')
        self.backup_frequency = get_with_default(kwargs, 'backup_frequency', default=21600)  # 6 Hours (in seconds)
        # self.backup_frequency = get_with_default(kwargs, 'backup_frequency', default=5)  # 6 Hours (in seconds)
        self.min_java_memory = get_with_default(kwargs, 'min_java_memory', default='2G')
        self.max_java_memory = get_with_default(kwargs, 'max_java_memory', default='2G')
        self.discord_api_token = kwargs.get('discord_api_token')
        self.process = None
        self.discord = None

        self.validate_config()
        self.configure_logging()

    def validate_config(self):
        for key in self.required_fields:
            if hasattr(self, key) and not getattr(self, key):
                raise ValueError('Required parameter, `{}` does not have a value set!'.format(key))

        try:
            if isinstance(self.backup_frequency, str):
                self.backup_frequency = int(self.backup_frequency)
        except:
            raise ValueError('Parameter, `backup_frequency` is not a valid integer!')

    def configure_logging(self):
        # Max size is 100 MB
        file_handler = handlers.RotatingFileHandler(self.log_path, maxBytes=104857600, backupCount=5)
        stdout_handler = logging.StreamHandler(sys.stdout)
        handler_list = [file_handler, stdout_handler]

        logging.basicConfig(
            level=logging.DEBUG, 
            format='[%(asctime)s] [%(levelname)s]: %(message)s',
            handlers=handler_list
        )

        self.logger = logging.getLogger('minecraft-manager')

    def log(self, msg, level='info', with_traceback=False):
        if not self.logger:
            print('[{}] {}'.format(level, msg))
            if with_traceback:
                print('[{}] {}'.format(level, traceback.format_exc()))
        else:
            if hasattr(self.logger, level):
                getattr(self.logger, level)(msg)
            if with_traceback:
                self.logger.debug(traceback.format_exc())

    def start(self):
        self.log('Starting Minecraft Manager...')
        self.log('Type `help` for a list of commands')
        self.log(' -> Using server executable: {}'.format(self.server_path), level='debug')
        self.log(' -> Backing up every {} minutes to {}'.format(
            self.backup_frequency / 60, self.backup_dir), level='debug')
        self.log(' -> Excluding files: {}'.format(', '.join(self.excluded_files)), level='debug')
        self.log(' -> Excluding file types: {}'.format(', '.join(self.excluded_file_types)), level='debug')
        self.log(' -> Logging to file: {}'.format(self.log_path), level='debug')

        # Listen for commands to the stdin of the parent process
        self.read_thread = Thread(target=self.run_async_thread, args=(self.listen_for_stdin,))
        self.read_thread.start()

        # Start the server
        self.start_server()

        # Start the backup timer
        self.start_backup_timer()

        # Start Discord Bot
        if self.discord_api_token:
            self.discord = DiscordManager(self.discord_api_token, self)
            self.discord.start()

    def run_async_thread(self, func):
        asyncio.run(func())

    def start_server(self):
        self.log('Starting Minecraft Server...')

        # "CD" into the server directory
        os.chdir(self.get_jar_dir())

        # Start the process
        self.process = subprocess.Popen(
            self.get_command_parts(), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.state = ManagerState.RUNNING

        # Listen for commands to the stdout of the child process
        self.listen_thread = Thread(target=self.run_async_thread, args=(self.listen_for_stdout,))
        self.listen_thread.start()

    def start_backup_timer(self, force=False):
        if hasattr(self, 'backup_timer') and self.backup_timer and self.backup_timer.is_alive:
            if not force:
                self.log('Backup timer already in progress. Not creating a new one...')
                return

            self.log('Backup timer already in progress. Canceling it...')
            self.backup_timer.cancel()

        try:
            self.backup_timer = Timer(self.backup_frequency, self.perform_backup) # FIND NEXT HOURLY MARK
            self.backup_timer.start()

            next_time = datetime.timestamp(datetime.utcnow()) + self.backup_frequency
            next_time = datetime.fromtimestamp(next_time)
            logging.info('Backup timer started. Next backup at: {}'.format(
                next_time.now().strftime('%Y-%m-%d %H:%M:%S')))
        except Exception as ex:
            self.log('Failed to start backup timer! Error: {}'.format(
                ex.message if hasattr(ex, 'message') else str(ex)))

    async def command_handler(self, command):
        if not command:
            return

        self.log('Handling Command: "{}"'.format(command), level='debug')
        sani_cmd = command.lower().strip().replace('_', '-').replace(' ', '-')
        if sani_cmd.lower() in ['stop', 'quit']:
            self.run_server_command('stop')
            self.process.wait()
            self.state = ManagerState.INACTIVE
            self.log('Stopped Minecraft Server...')
        elif sani_cmd.lower() in ['start']:
            if self.process and self.state != ManagerState.INACTIVE:
                self.log('Minecraft server is already running! Not starting it again...')
                return

            self.start_server()
        elif sani_cmd.lower() in ['restart']:
            if self.process and self.state == ManagerState.RUNNING:
                await self.command_handler('stop')
            self.start_server()
        elif sani_cmd.lower() in ['quit', 'exit']:
            if self.process and self.state == ManagerState.RUNNING:
                await self.command_handler('stop')
            self.log('Quiting Minecraft Manager...')
            await self.stop_server(quit=True)
        elif sani_cmd.lower() in ['backup', 'backup-now']:
            self.stop_backup()
            self.perform_backup(start_next_timer=False)
        elif sani_cmd.lower() in ['cancel-backup-timer', 'cancel-backup', 'cancel-backup-schedule']:
            self.stop_backup()
        elif sani_cmd.lower() in ['start-backup', 'start-backup-timer']:
            self.start_backup_timer()
        elif sani_cmd.lower() in ['restore', 'restore-last']:
            await self.perform_restore_last_snapshot()
        elif sani_cmd.lower() in ['help']:
            self.display_help()
        else:
            # If no cases match, forward it to the server
            self.run_server_command(command)

    async def listen_for_stdout(self):
        if not self.process:
            return

        self.log('Listening for Minecraft server outputs...', level='debug')

        ret_code = None
        for stdout_line in iter(self.process.stdout.readline, ""):
            line = stdout_line.decode('utf-8').rstrip()
            if line:
                self.log(line, level='debug')
            elif self.process.returncode is not None:
                # If the process has returned, stop listening
                ret_code = self.process.returncode
                break
            
            if (self.state != ManagerState.RUNNING):
                ret_code = -1
                break

            if not self.process or not self.process.stdout or self.process.stdout.closed:
                ret_code = 0
                break

        self.log('Stopped listening for Minecraft server outputs...', level='debug')
        
        if ret_code in [None, -1]:
            self.log('Waiting for Minecraft server to close...', level='debug')

            try:
                ret_code = self.process.wait()
            except:
                pass

            self.log('Minecraft server closed', level='debug')

        await self.stop_server()
        if ret_code and ret_code != 130:  # 130 is SIGKILL/SIGTERM
            self.log('Subprocess error detected! Code: {}; Command: {}'.format(ret_code, self.get_run_command()))

        self.listen_thread = None

    async def listen_for_stdin(self):
        self.log('Listening for input commands...', level='debug')

        for line in iter(sys.stdin.readline, ""):   
            if self.state == ManagerState.QUITING or not sys.stdin or sys.stdin.closed:
                break
            if line:
                await self.command_handler(line.rstrip())

        self.log('Stopped listening for input commands', level='debug')

    async def stop_server(self, quit=False, exit_code=0):
        self.state = ManagerState.QUITING if quit else ManagerState.STOPPING

        if self.process and self.process.returncode is None:
            await self.command_handler("stop")
        elif self.process:
            try:
                self.process.stdout.close()
                self.process.stdin.close()
                self.process.kill()
                self.process.terminate()
            except:
                pass

        try:
            if self.listen_thread and self.listen_thread.is_alive:
                self.listen_thread.join()
        except:
            pass

        if quit:
            self.log('Quitting...')

            if self.discord:
                await self.discord.stop()

            sys.exit(exit_code)
        else:
            self.state = ManagerState.INACTIVE

    def stop_backup(self):
        self.log('Cancelling backup timer...', level='debug')
        if self.backup_timer and self.backup_timer.is_alive:
            self.backup_timer.cancel()
        
        self.backup_timer = None

    def run_server_command(self, cmd):
        if not self.process or not self.process.stdin or self.process.stdin.closed:
            self.log("Can't send command to Minecraft server. Server is not running!")
            return

        self.log('Executing Server Command, "{}"'.format(cmd), level='debug')

        try:
            self.process.stdin.write(str.encode('{}\n'.format(cmd)))
            self.process.stdin.flush()
        except Exception as ex:
            self.log('Failed to execute server command! Error: {}'.format(str(ex)), level='error')

    def send_server_message(self, message):
        self.run_server_command('say {}'.format(message))

    def perform_backup(self, start_next_timer=True):
        self.log('Performing backup...')
        self.run_server_command("say Performing backup...")
        self.run_server_command("save-off")
        self.run_server_command("save-all")

        backup = BackupManager(
            self.server_path,
            self.backup_dir,
            excluded_files=self.excluded_files,
            excluded_file_types=self.excluded_file_types,
            manager=self,
            cwd=self.current_dir
        )
        file_path = backup.take_snapshot()
        if file_path:
            self.log('Successfully created new backup at: {}'.format(file_path))
        else:
            self.log('Failed to take backup!', level='error')

        if self.state not in [ManagerState.STOPPING, ManagerState.QUITING]:
            self.run_server_command("save-on")
            self.run_server_command("say Backup Complete!")

        # Start the next backup timer
        if self.state != ManagerState.QUITING and start_next_timer:
            self.start_backup_timer()

    async def perform_restore_last_snapshot(self):
        self.log('Performing restore of last backup...')

        if self.minecraft_running():
            self.run_server_command("say Performing restore...")
            await self.command_handler('stop')

        backup = BackupManager(
            self.server_path,
            self.backup_dir,
            excluded_files=self.excluded_files,
            excluded_file_types=self.excluded_file_types,
            manager=self,
            cwd=self.current_dir
        )

        await backup.restore_last_snapshot()
        self.log('Restore Successful! Starting Minecraft Server...')
        await self.command_handler('start')

    def display_help(self):
        parts = [
            '[========== Help ========== ]',
            '',
            'Hint: Type one of the following commands and hit enter. Comma-separated commands mean you can use either',
            '',
            'Commands:',
            '- stop                       -> Stop the Minecraft Server',
            '- start                      -> Start the Minecraft Server',
            '- restart                    -> Restart the Minecraft Server',
            '- quit, exit                 -> Stop the server and quit the application',
            '- backup, backup-now         -> Take a backup of the Minecraft Server',
            '- cancel-backup, stop-backup -> Cancel and Stop the backup scheduler',
            '- start-backup               -> Start the backup scheduler'
        ]

        for i in parts:
            self.log(i)

    def minecraft_running(self):
        return self.state == ManagerState.RUNNING and self.process and self.process.returncode is None

    def get_jar_dir(self):
        return Path(self.server_path).parent.absolute()

    def get_command_parts(self):
        return ['java', '-Xms2G', '-Xmx2G', '-jar', self.server_path, '--nogui']

    def get_run_command(self):
        return ' '.join(self.get_command_parts())
