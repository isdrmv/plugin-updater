"""This script allows you to automatically download/update Minecraft plugins.

Working principle: overwrite plugin files if necessary. Working with
spigotmc.org, Jenkins sites, github.com and others (via direct URLs).
However, the script is far from perfect :)

Author: Denis Romanov (https://github.com/isdrmv).
"""

from typing import Dict
import json
import logging
import os
import sys

import requests

LOG_FILE = 'plugin_updater.log'
VERSION_FILE = 'plugin_versions.json'
PLUGIN_DIR = 'plugins'

# Spigot:
# 'project_url': 'file_name_with_extension'
# Jenkins or GitHub:
# 'project_url': {file_index_starts_from_zero: 'file_name_with_extension', ...}
# Other:
# 'direct_url': 'file_name_with_extension'
# pylint: disable=line-too-long
PLUGINS = {
    'https://www.spigotmc.org/resources/ath-peak-players-record-spigot-and-bungeecord-support.87124': 'Ath.jar',
    'https://www.spigotmc.org/resources/chatty-lightweight-universal-bukkit-chat-system-solution-1-7-10-1-19.59411': 'Chatty.jar',
    'https://www.spigotmc.org/resources/chunky.81534': 'Chunky.jar',
    'https://www.spigotmc.org/resources/gsit-modern-sit-seat-and-chair-lay-and-crawl-plugin-1-13-x-1-19-x.62325': 'GSit.jar',
    'https://www.spigotmc.org/resources/luckperms.28140': 'LuckPerms.jar',
    'https://www.spigotmc.org/resources/mycommand.22272': 'MyCommand.jar',
    'https://www.spigotmc.org/resources/placeholderapi.6245': 'PlaceholderAPI.jar',
    'https://www.spigotmc.org/resources/skinsrestorer.2124': 'SkinsRestorer.jar',
    'https://www.spigotmc.org/resources/spark.57242': 'spark.jar',
    'https://www.spigotmc.org/resources/vault.34315': 'Vault.jar',
    'https://ci.codemc.io/job/AuthMe/job/AuthMeReloaded': {3: 'AuthMe.jar'},
    'https://ci.ender.zone/job/EssentialsX': {0: 'EssentialsX.jar', 7: 'EssentialsXSpawn.jar'},
    'https://ci.athion.net/job/FastAsyncWorldEdit': {0: 'FastAsyncWorldEdit.jar'},
    'https://ci.dmulloy2.net/job/ProtocolLib': {0: 'ProtocolLib.jar'},
    'https://github.com/NEZNAMY/TAB': {0: 'TAB.jar'},
    'https://dev.bukkit.org/projects/worldguard/files/latest': 'WorldGuard.jar',
}
# pylint: enable=line-too-long


def run_logging() -> None:
    """Run logging to the file and console."""
    logging.basicConfig(
        format='[%(asctime)s %(levelname)s]: %(message)s',
        datefmt='%d.%m.%Y %H:%M:%S',
        level=logging.INFO,
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(),
        ]
    )


class VersionFileHandler:
    """Working with a JSON file containing plugin versions."""

    def __init__(self):
        self._data: Dict[str, int] = {}

        self._handle_file()

    def __del__(self):
        self.write()

    def get(self, key: str) -> int | None:
        """Get a value from the data by key."""
        return self._data[key] if key in self._data else None

    def set(self, key: str, value: int) -> None:
        """Set a value on the key in the data."""
        self._data[key] = value

    def read(self) -> None:
        """Read a data from the file."""
        with open(VERSION_FILE, 'r') as infile:
            self._data = json.load(infile)

    def write(self) -> None:
        """Write the current data to the file."""
        with open(VERSION_FILE, 'w+') as outfile:
            json.dump(self._data, outfile)

    def _handle_file(self) -> None:
        """Create/read the file depending on its existence."""
        # Maybe it could be done in a more beautiful way?
        if os.path.exists(VERSION_FILE):
            self.read()
        else:
            self.write()


