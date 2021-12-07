from logging import root
import os
import shutil
import tarfile
from pathlib import Path
from time import sleep
from datetime import datetime
from pathlib import Path
from .manager import Manager

class BackupManager:

    def __init__(self, server_path, backup_path, excluded_files=None, excluded_file_types=None,
                 max_backups=10, cwd=None, manager=None):
        self.server_path = server_path
        self.backup_path = backup_path
        self.excluded_files = excluded_files or []
        self.excluded_file_types = excluded_file_types or []
        self.max_backups = max_backups if isinstance(max_backups, int) else int(max_backups)
        self.manager = manager

        if self.server_path.endswith('.jar'):
            self.server_path = Path(self.server_path).parent.absolute()

        self.excluded_files = [item for item in self.excluded_files if item]
        self.excluded_file_types = [item.replace('*', '') for item in self.excluded_file_types if item]
        self.excluded_file_types = [
            item if item.startswith('.') else '.{}'.format(item) for item in self.excluded_file_types if item]

        if not self.backup_path.endswith('/'):
            self.backup_path += '/'
        if self.backup_path.startswith('./'):
            self.backup_path = os.path.join(cwd or os.getcwd(), self.backup_path[2:])
        if not self.backup_path.startswith('/'):
            self.backup_path = os.path.join(cwd or os.getcwd(), self.backup_path)

        self.create_backup_directory()

        # Cache the server file names
        self.server_files = self.get_server_files()

    def create_backup_directory(self):
        exists = os.path.exists(self.backup_path)
        is_dir = os.path.isdir(self.backup_path)
        if exists and is_dir:
            return

        if (exists and not is_dir) or not exists:
            os.mkdir(self.backup_path)

    def take_snapshot(self):
        # Make sure our directory exists
        self.create_backup_directory()

        # Cache the server file names
        self.cache_server_filenames()

        # If we have maxed out our backups, delete some, starting from the oldest
        self.delete_old_backups()

        # Copy JAR files to it
        self.server_files = self.get_server_files()
        for i in self.server_files:
            shutil.copyfile(i, os.path.join(self.backup_path, Path(i).name))

        # Make the compressed backup
        self.manager.log('Taking snapshot of Minecraft Server...')
        save_path = os.path.join(self.backup_path, self.get_filename())
        self.make_tarfile(save_path, self.server_path)

        # Wait 1 second just to make sure the tar is fully written
        sleep(1)

        # Check to make sure the file exists
        if not os.path.exists(save_path):
            self.manager.log("Failed to create snapshot! File not found!")
            return None

        # If it's successful, get the file and log
        size = os.path.getsize(save_path)
        self.manager.log('Successfully took snapshot of the Minecraft Server: {} bytes'.format(size))
        return save_path

    async def restore_last_snapshot(self, save_current=False):
        # Make sure we have at least one backup
        latest = self.get_most_recent_backup()
        if not latest:
            self.manager.log('Please take a snapshot before trying to restore to one...', level='warn')
            return

        # Get the server JAR files
        server_dir = self.manager.get_jar_dir()
        self.server_files = self.get_server_files()

        # If we want to save our current state
        if save_current:
            await self.manager.command_handler('backup-now')

        # Stop the server
        await self.manager.stop_server()

        # Delete the old server files
        if os.path.exists(server_dir):
            shutil.rmtree(server_dir)

        # Re-make the directory
        if not os.path.exists(server_dir):
            os.mkdir(server_dir)

        # Unzip the latest snapshot
        latest_unzipped = latest.replace('.tar.gz', '')
        with tarfile.open(latest, "r:gz") as tar:
            tar.extractall(latest_unzipped)

        # Copy latest snapshot to the directory
        shutil.copytree(
            os.path.join(latest_unzipped, Path(server_dir).name), server_dir, dirs_exist_ok=True)

        # Copy the server JARs back over
        for i in self.server_files:
            shutil.copyfile(os.path.join(self.backup_path, Path(i).name), i)

        # Cleanup the unzipped files
        shutil.rmtree(latest_unzipped)

    def _file_filter(self, tarinfo):
        # Skip over excluded files
        if tarinfo.name in self.excluded_files:
            return None

        # Skip over cache files. These will be redownloaded
        if '/cache/' in tarinfo.name:
            return None

        # Skip over server JARs
        skip_files = [Path(i).name for i in (self.server_files or [])]
        if Path(tarinfo.name).name in skip_files:
            return None

        # Skip over specific file types
        if any(tarinfo.name.endswith(i) for i in self.excluded_file_types):
            return None

        return tarinfo

    def make_tarfile(self, output_filename, source_dir):
        with tarfile.open(output_filename, "w:gz") as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir), filter=self._file_filter)

    def delete_old_backups(self):
        backup_count = self.get_backup_count()
        old_backups = 0 if (
                backup_count == self.max_backups or backup_count < self.max_backups
            ) else backup_count - self.max_backups
        success = 0

        if old_backups == 0:
            return

        self.manager.log('Deleting {} old backups...'.format(old_backups))
        for _ in range(old_backups):
            oldest = self.get_oldest_backup()

            try:
                os.unlink(oldest)
                success += 1
            except:
                pass

        self.manager.log('Successfully deleted {} old backups...'.format(success))

    def get_backup_count(self):
        count = 0
        for entry in os.scandir(self.backup_path):
            # Skip over any non-backup files
            if not self.is_backup_file(entry):
                continue

            # Pull out the timestamp
            ts = self.get_timestamp_from_file(entry.name)
            if ts is None:
                continue

            count += 1

        return count

    def get_oldest_backup(self):
        oldest = self.current_time()
        oldest_backup = None
        for entry in os.scandir(self.backup_path):
            # Skip over any non-backup files
            if not self.is_backup_file(entry):
                continue

            # Pull out the timestamp
            ts = self.get_timestamp_from_file(entry.name)
            if ts is None:
                continue

            if ts < oldest:
                oldest = ts
                oldest_backup = entry.path

        return oldest_backup

    def get_server_files(self, root_path=None):
        server_files = []
        for entry in os.scandir(root_path or self.manager.get_jar_dir()):
            # Skip over any non-server files
            if not entry.name.endswith('.jar'):
                continue

            server_files.append(entry.path)

        return server_files

    def get_most_recent_backup(self):
        newest = 0
        newest_backup = None
        for entry in os.scandir(self.backup_path):
            # Skip over any non-backup files
            if not self.is_backup_file(entry):
                continue

            # Pull out the timestamp
            ts = self.get_timestamp_from_file(entry.name)
            if ts is None:
                continue

            if ts > newest:
                newest = ts
                newest_backup = entry.path

        return newest_backup

    def get_timestamp_from_file(self, filename):
        parts = filename.replace('.tar.gz', '').split('-')
        ts = parts[2]

        try:
            return int(ts)
        except:
            return None

    def cache_server_filenames(self):
        server_files = self.get_server_files()
        self.server_files = [Path(i).name for i in server_files]

    def is_backup_file(self, file_item):
        return (
            file_item.name.startswith('minecraft-backup-') and
            file_item.name.endswith('.tar.gz') and
            file_item.is_file()
        )

    def get_filename(self):
        return 'minecraft-backup-{}.tar.gz'.format(self.current_time())

    def current_time(self):
        return int(datetime.utcnow().timestamp())