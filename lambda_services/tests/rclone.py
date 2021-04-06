# coding: utf-8
"""Rclone is used to mount remote directories for easier processing of files."""

from distutils.spawn import find_executable
from logging import getLogger, ERROR, INFO
from os import listdir
from os.path import abspath, exists, ismount
from subprocess import check_output, CalledProcessError
from time import sleep

_LOGGER = getLogger(__name__)

"""
DESCRIPTION:

The purpose of this class is to use https://rclone.org to mount and unmount
remote storage such as Amazon S3 and Azure Blob storage. This allows other
classes to use the remove storage as if it is local.
"""


def check_rclone_program():
    rclone_prog = "rclone"
    ret = find_executable(rclone_prog)
    if ret is None:
        _LOGGER.critical(
            "ERROR: rclone not found\n\t"
            "Please install rclone firstly: https://rclone.org/downloads/"
        )
        raise FileNotFoundError()
    return ret


class Rclone:
    def __init__(self, config_name):
        """Create interface to rclone executable.

        The use case for this class is to umount a remote src_path
        from the config_name onto a local path. If you had a config
        named, S3, This would be the
        equivalent of running:
            rclone mount --daemon S3::bucket/name/ $HOME/S3_mount/
        To find a list of configs, run the following:
            rclone listremotes

        :param str config_name: The string for the config to use
        """
        self.config_name = config_name
        self.mount_path = None
        self._LOGGER = getLogger(__class__.__name__)

        ret = check_rclone_program()
        self._LOGGER.info("INFO: rclone is detected: %s", ret)

    def mount(self, remote_path, mount_path):
        """Mount the remote path to the local mount path
        :param str remote_path: the remote path to mount
        :param str mount_path: the local path where the remote is mounted
        """

        # So we can unmount the mount_path later
        if exists(mount_path):
            self.mount_path = mount_path
        else:
            raise FileNotFoundError(mount_path)

        # Unmount any existing mount
        if ismount(abspath(self.mount_path)):
            self._LOGGER.debug(
                "DEBUG: Unmounting existing %s", self.mount_path
            )
            self.umount()

        args = f"{self.config_name}://{remote_path} {self.mount_path}"
        cmd = f"rclone mount --daemon {args}"
        _LOGGER.debug("MOUNT: %s", cmd)
        self.runcmd(cmd)

        # Don't return until there files can be seen otherwise the
        # mount may have been successful but is not useful unless
        # files in the mount can be accessed.
        file_list = []
        attempt = 0
        max_attempts = 20
        while not file_list and attempt < max_attempts:
            file_list = listdir(self.mount_path)
            _LOGGER.debug("ATTEMPT: %s, LIST: %s", attempt, file_list)
            attempt += 1
            sleep(1)

    def umount(self):
        """Unmount the remote path from the local mount path
        :param str mount_path: the local path where the remote is mounted
        """
        _LOGGER.debug(f"DEBUG: UMOUNT: {self.mount_path}")
        cmd = f"umount {self.mount_path}"
        self.runcmd(cmd)

        # Make sure unmount worked
        attempt = 0
        max_attempts = 20
        while ismount(abspath(self.mount_path)) and attempt < max_attempts:
            _LOGGER.debug("DEBUG: Unmount waiting %s", self.mount_path)
            _LOGGER.debug("ATTEMPT: %s", attempt)
            attempt += 1
            sleep(1)

    def runcmd(self, cmd):
        ret = None
        try:
            ret = check_output(cmd, shell=True)
            self._LOGGER.info(
                "COMMAND: %s, is okay:\n\t%s",
                cmd,
                ret.decode("utf-8").replace("\0", ""),
            )
        except CalledProcessError as cpe:
            print(f"RET: {ret}\nCPE: {cpe}")
            self._LOGGER.critical(
                "ERROR: %s, failed with:\n\t%s",
                cmd,
                ret.decode("utf-8").replace("\0", ""),
            )
            exit(cpe)