class PluginUpdater:
    """Downloading/updating plugins if its version is outdated."""

    def __init__(self):
        # A little statistics to broaden the mind.
        self._updated: int = 0
        self._downloaded: int = 0
        self._total: int = 0

        self._version_file_handler: VersionFileHandler = VersionFileHandler()

        self._handle_dirs()

    def run(self) -> None:
        """Run PluginUpdater."""
        logging.info('PluginUpdater is running.')

        if not PLUGINS:
            logging.critical('Plugins are not specified.')
            return

        for url, files in PLUGINS.items():
            if type(url) != str or type(files) not in (str, dict):
                return

            self._total += len(files) if type(files) == dict else 1

            domain = url.lower().split('/')[2]
            if 'spigotmc.org' in domain:
                self.download(self._handle_spigot(url, files))
            # Unfortunately, plugin developers usually host Jenkins on their
            # own server. Fortunately, such domains always have a
            # "ci" subdomain.
            elif 'ci.' in domain:
                self.download(self._handle_jenkins(url, files))
            elif 'github.com' in domain:
                self.download(self._handle_github(url, files))
            else:
                # The other types of plugins try to download from
                # direct links.
                self.download({url: files})

        logging.info(
            f'PluginUpdater is finished (updated/downloaded/total: '
            f'{self._updated}/{self._downloaded}/{self._total}).'
        )

    def download(self, data: Dict[str, str] | None) -> None:
        """Download the plugin by data."""
        if data is None:
            return

        for url, file in data.items():
            response = requests.get(url)
            if response.ok:
                with open(f'{PLUGIN_DIR}/{file}', 'wb') as outfile:
                    outfile.write(response.content)
                    self._downloaded += 1
            else:
                logging.error(f'Failed to download the file "{file}".')

    def _handle_dirs(self) -> None:
        """Create the plugins directory if it does not exist."""
        if not os.path.exists(PLUGIN_DIR):
            os.makedirs(PLUGIN_DIR, exist_ok=True)

    def _handle_spigot(self, url: str, file: str) -> Dict[str, str] | None:
        """Get a direct URL to the Spigot plugin."""
        resource = url.split('.')[-1]
        response = requests.get(
            f'https://api.spiget.org/v2/resources/{resource}/versions/latest'
        )
        if response.ok:
            version = response.json()['id']
            if self._version_file_handler.get(file) != version:
                self._version_file_handler.set(file, version)
                self._updated += 1
                direct_url = (f'https://api.spiget.org/v2/resources/'
                              f'{resource}/download?version={version}')
                return {direct_url: file}
        else:
            logging.error(f'Failed to get data from URL: "{url}".')

    def _handle_jenkins(
        self, url: str, files: Dict[int, str]
    ) -> Dict[str, str] | None:
        """Get a direct URL to the Jenkins plugin."""
        response = requests.get(f'{url}/lastSuccessfulBuild/api/json')
        if response.ok:
            data = response.json()
            build = data['number']
            if self._version_file_handler.get(
                files[next(iter(files))]
            ) != build:
                result = {}
                for i, file in files.items():
                    direct_url = (f'{url}/lastSuccessfulBuild/artifact/'
                                  f'{data["artifacts"][i]["relativePath"]}')
                    result[direct_url] = file
                    self._version_file_handler.set(file, build)
                    self._updated += 1
                return result
        else:
            logging.error(f'Failed to get data from URL: "{url}".')

    def _handle_github(
        self, url: str, files: Dict[int, str]
    ) -> Dict[str, str] | None:
        """Get a direct URL to the GitHub plugin."""
        response = requests.get(
            f'{url.replace("github.com", "api.github.com/repos")}/'
            f'releases/latest'
        )
        if response.ok:
            data = response.json()
            release = data['id']
            if self._version_file_handler.get(
                files[next(iter(files))]
            ) != release:
                result = {}
                for i, file in files.items():
                    direct_url = data['assets'][i]['browser_download_url']
                    result[direct_url] = file
                    self._version_file_handler.set(file, release)
                    self._updated += 1
                return result
        else:
            logging.error(f'Failed to get data from URL: "{url}".')


def main() -> None:
    """Run logging and PluginUpdater."""
    run_logging()

    plugin_updater = PluginUpdater()
    plugin_updater.run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # Clean fail on keyboard interrupt - beautiful.
        sys.exit(1)
    except Exception as exc:
        # Just in case.
        logging.exception(exc, exc_info=True)
