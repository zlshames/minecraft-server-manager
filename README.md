# Minecraft Server Manager

## Usage

Using the manager is as simple as installing it, then running it with the configurable parameters

### Installation

```bash
git clone git@github.com:zlshames/minecraft-server-manager.git
cd minecraft-server-manager
pip install -e ./
```

### Running the App

By default, there is only 1 required parameter, `server-path`. This tells the manager where your Minecraft Server JAR file is, so that it can run and manage it.

```bash
beachboys-minecraft-manager \
    --server-path="/path/to/your/server/paper-1.17.1-251.jar"
```

#### CLI Parameters

There are a handful of other CLI paramters that you can specify to determine how the manager will run

* **log-path**: The path for your default log file (Default: `./minecraft-manager.log`)
* **backup-dir**: The directory you want backups saved in (Default: `./backups/`)
* **excluded-files**: Comma-separated list of files to exclude
* **excluded-file-types**: Comma-separated list of file types to exclude
* **backup-frequency**: A number representing how often you want backups to run, in seconds (Default: 6 hours)
* **min-java-memory**: The minimum amount of memory that the JVM should use
* **max-java-memory**: The maximum amount of memory that the JVM can use
* **discord-api-token**: Discord Bot API Token

### Interaction

In order to interact with the server while it's running, you can either type commands into the process' standard input (i.e. just type a command and hit enter), or, if you have a Discord bot setup with app, you can run commands from your Discord server. The manager provides specific commands that are handled, and any unrecognized commands will be forwarded to the running Minecraft Server. For instance, you can run `save-on` to enable auto-saves for your Minecraft Server (this is not one manually handled by the manager)

**Available Commands**:

* stop, quit
* start
* restart
* quit
* backup, backup-now
* cancel-backup-timer, cancel-backup, cancel-backup-schedule
* start-backup
* restore
* restore-last
* help

#### Discord

If you are controlling the manager from Discord (via a bot), simply prefix your commands with, `!server`. For instance, `!server ping`