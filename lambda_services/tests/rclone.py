# coding: utf-8
"""Rclone is used to mount remote directories for easier processing of files."""

from logging import getLogger, ERROR, INFO
from distutils.spawn import find_executable
from subprocess import check_output, CalledProcessError
from os.path import exists, ismount
from os import listdir
from sys import exit

_LOGGER = getLogger(__name__)

"""
DESCRIPTION:
"""


def check_rclone_program():
    rclone_prog = "rclone"
    ret = find_executable(rclone_prog)
    if ret is None:
        exit("Please install rclone firstly: https://rclone.org/downloads/")
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

        ret = check_rclone_program()
        _LOGGER.info("INFO: rclone is detected: %s", ret)

    def mount(self, remote_path, mount_path):
        """Mount the remote path to the local mount path
        :param str remote_path: the remote path to mount
        :param str mount_path: the local path where the remote is mounted
        """

        # Unmount any existing mount
        if self.mount_path and ismount(self.mount_path):
            self.umount()

        # So we can unmount the mount_path later
        if exists(mount_path):
            self.mount_path = mount_path
        else:
            raise FileNotFoundError(mount_path)

        args = f"{self.config_name}://{remote_path} {self.mount_path}"
        cmd = f"rclone mount --daemon {args}"
        print(f"MOUNT: {cmd}")
        self.runcmd(cmd)

    def umount(self):
        """Mount the remote path to the local mount path
        :param str remote_path: the remote path to mount
        :param str mount_path: the local path where the remote is mounted
        """
        print(f"UMOUNT: {self.mount_path}")
        cmd = f"umount {self.mount_path}"
        self.runcmd(cmd)
        self.mount_path = None

    def runcmd(self, cmd):
        ret = None
        try:
            ret = check_output(cmd, shell=True)
            _LOGGER.info(
                "COMMAND: %s, is okay:\n\t%s",
                cmd,
                ret.decode("utf-8").replace("\0", ""),
            )
        except CalledProcessError as cpe:
            print(f"RET: {ret}\nCPE: {cpe}")
            _LOGGER.critical(
                "ERROR: %s, failed with:\n\t%s",
                cmd,
                ret.decode("utf-8").replace("\0", ""),
            )
            exit(cpe)
