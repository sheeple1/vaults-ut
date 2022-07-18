from ast import literal_eval
from operator import sub
from pathlib import Path
import json
import os
import subprocess
import shutil
import uuid

HOME = os.path.expanduser("~")
XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config"))
APP_CONFIG = Path.joinpath(Path(XDG_CONFIG_HOME), "vaults-ut.walking-octopus")

APP_CONFIG.mkdir(parents=True, exist_ok=True)
configFilePath = Path.joinpath(APP_CONFIG, "knownVaults.json")
configFilePath.touch(exist_ok=True)

def get_config() -> dict:
    configFile = open(str(configFilePath), "r", encoding='utf-8').read()
    if configFile == "": return {}

    return json.loads(configFile)

vault_dict = get_config()

def save_config():
    jsonVaults = json.dumps(vault_dict)
    # TODO: Filter out the non-existent vaults

    configFile = open(str(configFilePath), "w", encoding='utf-8')

    if jsonVaults != "{}":
        configFile.write(jsonVaults)
    else:
        configFile.write("")

    configFile.close()

def get_data():
    vault_list = []

    for vault_id in vault_dict:
        vault_dict[vault_id]["is_mounted"] = is_mounted(vault_id)

    for vault_id in vault_dict:
        item = vault_dict[vault_id]
        item["id"] = vault_id
        vault_list.append(item)

    return vault_list

def is_available() -> dict:
    (gocryptfs_status, _) = subprocess.getstatusoutput('gocryptfs --version')
    (fust_status, _) = subprocess.getstatusoutput('fusermount -V')

    return { 'gocryptfs': gocryptfs_status == 0, 'fuse': fust_status == 0 }

# FIXME: shell=True is unsecure
def install_fuse(sudo_password: str) -> int:
    cmd1 = subprocess.Popen(['echo', sudo_password], stdout=subprocess.PIPE)
    cmd2 = subprocess.Popen("sudo -S sh -c 'mount -o rw,remount /; apt-get update; apt-get install fuse -y; mount -o ro,remount /'",
        stdin=cmd1.stdout,
        stdout=subprocess.PIPE,
        shell=True)

    cmd2.wait()

    return cmd2.returncode

def disable_sleep(appID: str) -> int:
    sleep_exempt_apps = literal_eval(str(subprocess.check_output(["gsettings", "get", "com.canonical.qtmir", "lifecycle-exempt-appids"]).strip(), "utf-8"))

    if appID not in sleep_exempt_apps:
        sleep_exempt_apps.append(appID)

    returncode = subprocess.call(["gsettings", "set", "com.canonical.qtmir", "lifecycle-exempt-appids", str(sleep_exempt_apps)])
    return returncode

def mv(source: str, dest: str) -> int:
    source = source.replace("~", os.getenv("HOME")) # What if HOME is not set?
    source = source.replace("file://", "")

    child = subprocess.run(["mv", source, dest])
    return child.returncode

def is_mounted(uuid: str) -> bool:
    mount_dir = vault_dict[uuid]["mount_directory"]
    (status, output) = subprocess.getstatusoutput("mountpoint " + mount_dir)

    # If the user closed an app without unmounting the vault,
    # it will result in `Transport endpoint is not connected` error.
    # I must check for it and remount it if needed.

    if "Transport endpoint is not connected" in output:
        unmount(uuid)

    return status == 0

def import_vault(vault: dict) -> int:
    # FIXME: Throw an exception if `gocryptfs.conf` isn't found
    if not os.path.exists(vault["encrypted_data_directory"]):
        return 1

    vault["encrypted_data_directory"] = vault["encrypted_data_directory"].replace("~", os.getenv("HOME"))
    vault["mount_directory"] = vault["mount_directory"].replace("~", os.getenv("HOME"))
    
    my_uuid = str(uuid.uuid4())
    vault_dict[my_uuid] = vault
    save_config()

    return 0

def init(vault: dict, password: str) -> int:
    vault["encrypted_data_directory"] = vault["encrypted_data_directory"].replace("~", os.getenv("HOME"))
    vault["mount_directory"] = vault["mount_directory"].replace("~", os.getenv("HOME"))
    vault["is_mounted"] = False

    os.makedirs(vault["encrypted_data_directory"], exist_ok=True)

    # Because no benchmark data was provided, I assume most phones do not have AES acceleration,
    # so, I'll use 'xchacha' for better performance.

    child = subprocess.Popen(["gocryptfs", "-xchacha", "-init", vault["encrypted_data_directory"]],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True)

    child.communicate(password)

    child.wait()

    my_uuid = str(uuid.uuid4())
    vault_dict[my_uuid] = vault

    save_config()

    return child.returncode


# TODO: Add option to turn a dir into a vault

# TODO: Add way to view a recovery key

# TODO: Implement password change in the UI
def change_password(vault_id: str, new_password: str, old_password: str) -> int:
    cipher_dir = vault_dict[vault_id]["encrypted_data_directory"]
    child = subprocess.Popen(["gocryptfs", "--passwd", cipher_dir],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True)

    child.communicate(old_password + "\n" + new_password)

    child.wait()

    return child.returncode

# TODO: Add a speed benchmark

# TODO: Implement vault editing in the UI
def edit_vault(vault_id: str, edited_vault: dict) -> bool:
    status_mountdir, status_datadir = 1, 1

    if edited_vault["mount_directory"] != vault_dict[vault_id]["mount_directory"]:
        status_mountdir = mv(vault_dict[vault_id]["mount_directory"], edited_vault["mount_directory"])

    if edited_vault["encrypted_data_directory"] != vault_dict[vault_id]["encrypted_data_directory"]:
        status_datadir = mv(vault_dict[vault_id]["encrypted_data_directory"], edited_vault["encrypted_data_directory"])

    vault_dict[vault_id] = edited_vault

    return status_mountdir == 0 and status_datadir == 0

# TODO: Implement fsck in the UI
def fsck(uuid: str, password: str) -> int:
    child = subprocess.Popen(["gocryptfs", "-fsck", vault_dict[uuid]["encrypted_data_directory"]],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True)

    child.communicate(password)

    child.wait()

    return child.returncode


def mount(uuid: str, password: str) -> int:
    vault = vault_dict[uuid]
    os.makedirs(vault["mount_directory"], exist_ok=True)

    child = subprocess.Popen(["gocryptfs", vault["encrypted_data_directory"], vault["mount_directory"]],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True)

    child.communicate(password)

    if child.returncode == 0:
        vault_dict[uuid]["is_mounted"] = is_mounted(uuid)

    return child.returncode

def unmount(uuid: str):
    output = subprocess.run(["fusermount", "-u", vault_dict[uuid]["mount_directory"]], stdout=subprocess.DEVNULL)

    if output.returncode == 0:
        vault_dict[uuid]["is_mounted"] = is_mounted(uuid)

    return output.returncode

def remove(uuid: str):
    vault = vault_dict[uuid]

    # FIXME: Unhandled error
    unmount(uuid)

    shutil.rmtree(vault["encrypted_data_directory"], ignore_errors=True)
    shutil.rmtree(vault["mount_directory"], ignore_errors=True)

    vault_dict.pop(uuid, None)
    save_config()
