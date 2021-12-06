
import asyncio
import atexit
import click
from .manager import MinecraftManager

manager: MinecraftManager = None

def close_process():
    if manager:
        manager.log('Force close or crash detected! Cleaning up child processes...', level='warn')
        asyncio.run(manager.stop_server(quit=True))


@click.command()
@click.option('--server-path', type=click.Path(exists=True), help='The path to your minecraft server executable (jar)')
@click.option('--log-path', type=click.Path(exists=False), help='The path for your default log file')
@click.option('--backup-dir', type=click.Path(exists=True), help='The directory you want backups saved in')
@click.option('--excluded-files', type=str, help='Comma-separated list of files to exclude')
@click.option('--excluded-file-types', type=str, help='Comma-separated list of file types to exclude')
@click.option('--backup-frequency', type=int, help='A number representing how often you want backups to run (in seconds)')
@click.option('--min-java-memory', type=str, help='The minimum amount of memory that the JVM should use')
@click.option('--max-java-memory', type=str, help='The maximum amount of memory that the JVM can use')
@click.option('--discord-api-token', type=str, help='Discord Bot API Token')
def execute_command(server_path, log_path, backup_dir, excluded_files, excluded_file_types,
                   backup_frequency, min_java_memory, max_java_memory, discord_api_token):
    """
    Handler for the execute command
    """

    global manager
    manager = MinecraftManager(server_path, **{
        'log_path': log_path,
        'backup_dir': backup_dir,
        'excluded_files': (excluded_files or '').split(','),
        'excluded_file_types': (excluded_file_types or '').split(','),
        'backup_frequency': backup_frequency,
        'min_java_memory': min_java_memory,
        'max_java_memory': max_java_memory,
        'discord_api_token': discord_api_token
    })

    # Register a handler for when the process is exited
    atexit.register(close_process)

    # Start the manager
    manager.start()


def execute():
   execute_command()
