#!/usr/bin/env python3
import ctypes
import json
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

if os.name == "nt":
    import msvcrt
else:
    import select
    import tty
    import termios

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:  # pragma: no cover
    tk = None
    ttk = None
    messagebox = None
    filedialog = None

CONFIG_FILE_NAME = "wol_vm.config"
VM_DIR_NAME = "WoL_VM"


def get_default_vm_dir():
    """Returns the default VM storage directory in a user-writable location."""
    if os.name == "nt":
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base_dir = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

    try:
        os.makedirs(base_dir, exist_ok=True)
    except OSError:
        base_dir = os.path.expanduser("~")

    vm_dir = os.path.join(base_dir, VM_DIR_NAME)
    try:
        os.makedirs(vm_dir, exist_ok=True)
    except OSError:
        vm_dir = os.path.expanduser("~")
    return vm_dir


def get_config_path():
    """Returns a user-writable config path instead of the script directory."""
    base_dir = None
    if os.name == "nt":
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base_dir = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")

    try:
        os.makedirs(base_dir, exist_ok=True)
    except OSError:
        base_dir = os.path.expanduser("~")

    config_path = os.path.join(base_dir, CONFIG_FILE_NAME)
    legacy_path = os.path.abspath(CONFIG_FILE_NAME)

    if not os.path.exists(config_path) and os.path.exists(legacy_path):
        try:
            shutil.copy2(legacy_path, config_path)
        except OSError:
            pass

    return config_path


CONFIG_FILE = get_config_path()
HOST_ACTION_LOCK = threading.Lock()


def get_vm_disk_path(vm_dir=None):
    """Returns the disk image path, using either a custom selected directory or the default VM folder."""
    selected_dir = vm_dir or get_default_vm_dir()
    try:
        os.makedirs(selected_dir, exist_ok=True)
    except OSError:
        selected_dir = get_default_vm_dir()

    disk_path = os.path.join(selected_dir, "WoL_disk.qcow2")
    legacy_path = os.path.abspath("WoL_disk.qcow2")

    if not os.path.exists(disk_path) and os.path.exists(legacy_path):
        try:
            shutil.move(legacy_path, disk_path)
        except OSError:
            pass

    return disk_path


DEFAULT_VM_DIR = get_default_vm_dir()
DISK_IMAGE = get_vm_disk_path(DEFAULT_VM_DIR)
ISO_PATH_WIN11_X64 = os.path.expanduser("~/Downloads/WoL_Win11_x64.iso")
ISO_PATH_ARM64 = os.path.expanduser("~/Downloads/WoL_ARM64.iso")
ISO_PATH_WIN10_X64 = os.path.expanduser("~/Downloads/WoL_Win10_x64.iso")
ISO_PATH_X86 = os.path.expanduser("~/Downloads/WoL_x86.iso")
VIRTIO_ISO_PATH = os.path.expanduser("~/Downloads/virtio-win-0.1.262.iso")

VIRTIO_ITEM_ID = "virtio-win-0.1.262"
VIRTIO_ISO_NAME = "virtio-win-0.1.262.iso"
DOWNLOAD_IN_PROGRESS = False
CTRL_CLOSE_EVENT = 2

GUI_THEME = {
    "bg": "#071b2b",
    "bg_alt": "#0a2740",
    "panel": "#0f3353",
    "panel_2": "#153f66",
    "blue": "#1e88e5",
    "blue_dark": "#0d47a1",
    "blue_light": "#cfe8ff",
    "white": "#f2f8ff",
    "black": "#020b13",
    "muted": "#9dc8ff",
    "accent": "#2ba7ff",
    "success": "#1cc88a",
    "warn": "#ffd166",
    "danger": "#ff6b6b",
}


def handle_console_close_event(event):
    """Block terminal close during an active ISO download on Windows."""
    if DOWNLOAD_IN_PROGRESS and event == CTRL_CLOSE_EVENT:
        print(
            "\nYou can't close this tab while it is in the process of downloading an ISO. "
            "Use 'c' or 'q' instead.",
            flush=True,
        )
        return True
    return False


def install_console_close_guard():
    """Registers the Windows console close handler for the active terminal."""
    if os.name != "nt":
        return

    kernel32 = ctypes.WinDLL("kernel32")
    handler = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)(
        handle_console_close_event
    )
    kernel32.SetConsoleCtrlHandler(handler, True)


def handle_download_close_attempt(signum, frame):
    """Prevent accidental shutdown while an ISO is being downloaded."""
    if DOWNLOAD_IN_PROGRESS:
        print(
            "\nYou can't close this tab while it is in the process of downloading an ISO. "
            "Use 'c' or 'q' instead.",
            flush=True,
        )
        return
    raise KeyboardInterrupt


def remove_partial_download(path):
    """Deletes an incomplete ISO or other temp download if the transfer is cancelled or fails."""
    if not path:
        return
    try:
        if os.path.exists(path) and os.path.isfile(path):
            os.remove(path)
            print(f"Partial file removed: {path}")
    except OSError as exc:
        print(f"Could not remove partial file {path}: {exc}")


def get_current_user_groups():
    """Returns a robust, cross-distro set of groups for the current user."""
    groups = set()

    try:
        groups.update(os.getgroups())
    except Exception:
        pass

    for command in (["id", "-nG"], ["groups"]):
        try:
            output = subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL)
        except Exception:
            continue

        if not output:
            continue

        raw_parts = re.split(r"[\s:]+", output.strip())
        groups.update(part for part in raw_parts if part)

    return groups


def get_kvm_flags(qemu_binary):
    """Returns KVM flags only when the host, binary, and /dev/kvm access all match."""
    host_arch = platform.machine().lower()
    is_x86_match = "x86_64" in host_arch and qemu_binary == "qemu-system-x86_64"
    is_arm_match = "aarch64" in host_arch and qemu_binary == "qemu-system-aarch64"

    if not (is_x86_match or is_arm_match):
        print(
            "⚠️ Host and Guest architectures differ. Running in emulation mode"
            " without KVM."
        )
        return []

    if os.name == "nt":
        return ["-enable-kvm", "-cpu", "host"]

    kvm_device = "/dev/kvm"
    if not os.path.exists(kvm_device):
        print(
            "⚠️ KVM is not available on this system. Running in emulation mode"
            " without KVM."
        )
        return []

    if not os.access(kvm_device, os.R_OK | os.W_OK):
        print(
            "⚠️ KVM is installed but this user cannot access /dev/kvm. "
            "Add your user to the 'kvm' group or fix permissions, then rerun."
        )
        print("Fix command: sudo usermod -aG kvm $USER")
        print("Then log out and back in, or reboot the system.")
        return []

    user_groups = get_current_user_groups()
    if "kvm" not in user_groups:
        print(
            "⚠️ /dev/kvm is present, but the user is not in the kvm group. "
            "KVM acceleration will be disabled until the user is added to the group."
        )
        print("Fix command: sudo usermod -aG kvm $USER")
        return []

    return ["-enable-kvm", "-cpu", "host"]


def safe_systemctl_action(action_name, command):
    """Runs systemctl commands only when systemd is present, with generic fallbacks for non-systemd Linux."""
    if shutil.which("systemctl"):
        subprocess.run(command)
        return

    fallback_map = {
        "shutdown": ["shutdown", "-P", "now"],
        "restart": ["reboot"],
        "sleep": ["systemctl", "suspend"],
    }

    fallback = fallback_map.get(action_name)
    if fallback and shutil.which(fallback[0]):
        subprocess.run(fallback)
        return

    if action_name == "sleep":
        for candidate in ("pm-suspend", "loginctl suspend", "systemctl suspend"):
            binary = candidate.split()[0]
            if shutil.which(binary):
                subprocess.run(candidate.split())
                return

    print(f"\nThis system does not support host {action_name} actions automatically.")


def detect_desktop_environment():
    """Detects the active Linux desktop environment to choose the best autostart method."""
    candidates = [
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("GNOME_DESKTOP_SESSION_ID", ""),
        os.environ.get("KDE_FULL_SESSION", ""),
        os.environ.get("CINNAMON_VERSION", ""),
    ]

    for value in candidates:
        if not value:
            continue
        normalized = value.lower()
        if "kde" in normalized:
            return "kde"
        if "gnome" in normalized:
            return "gnome"
        if "cinnamon" in normalized:
            return "cinnamon"
        if "xfce" in normalized:
            return "xfce"
        if "mate" in normalized:
            return "mate"
        if "lxqt" in normalized or "lubuntu" in normalized:
            return "lxqt"
        if "budgie" in normalized:
            return "budgie"

    if os.path.exists(os.path.expanduser("~/.kde")):
        return "kde"
    if os.path.exists(os.path.expanduser("~/.config/cinnamon")):
        return "cinnamon"
    if os.path.exists(os.path.expanduser("~/.config/xfce4")):
        return "xfce"

    return "generic"


def create_autostart_entry():
    """Creates a desktop autostart entry for the current Linux session, with generic fallbacks."""
    desktop_env = detect_desktop_environment()
    config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")

    autostart_dirs = []
    if desktop_env == "kde":
        autostart_dirs.extend(
            [
                os.path.join(config_home, "autostart"),
                os.path.expanduser("~/.kde/Autostart"),
            ]
        )
    else:
        autostart_dirs.append(os.path.join(config_home, "autostart"))

    if not autostart_dirs:
        autostart_dirs.append(os.path.join(config_home, "autostart"))

    python_bin = shutil.which("python3") or sys.executable
    script_path = os.path.abspath(__file__)
    exec_command = f"{shlex.quote(python_bin)} {shlex.quote(script_path)}"

    desktop_content = f"""[Desktop Entry]
Type=Application
Name=Windows on Linux VM
Comment=Launch the WoL VM automatically after login.
Exec={exec_command}
Terminal=false
StartupNotify=false
Hidden=false
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
X-KDE-StartupNotify=false
"""

    created_paths = []
    for directory in dict.fromkeys(autostart_dirs):
        os.makedirs(directory, exist_ok=True)
        desktop_file_path = os.path.join(directory, "wol_vm.desktop")
        with open(desktop_file_path, "w", encoding="utf-8") as f:
            f.write(desktop_content)
        created_paths.append(desktop_file_path)

    if desktop_env == "generic":
        print("\n⚠️ No desktop environment was detected; a generic XDG autostart entry was created.")
    else:
        print(f"\n✅ Autostart configuration created for {desktop_env}.")

    for path in created_paths:
        print(f" - {path}")


def get_host_display_size():
    """Returns the current host display width and height when available."""
    try:
        if os.name == "nt":
            user32 = ctypes.windll.user32
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            if width and height:
                return width, height
    except Exception:
        pass

    if os.environ.get("WAYLAND_DISPLAY"):
        return 1920, 1080

    for command in (["xrandr"], ["xdpyinfo"]):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            continue

        if result.returncode != 0:
            continue

        output = result.stdout or ""
        if command[0] == "xrandr":
            for line in output.splitlines():
                if "connected" in line and "current" in line:
                    match = re.search(r"current\s+(\d+)\s+x\s+(\d+)", line, flags=re.IGNORECASE)
                    if match:
                        return int(match.group(1)), int(match.group(2))
        else:
            match = re.search(r"dimensions:\s*(\d+)\s+x\s+(\d+)", output, flags=re.IGNORECASE)
            if match:
                return int(match.group(1)), int(match.group(2))

    return 1920, 1080


def get_qemu_display_args():
    """Use a display mode that is compatible with common Linux session types."""
    if os.environ.get("WAYLAND_DISPLAY"):
        return ["-display", "gtk,show-cursor=on"]

    return ["-display", "default,show-cursor=on", "-full-screen"]


def play_vm_launch_notification():
    message = "Finished process. The VM is starting."
    print(f"\n{message}")

    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass

    for voice_cmd in (
        ["espeak-ng", message],
        ["espeak", message],
        ["spd-say", message],
    ):
        binary = shutil.which(voice_cmd[0])
        if not binary:
            continue
        try:
            subprocess.Popen(
                voice_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            break
        except Exception:
            pass


def print_all_prereqs_passed():
    """Shows a final success message only after all checks have passed."""
    print("\n✅ All prerequisites passed. The VM is ready to launch.")
    play_vm_launch_notification()


def handle_host_exit_action(action):
    with HOST_ACTION_LOCK:
        if action == "shutdown":
            print("\nShutting down host system...")
            safe_systemctl_action("shutdown", ["systemctl", "poweroff"])
        elif action == "restart":
            print("\nRestarting host system...")
            safe_systemctl_action("restart", ["systemctl", "reboot"])
        elif action == "sleep":
            print("\nPutting host system to sleep...")
            safe_systemctl_action("sleep", ["systemctl", "suspend"])
        else:
            print("\nVM closed. Exiting script.")
            print("Deleting incomplete ISO files.")
            # If the ISO file doesn't exist, it will switch to the next one, and at the last ISO, it will just pass.
            os.remove(ISO_PATH_WIN11_X64) if os.path.exists(ISO_PATH_WIN11_X64) else None
            os.remove(ISO_PATH_ARM64) if os.path.exists(ISO_PATH_ARM64) else None
        os.remove(ISO_PATH_WIN10_X64) if os.path.exists(ISO_PATH_WIN10_X64) else None
        os.remove(ISO_PATH_X86) if os.path.exists(ISO_PATH_X86) else None
        print("Deleting incomplete VirtIO ISO files if any exist.")
        os.remove(VIRTIO_ISO_PATH) if os.path.exists(VIRTIO_ISO_PATH) else None


def save_config(qemu_binary, ram_size, cpu_cores, exit_action, vm_dir=None, custom_iso_path=None):
    config_data = {
        "qemu_binary": qemu_binary,
        "ram_size": ram_size,
        "cpu_cores": cpu_cores,
        "exit_action": exit_action,
        "vm_dir": vm_dir or DEFAULT_VM_DIR,
        "custom_iso_path": custom_iso_path or "",
    }
    config_path = get_config_path()
    config_dir = os.path.dirname(config_path)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f)


def delete_vm_data():
    """Deletes the saved VM disk image and config, plus any legacy local copies."""
    removed = []
    candidate_paths = [
        DISK_IMAGE,
        CONFIG_FILE,
        os.path.abspath("WoL_disk.qcow2"),
        os.path.abspath(CONFIG_FILE_NAME),
    ]

    for path in dict.fromkeys(candidate_paths):
        if not path or not os.path.exists(path):
            continue
        try:
            os.remove(path)
            removed.append(path)
        except OSError:
            pass

    try:
        vm_dir = os.path.dirname(DISK_IMAGE)
        if os.path.isdir(vm_dir) and not os.listdir(vm_dir):
            os.rmdir(vm_dir)
    except OSError:
        pass

    return removed


def load_config():
    config_paths = [get_config_path(), os.path.abspath(CONFIG_FILE_NAME)]
    seen = set()
    for path in config_paths:
        if path in seen:
            continue
        seen.add(path)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
            except OSError:
                continue
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {
                    "qemu_binary": content,
                    "ram_size": "4",
                    "cpu_cores": "2",
                    "exit_action": "none",
                    "vm_dir": DEFAULT_VM_DIR,
                    "custom_iso_path": "",
                }
    return None


def clear_terminal():
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


def launch_vm_process(qemu_cmd, exit_action="none"):
    """Starts QEMU detached and optionally triggers a host action when the VM exits."""
    if os.name != "nt":
        check_linux_vm_runtime_compatibility(qemu_cmd[0] if qemu_cmd else "qemu-system-x86_64")

    proc = subprocess.Popen(qemu_cmd, start_new_session=True)

    def wait_for_exit():
        try:
            proc.wait()
            if exit_action and exit_action != "none":
                handle_host_exit_action(exit_action)
        except Exception:
            pass

    if exit_action and exit_action != "none":
        threading.Thread(target=wait_for_exit, daemon=True).start()

    return proc


def check_linux_vm_runtime_compatibility(qemu_binary):
    """Warns about common Linux compatibility problems before a VM starts."""
    if os.name == "nt":
        return True

    wayland_session = bool(os.environ.get("WAYLAND_DISPLAY"))
    display_info = "Wayland" if wayland_session else "X11"
    print(f" - display backend: {display_info} session detected")

    if wayland_session:
        print(" - display note: Wayland may need GTK-based display settings; fullscreen may be limited")
    elif not shutil.which("xrandr") and not shutil.which("xdpyinfo"):
        print(" - display note: no X11 sizing utilities found; using a safe default fallback size")

    if os.path.exists("/dev/kvm"):
        if not os.access("/dev/kvm", os.R_OK | os.W_OK):
            print(" - /dev/kvm access: denied")
        else:
            print(" - /dev/kvm access: OK")

        user_groups = get_current_user_groups()
        if "kvm" not in user_groups:
            print(" - user group membership: not in kvm group; KVM acceleration may be disabled")
        else:
            print(" - user group membership: member of kvm group")
    else:
        print(" - /dev/kvm access: not present; emulation mode may be used")

    if not shutil.which("systemctl"):
        print(" - init system: non-systemd fallback mode enabled")

    return True


def print_linux_readiness_report(qemu_binary):
    if os.name == "nt":
        return

    print("\nLinux readiness check:")
    checks = [
        ("QEMU binary", shutil.which(qemu_binary)),
        ("qemu-img", shutil.which("qemu-img")),
        ("systemctl", shutil.which("systemctl")),
        ("/dev/kvm exists", os.path.exists("/dev/kvm")),
    ]

    for label, result in checks:
        status = "OK" if result else "MISSING"
        print(f" - {label}: {status}")

    if os.path.exists("/dev/kvm"):
        print(f" - /dev/kvm accessible: {'YES' if os.access('/dev/kvm', os.R_OK | os.W_OK) else 'NO'}")

    groups = get_current_user_groups()
    if "kvm" in groups:
        print(" - user group membership: member of kvm group")
    else:
        print(" - user group membership: not in kvm group")

    if not shutil.which("systemctl"):
        print(" - init system: non-systemd fallback mode enabled")


def resolve_executable(command_name):
    resolved = shutil.which(command_name)
    if resolved:
        return resolved

    if os.name != "nt":
        return None

    extensions = ["", ".exe", ".bat", ".cmd"]
    candidate_names = [command_name]
    if not command_name.lower().endswith(".exe"):
        candidate_names.extend(f"{command_name}{ext}" for ext in extensions)

    install_roots = [
        r"C:\Program Files\qemu",
        r"C:\Program Files\QEMU",
        r"C:\Program Files\qemu\bin",
        r"C:\Program Files\QEMU\bin",
    ]

    for root in install_roots:
        if not os.path.isdir(root):
            continue
        for name in candidate_names:
            full_path = os.path.join(root, name)
            if os.path.exists(full_path):
                return full_path

    return None


def ensure_required_dependencies(qemu_binary, exit_action="none", gui_mode=False):
    if os.name != "nt":
        print_linux_readiness_report(qemu_binary)

    required = ["qemu-img", qemu_binary]
    if os.name != "nt" and exit_action in {"shutdown", "restart", "sleep"}:
        required.append("systemctl")

    missing = [cmd for cmd in required if resolve_executable(cmd) is None]
    if not missing:
        return

    missing_list = ", ".join(missing)
    message = (
        f"Missing required dependency/dependencies: {missing_list}\n\n"
        "Install QEMU and make sure qemu-img and the selected QEMU binary are available.\n\n"
        "Windows: install QEMU from https://www.qemu.org/download/ and make sure the install folder is on PATH.\n\n"
        "Linux example:\n"
        "  sudo apt install qemu-system-x86 qemu-utils systemd\n"
        "  # or on Fedora/RHEL: sudo dnf install qemu-system-x86 qemu-img systemd\n"
        "  # or on Arch: sudo pacman -S qemu-system-x86 qemu-img systemd"
    )

    if gui_mode:
        raise RuntimeError(message)

    print(f"\n{message}")
    sys.exit(1)


def monitor_download_cancel(cancel_flag):
    if not sys.stdin.isatty():
        return

    try:
        if os.name == "nt":
            while not cancel_flag[0]:
                if msvcrt.kbhit():
                    key = msvcrt.getwch().lower()
                    if key in {"c", "q", "\x03"}:
                        cancel_flag[0] = True
                        print("\nCancel requested. Stopping download...", flush=True)
                        break
                time.sleep(0.1)
        else:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            try:
                while not cancel_flag[0]:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1).lower()
                        if key in {"c", "q", "\x03"}:
                            cancel_flag[0] = True
                            print("\nCancel requested. Stopping download...", flush=True)
                            break
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        pass


def get_adaptive_chunk_size(speed_mbps):
    """Scale the read chunk size to match the current connection quality."""
    if speed_mbps <= 1.5:
        return 1 * 1024 * 1024
    if speed_mbps <= 4.0:
        return 2 * 1024 * 1024
    if speed_mbps <= 10.0:
        return 4 * 1024 * 1024
    return 8 * 1024 * 1024


def validate_iso_file(path, min_size_mb=10):
    """Verifies that an ISO file exists, has realistic content, and is readable by QEMU."""
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"ISO file not found: {path}")

    file_size = os.path.getsize(path)
    if file_size < min_size_mb * 1024 * 1024:
        raise ValueError(
            f"ISO file is too small to be valid: {path} ({file_size / (1024 * 1024):.1f} MB)"
        )

    print(f"Validating ISO integrity: {path}")
    print(f" - Size check: {file_size / (1024 * 1024):.1f} MB")

    try:
        with open(path, "rb") as iso_file:
            header = iso_file.read(0x20000)
    except OSError as exc:
        raise ValueError(f"Unable to read ISO file: {path} ({exc})") from exc

    if len(header) < 0x20000:
        raise ValueError(f"ISO file is incomplete or truncated: {path}")

    if b"CD001" not in header:
        raise ValueError(f"ISO file does not appear to be a valid ISO image: {path}")
    print(" - Volume header check: passed")

    qemu_check = subprocess.run(
        [resolve_executable("qemu-img") or "qemu-img", "info", "--output=json", path],
        capture_output=True,
        text=True,
    )
    if qemu_check.returncode != 0:
        error_text = (qemu_check.stderr or qemu_check.stdout or "unknown QEMU validation error").strip()
        raise ValueError(f"QEMU rejected the ISO as invalid: {error_text}")
    print(" - QEMU validation: passed")

    return True


def prepare_install_media(item_id, iso_name, output_file, virtio_item_id=None, virtio_iso_name=None, virtio_output_file=None):
    """Downloads the Windows install ISO and the VirtIO ISO before VM setup begins."""
    if os.path.exists(output_file):
        try:
            validate_iso_file(output_file)
            print(f"\nValidated existing Windows install ISO: {output_file}")
        except ValueError as exc:
            print(f"\nISO validation failed for {output_file}: {exc}")
            print("Deleting corrupted ISO and re-downloading...")
            try:
                os.remove(output_file)
            except OSError:
                pass
            download_with_eta(item_id, iso_name, output_file)
    else:
        print(f"\nDownloading Windows install ISO: {output_file}")
        download_with_eta(item_id, iso_name, output_file)

    if virtio_output_file:
        if os.path.exists(virtio_output_file):
            try:
                validate_iso_file(virtio_output_file)
                print(f"\nValidated existing VirtIO ISO: {virtio_output_file}")
            except ValueError as exc:
                print(f"\nVirtIO ISO validation failed for {virtio_output_file}: {exc}")
                print("Deleting corrupted VirtIO ISO and re-downloading...")
                try:
                    os.remove(virtio_output_file)
                except OSError:
                    pass
                download_with_eta(virtio_item_id, virtio_iso_name, virtio_output_file)
        else:
            print(f"\nDownloading VirtIO drivers ISO: {virtio_output_file}")
            download_with_eta(virtio_item_id, virtio_iso_name, virtio_output_file)


def download_with_eta(item_id, iso_name, output_filename):
    global DOWNLOAD_IN_PROGRESS

    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    install_console_close_guard()

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, handle_download_close_attempt)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handle_download_close_attempt)

    encoded_name = urllib.parse.quote(iso_name)
    direct_url = f"https://archive.org/download/{item_id}/{encoded_name}"

    resume_from = os.path.getsize(output_filename) if os.path.exists(output_filename) else 0
    resume_mode = resume_from > 0

    print(f"Targeting URL: {direct_url}")
    print(f"Saving to: {output_filename}")
    if resume_mode:
        print(f"Resuming download from {resume_from / (1024 * 1024):.1f} MB")
    print("Starting download... Type 'c' or 'q' at any time to cancel.\n")

    DOWNLOAD_IN_PROGRESS = True
    cancel_flag = [False]
    cancel_thread = threading.Thread(
        target=monitor_download_cancel,
        args=(cancel_flag,),
        daemon=True,
    )
    cancel_thread.start()

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        if resume_mode:
            headers["Range"] = f"bytes={resume_from}-"

        req = urllib.request.Request(direct_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            if resume_mode and response.getcode() == 200:
                print("Server does not support resume. Restarting download from zero.")
                os.remove(output_filename)
                resume_from = 0
                headers = {"User-Agent": "Mozilla/5.0"}
                req = urllib.request.Request(direct_url, headers=headers)
                with urllib.request.urlopen(req) as response, open(
                    output_filename, "wb"
                ) as out_file:
                    total_size = int(response.getheader("Content-Length", 0))
                    downloaded = 0
                    chunk_size = 5 * 1024 * 1024
                    start_time = time.time()

                    while True:
                        if cancel_flag[0]:
                            raise KeyboardInterrupt

                        chunk_start_time = time.monotonic()
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        out_file.write(chunk)
                        downloaded += len(chunk)

                        chunk_elapsed = time.monotonic() - chunk_start_time
                        if chunk_elapsed > 0:
                            chunk_speed_mbps = (len(chunk) / (1024 * 1024)) / chunk_elapsed
                            chunk_size = get_adaptive_chunk_size(chunk_speed_mbps)

                        elapsed_time = time.time() - start_time
                        if elapsed_time > 0:
                            speed_mbps = (downloaded / (1024 * 1024)) / elapsed_time

                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                remaining_bytes = total_size - downloaded

                                if speed_mbps > 0:
                                    eta_seconds = int(
                                        remaining_bytes / (speed_mbps * 1024 * 1024)
                                    )
                                    mins, secs = divmod(eta_seconds, 60)
                                    hrs, mins = divmod(mins, 60)

                                    if hrs > 0:
                                        eta_str = f"{hrs}h {mins}m {secs}s"
                                    elif mins > 0:
                                        eta_str = f"{mins}m {secs}s"
                                    else:
                                        eta_str = f"{secs}s"
                                else:
                                    eta_str = "Calculating ETA..."

                                mb_dl = downloaded / (1024 * 1024)
                                mb_total = total_size / (1024 * 1024)
                                clear_terminal()
                                print(
                                    f"Progress: {mb_dl:.1f}/{mb_total:.1f} MB"
                                    f" ({percent:.1f}%) | Speed: {speed_mbps:.2f} MB/s"
                                    f" | ETA: {eta_str}"
                                )

                        if cancel_flag[0]:
                            raise KeyboardInterrupt

                    if cancel_flag[0]:
                        raise KeyboardInterrupt

                    print("\n\nDownload complete! File saved successfully.")
                return

            total_size = int(response.getheader("Content-Range", "").split("/")[-1] or response.getheader("Content-Length", 0))
            if not total_size:
                total_size = resume_from
            downloaded = resume_from
            mode = "ab" if resume_from > 0 else "wb"

            with open(output_filename, mode) as out_file:
                chunk_size = 5 * 1024 * 1024
                start_time = time.time()

                while True:
                    if cancel_flag[0]:
                        raise KeyboardInterrupt

                    chunk_start_time = time.monotonic()
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    out_file.write(chunk)
                    downloaded += len(chunk)

                    chunk_elapsed = time.monotonic() - chunk_start_time
                    if chunk_elapsed > 0:
                        chunk_speed_mbps = (len(chunk) / (1024 * 1024)) / chunk_elapsed
                        chunk_size = get_adaptive_chunk_size(chunk_speed_mbps)

                    elapsed_time = time.time() - start_time
                    if elapsed_time > 0:
                        speed_mbps = (downloaded / (1024 * 1024)) / elapsed_time

                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            remaining_bytes = total_size - downloaded

                            if speed_mbps > 0:
                                eta_seconds = int(
                                    remaining_bytes / (speed_mbps * 1024 * 1024)
                                )
                                mins, secs = divmod(eta_seconds, 60)
                                hrs, mins = divmod(mins, 60)

                                if hrs > 0:
                                    eta_str = f"{hrs}h {mins}m {secs}s"
                                elif mins > 0:
                                    eta_str = f"{mins}m {secs}s"
                                else:
                                    eta_str = f"{secs}s"
                            else:
                                eta_str = "Calculating ETA..."

                            mb_dl = downloaded / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)
                            clear_terminal()
                            print(
                                f"Progress: {mb_dl:.1f}/{mb_total:.1f} MB"
                                f" ({percent:.1f}%) | Speed: {speed_mbps:.2f} MB/s"
                                f" | ETA: {eta_str}"
                            )

                    if cancel_flag[0]:
                        raise KeyboardInterrupt

            if cancel_flag[0]:
                raise KeyboardInterrupt

            print("\n\nDownload complete! File saved successfully.")

    except KeyboardInterrupt:
        remove_partial_download(output_filename)
        print("\nDownload cancelled by user. Partial file removed.")
        sys.exit(0)
    except Exception as e:
        remove_partial_download(output_filename)
        print(f"\nFailed to download: {e}")
        sys.exit(1)
    finally:
        DOWNLOAD_IN_PROGRESS = False

    try:
        print(f"\nRunning post-download validation for: {output_filename}")
        validate_iso_file(output_filename)
        print("ISO validation complete. Ready to boot in QEMU.")
    except ValueError as exc:
        print(f"\nPost-download validation failed: {exc}")
        remove_partial_download(output_filename)
        raise RuntimeError(f"The ISO is incomplete or corrupted: {output_filename}") from exc


class ConsoleOutput:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, text):
        if text:
            self.text_widget.insert(tk.END, text)
            self.text_widget.see(tk.END)
            self.text_widget.update_idletasks()

    def flush(self):
        pass

    def isatty(self):
        return True


class StartupSelector:
    def __init__(self, root):
        self.root = root
        self.mode_choice = None
        self.root.title("WoL Launcher")
        self.root.geometry("720x420")
        self.root.configure(bg=GUI_THEME["bg"])
        self.root.resizable(False, False)

        wrapper = tk.Frame(root, bg=GUI_THEME["bg"], padx=30, pady=30)
        wrapper.pack(fill="both", expand=True)

        title = tk.Label(
            wrapper,
            text="Windows on Linux",
            font=("Segoe UI", 32, "bold"),
            fg=GUI_THEME["white"],
            bg=GUI_THEME["bg"],
            anchor="center",
        )
        title.pack(pady=(0, 10))

        subtitle = tk.Label(
            wrapper,
            text="Choose how you want to launch the setup",
            font=("Segoe UI", 14),
            fg=GUI_THEME["muted"],
            bg=GUI_THEME["bg"],
        )
        subtitle.pack(pady=(0, 20))

        cards = tk.Frame(wrapper, bg=GUI_THEME["bg"])
        cards.pack(fill="both", expand=True)

        gui_card = tk.Frame(cards, bg=GUI_THEME["panel"], padx=20, pady=20, highlightbackground=GUI_THEME["blue"], highlightthickness=2)
        gui_card.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        cli_card = tk.Frame(cards, bg=GUI_THEME["panel"], padx=20, pady=20, highlightbackground=GUI_THEME["blue_light"], highlightthickness=2)
        cli_card.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        tk.Label(gui_card, text="🖥️ GUI MODE", font=("Segoe UI", 18, "bold"), fg=GUI_THEME["white"], bg=GUI_THEME["panel"]).pack(anchor="w", pady=(0, 10))
        tk.Label(gui_card, text="Desktop interface for configuring and launching the VM.", font=("Segoe UI", 11), fg=GUI_THEME["blue_light"], bg=GUI_THEME["panel"], justify="left", wraplength=240).pack(anchor="w")
        gui_btn = tk.Button(gui_card, text="Launch GUI", width=18, height=2, bg=GUI_THEME["blue"], fg=GUI_THEME["white"], activebackground=GUI_THEME["blue_dark"], activeforeground=GUI_THEME["white"], font=("Segoe UI", 11, "bold"), bd=0, command=lambda: self.choice("gui"))
        gui_btn.pack(pady=(18, 0), anchor="w")

        tk.Label(cli_card, text="⌨️ CLI MODE", font=("Segoe UI", 18, "bold"), fg=GUI_THEME["white"], bg=GUI_THEME["panel"]).pack(anchor="w", pady=(0, 10))
        tk.Label(cli_card, text="Classic terminal setup flow with text prompts.", font=("Segoe UI", 11), fg=GUI_THEME["blue_light"], bg=GUI_THEME["panel"], justify="left", wraplength=240).pack(anchor="w")
        cli_btn = tk.Button(cli_card, text="Use CLI", width=18, height=2, bg=GUI_THEME["white"], fg=GUI_THEME["black"], activebackground=GUI_THEME["blue_light"], activeforeground=GUI_THEME["black"], font=("Segoe UI", 11, "bold"), bd=0, command=lambda: self.choice("cli"))
        cli_btn.pack(pady=(18, 0), anchor="w")

    def choice(self, mode):
        self.mode_choice = mode
        self.root.quit()
        self.root.destroy()


class WoLGui:
    def __init__(self, root):
        self.root = root
        self.root.title("WoL Setup")
        self.root.geometry("980x700")
        self.root.minsize(900, 620)
        self.root.configure(bg=GUI_THEME["bg"])

        self.selection_var = tk.StringVar(value="1")
        self.disk_size_var = tk.StringVar(value="20")
        self.ram_size_var = tk.StringVar(value="4")
        self.cpu_var = tk.StringVar(value="2")
        self.exit_action_var = tk.StringVar(value="none")
        self.output_path_var = tk.StringVar(value=DEFAULT_VM_DIR)
        self.custom_iso_var = tk.StringVar(value=(load_config() or {}).get("custom_iso_path", ""))
        self.log_widget = None
        self.launch_thread = None

        self.build_ui()

    def build_ui(self):
        main = tk.Frame(self.root, bg=GUI_THEME["bg"], padx=20, pady=20)
        main.pack(fill="both", expand=True)

        header = tk.Label(
            main,
            text="Windows on Linux VM Builder",
            font=("Segoe UI", 30, "bold"),
            fg=GUI_THEME["white"],
            bg=GUI_THEME["bg"],
        )
        header.pack(anchor="w", pady=(0, 8))

        sub = tk.Label(
            main,
            text="Build your VM! Select a Windows version, configure resources, and launch.",
            font=("Segoe UI", 11),
            fg=GUI_THEME["muted"],
            bg=GUI_THEME["bg"],
        )
        sub.pack(anchor="w", pady=(0, 18))

        content = tk.Frame(main, bg=GUI_THEME["bg"])
        content.pack(fill="both", expand=True)

        left = tk.Frame(content, bg=GUI_THEME["bg"], padx=8, pady=8)
        left.pack(side="left", fill="y")

        right = tk.Frame(content, bg=GUI_THEME["bg"], padx=8, pady=8)
        right.pack(side="right", fill="both", expand=True)

        selector_block = tk.Frame(left, bg=GUI_THEME["panel"], padx=16, pady=16)
        selector_block.pack(fill="x")

        tk.Label(selector_block, text="Windows Target", font=("Segoe UI", 18, "bold"), fg=GUI_THEME["white"], bg=GUI_THEME["panel"]).pack(anchor="w", pady=(0, 12))

        option_data = [
            ("1", "WoL 23H2 x64 (Win 11)", "qemu-system-x86_64"),
            ("2", "WoL 23H2 ARM64 (Win 11)", "qemu-system-aarch64"),
            ("3", "WoL 23H1 x64 (Win 10)", "qemu-system-x86_64"),
            ("4", "WoL 2303 x86 (Win 10)", "qemu-system-x86_64"),
        ]

        for key, label, _ in option_data:
            frame = tk.Frame(selector_block, bg=GUI_THEME["panel"], pady=4)
            frame.pack(fill="x", pady=3)
            tk.Radiobutton(
                frame,
                text=label,
                variable=self.selection_var,
                value=key,
                bg=GUI_THEME["panel"],
                activebackground=GUI_THEME["panel"],
                fg=GUI_THEME["white"],
                selectcolor=GUI_THEME["blue"],
                anchor="w",
                font=("Segoe UI", 10),
            ).pack(anchor="w")

        settings_block = tk.Frame(left, bg=GUI_THEME["panel"], padx=16, pady=16)
        settings_block.pack(fill="x", pady=(16, 0))

        tk.Label(settings_block, text="Settings", font=("Segoe UI", 18, "bold"), fg=GUI_THEME["white"], bg=GUI_THEME["panel"]).pack(anchor="w", pady=(0, 12))

        field_specs = [
            ("Disk size (GB)", self.disk_size_var, "20"),
            ("RAM (GB)", self.ram_size_var, "4"),
            ("CPU cores", self.cpu_var, "2"),
        ]

        for label, var, default in field_specs:
            row = tk.Frame(settings_block, bg=GUI_THEME["panel"])
            row.pack(fill="x", pady=6)
            tk.Label(row, text=label, width=18, fg=GUI_THEME["white"], bg=GUI_THEME["panel"], anchor="w", font=("Segoe UI", 10)).pack(side="left")
            entry = tk.Entry(row, textvariable=var, width=12, bg=GUI_THEME["white"], fg=GUI_THEME["black"], bd=0, insertbackground=GUI_THEME["black"], justify="center")
            entry.pack(side="right")
            var.set(default)

        exit_row = tk.Frame(settings_block, bg=GUI_THEME["panel"])
        exit_row.pack(fill="x", pady=(12, 0))
        tk.Label(exit_row, text="When VM exits", width=18, fg=GUI_THEME["white"], bg=GUI_THEME["panel"], anchor="w", font=("Segoe UI", 10)).pack(side="left")
        choices = [
            ("none", "Nothing"),
            ("shutdown", "Shutdown host"),
            ("restart", "Restart host"),
            ("sleep", "Sleep host"),
        ]
        menu = ttk.Combobox(exit_row, textvariable=self.exit_action_var, values=[value for value, _ in choices], width=13, state="readonly")
        menu.pack(side="right")
        menu.current(0)

        vm_dir_row = tk.Frame(settings_block, bg=GUI_THEME["panel"])
        vm_dir_row.pack(fill="x", pady=(12, 0))
        tk.Label(vm_dir_row, text="VM folder", width=18, fg=GUI_THEME["white"], bg=GUI_THEME["panel"], anchor="w", font=("Segoe UI", 10)).pack(side="left")
        vm_dir_entry = tk.Entry(vm_dir_row, textvariable=self.output_path_var, width=24, bg=GUI_THEME["white"], fg=GUI_THEME["black"], bd=0, insertbackground=GUI_THEME["black"])
        vm_dir_entry.pack(side="right")
        choose_dir_btn = tk.Button(
            vm_dir_row,
            text="Browse",
            bg=GUI_THEME["blue_light"],
            fg=GUI_THEME["black"],
            font=("Segoe UI", 9, "bold"),
            bd=0,
            command=self.choose_vm_directory,
        )
        choose_dir_btn.pack(side="right", padx=(8, 0))

        iso_row = tk.Frame(settings_block, bg=GUI_THEME["panel"])
        iso_row.pack(fill="x", pady=(12, 0))
        tk.Label(iso_row, text="Custom ISO", width=18, fg=GUI_THEME["white"], bg=GUI_THEME["panel"], anchor="w", font=("Segoe UI", 10)).pack(side="left")
        iso_entry = tk.Entry(iso_row, textvariable=self.custom_iso_var, width=24, bg=GUI_THEME["white"], fg=GUI_THEME["black"], bd=0, insertbackground=GUI_THEME["black"])
        iso_entry.pack(side="right")
        choose_iso_btn = tk.Button(
            iso_row,
            text="Browse",
            bg=GUI_THEME["blue_light"],
            fg=GUI_THEME["black"],
            font=("Segoe UI", 9, "bold"),
            bd=0,
            command=self.choose_custom_iso,
        )
        choose_iso_btn.pack(side="right", padx=(8, 0))

        actions = tk.Frame(right, bg=GUI_THEME["bg"], padx=10, pady=10)
        actions.pack(fill="both", expand=True)

        self.log_widget = tk.Text(
            actions,
            height=20,
            bg=GUI_THEME["black"],
            fg=GUI_THEME["white"],
            insertbackground=GUI_THEME["white"],
            font=("Consolas", 10),
            wrap="word",
            padx=12,
            pady=12,
        )
        self.log_widget.pack(fill="both", expand=True)

        self.log_widget.insert(tk.END, "Build your VM! Select a Windows version, configure resources, and launch.\n")
        self.log_widget.configure(state="disabled")

        buttons = tk.Frame(actions, bg=GUI_THEME["bg"])
        buttons.pack(fill="x", pady=(12, 0))

        start_btn = tk.Button(
            buttons,
            text="Build VM",
            bg=GUI_THEME["blue"],
            fg=GUI_THEME["white"],
            activebackground=GUI_THEME["blue_dark"],
            activeforeground=GUI_THEME["white"],
            font=("Segoe UI", 12, "bold"),
            bd=0,
            width=18,
            command=self.start_build_vm,
        )
        start_btn.pack(side="left")

        delete_btn = tk.Button(
            buttons,
            text="Delete VM",
            bg=GUI_THEME["danger"],
            fg=GUI_THEME["white"],
            activebackground="#d94a4a",
            activeforeground=GUI_THEME["white"],
            font=("Segoe UI", 10, "bold"),
            bd=0,
            width=18,
            command=self.delete_saved_vm,
        )
        delete_btn.pack(side="left", padx=(12, 0))

        tk.Button(
            buttons,
            text="Back to mode switch",
            bg=GUI_THEME["white"],
            fg=GUI_THEME["black"],
            activebackground=GUI_THEME["blue_light"],
            activeforeground=GUI_THEME["black"],
            font=("Segoe UI", 10, "bold"),
            bd=0,
            width=18,
            command=self.reload_mode_selector,
        ).pack(side="right")

        self.root.protocol("WM_DELETE_WINDOW", self.safe_close)

    def log(self, message):
        if self.log_widget is None:
            return

        def append():
            self.log_widget.configure(state="normal")
            self.log_widget.insert(tk.END, str(message) + "\n")
            self.log_widget.see(tk.END)
            self.log_widget.configure(state="disabled")

        try:
            self.root.after(0, append)
        except Exception:
            append()

    def choose_vm_directory(self):
        selected_dir = filedialog.askdirectory(title="Select VM folder", initialdir=self.output_path_var.get() or DEFAULT_VM_DIR)
        if selected_dir:
            self.output_path_var.set(selected_dir)

    def choose_custom_iso(self):
        selected_iso = filedialog.askopenfilename(title="Select Windows ISO", filetypes=[("ISO files", "*.iso"), ("All files", "*.*")], initialdir=os.path.expanduser("~/Downloads"))
        if selected_iso:
            self.custom_iso_var.set(selected_iso)

    def safe_close(self):
        self.root.destroy()
        sys.exit(0)

    def delete_saved_vm(self):
        if not os.path.exists(DISK_IMAGE) and not os.path.exists(CONFIG_FILE):
            messagebox.showinfo("No saved VM", "There is no saved VM disk or config to delete.")
            return

        confirm = messagebox.askyesno(
            "Delete saved VM",
            "This will remove the saved VM disk and config for this setup. Continue?",
        )
        if not confirm:
            return

        removed = delete_vm_data()
        if removed:
            self.log(f"Deleted saved VM data: {', '.join(removed)}")
        else:
            self.log("No saved VM data was found to delete.")

    def reload_mode_selector(self):
        self.root.destroy()
        start_mode_selector()

    def start_build_vm(self):
        if self.launch_thread is not None and self.launch_thread.is_alive():
            self.log("A VM build is already running.")
            return

        self.launch_thread = threading.Thread(target=self.launch_vm, daemon=True)
        self.launch_thread.start()

    def launch_vm(self):
        selection = self.selection_var.get()
        if selection == "1":
            ITEM_ID = "tiny-11-NTDEV"
            EXACT_ISO_NAME = "tiny11 23H2 x64.iso"
            OUTPUT_FILE = ISO_PATH_WIN11_X64
            qemu_binary = "qemu-system-x86_64"
        elif selection == "2":
            ITEM_ID = "tiny11a64"
            EXACT_ISO_NAME = "tiny11a64 r1.iso"
            OUTPUT_FILE = ISO_PATH_ARM64
            qemu_binary = "qemu-system-aarch64"
        elif selection == "3":
            ITEM_ID = "tiny-10-NTDEV"
            EXACT_ISO_NAME = "tiny10 23h1 x64.iso"
            OUTPUT_FILE = ISO_PATH_WIN10_X64
            qemu_binary = "qemu-system-x86_64"
        elif selection == "4":
            ITEM_ID = "tiny-10-NTDEV"
            EXACT_ISO_NAME = "tiny10 2303 x86.iso"
            OUTPUT_FILE = ISO_PATH_X86
            qemu_binary = "qemu-system-x86_64"
        else:
            self.root.after(0, lambda: messagebox.showerror("Invalid option", "Select a Windows build first."))
            return

        global DISK_IMAGE

        custom_iso_path = self.custom_iso_var.get().strip()
        use_custom_iso = bool(custom_iso_path)

        disk_size = self.disk_size_var.get().strip() or "20"
        ram_size = self.ram_size_var.get().strip() or "4"
        cpu_cores = self.cpu_var.get().strip() or "2"
        exit_action = self.exit_action_var.get() or "none"
        selected_vm_dir = self.output_path_var.get().strip() or DEFAULT_VM_DIR
        selected_disk_image = get_vm_disk_path(selected_vm_dir)
        DISK_IMAGE = selected_disk_image

        if use_custom_iso and not os.path.exists(custom_iso_path):
            self.root.after(0, lambda: messagebox.showerror("Missing ISO", f"Custom ISO not found:\n{custom_iso_path}"))
            return

        if os.path.exists(DISK_IMAGE):
            self.log("Saved VM detected. Launching existing VM directly.")
            config = load_config() or {}
            qemu_binary = config.get("qemu_binary") or qemu_binary
            ram_size = config.get("ram_size", ram_size)
            cpu_cores = config.get("cpu_cores", cpu_cores)
            exit_action = config.get("exit_action", exit_action)
            try:
                ensure_required_dependencies(qemu_binary, exit_action, gui_mode=True)
            except RuntimeError as exc:
                self.root.after(0, lambda: messagebox.showerror("Missing dependency", str(exc)))
                return
            qemu_binary_path = resolve_executable(qemu_binary) or qemu_binary
            kvm_flags = get_kvm_flags(qemu_binary)
            qemu_cmd = [
                qemu_binary_path,
                *kvm_flags,
                "-m",
                f"{ram_size}G",
                "-smp",
                f"{cpu_cores}",
                "-drive",
                f"file={DISK_IMAGE},if=virtio,format=qcow2",
                "-netdev",
                "user,id=net0",
                "-device",
                "virtio-net-pci,netdev=net0",
                "-boot",
                "order=c",
                *get_qemu_display_args(),
            ]
            self.log("Launching saved VM...")
            print_all_prereqs_passed()
            try:
                launch_vm_process(qemu_cmd, exit_action)
                self.log("Saved VM process started successfully.")
            except Exception as exc:
                self.log(f"Failed to launch saved VM: {exc}")
                return
            return

        self.log(f"Selected build: {selection} | RAM: {ram_size}G | Disk: {disk_size}G | CPU: {cpu_cores}")
        self.log(f"VM folder: {selected_vm_dir} | Disk image: {DISK_IMAGE}")
        self.log(f"Exit action: {exit_action} | QEMU binary: {qemu_binary}")

        if use_custom_iso:
            OUTPUT_FILE = custom_iso_path
            self.log(f"Using custom ISO: {OUTPUT_FILE}")
            self.log("Skipping download of the VirtIO ISO because a custom Windows ISO was selected.")
        else:
            self.log("Check the download progress in the other window. Once the download is complete, the VM will launch automatically.")

        try:
            try:
                ensure_required_dependencies(qemu_binary, exit_action, gui_mode=True)
            except RuntimeError as exc:
                self.root.after(0, lambda: messagebox.showerror("Missing dependency", str(exc)))
                return

            qemu_binary_path = resolve_executable(qemu_binary) or qemu_binary
            qemu_img_path = resolve_executable("qemu-img") or "qemu-img"

            if use_custom_iso:
                validate_iso_file(OUTPUT_FILE)
            else:
                prepare_install_media(
                    ITEM_ID,
                    EXACT_ISO_NAME,
                    OUTPUT_FILE,
                    VIRTIO_ITEM_ID,
                    VIRTIO_ISO_NAME,
                    VIRTIO_ISO_PATH,
                )
                validate_iso_file(OUTPUT_FILE)
                validate_iso_file(VIRTIO_ISO_PATH)

            save_config(qemu_binary, ram_size, cpu_cores, exit_action, vm_dir=selected_vm_dir, custom_iso_path=custom_iso_path)

            if not os.path.exists(DISK_IMAGE):
                self.log(f"Creating disk image: {DISK_IMAGE} ({disk_size}G)")
                subprocess.run([qemu_img_path, "create", "-f", "qcow2", DISK_IMAGE, f"{disk_size}G"], check=True)
            else:
                self.log(f"Using existing disk image: {DISK_IMAGE}")

            kvm_flags = get_kvm_flags(qemu_binary)

            qemu_cmd = [
                qemu_binary_path,
                *kvm_flags,
                "-m",
                f"{ram_size}G",
                "-smp",
                f"{cpu_cores}",
                "-drive",
                f"file={DISK_IMAGE},if=virtio,format=qcow2",
                "-drive",
                f"file={OUTPUT_FILE},media=cdrom,readonly=on",
            ]
            if not use_custom_iso:
                qemu_cmd.extend([
                    "-drive",
                    f"file={VIRTIO_ISO_PATH},media=cdrom,readonly=on",
                ])
            qemu_cmd.extend([
                "-boot",
                "order=c",
                "-netdev",
                "user,id=net0",
                "-device",
                "virtio-net-pci,netdev=net0",
                *get_qemu_display_args(),
            ])

            self.log("Launching QEMU virtual machine...")
            self.log("Note: when Windows prompts for a driver, select the VirtIO CD drive.")
            print_all_prereqs_passed()
            launch_vm_process(qemu_cmd, exit_action)
        except SystemExit:
            self.log("Build cancelled before completion.")
        except Exception as exc:
            self.log(f"Build failed: {exc}")
        finally:
            handle_host_exit_action(exit_action)


def execute_cli_flow():
    print("\nChoose a VM location or accept the default path.")
    default_vm_dir = DEFAULT_VM_DIR
    print(f"Default VM folder: {default_vm_dir}")
    custom_vm_dir = input("Enter VM folder path (leave blank for default): ").strip()
    vm_dir = custom_vm_dir or default_vm_dir
    vm_disk = get_vm_disk_path(vm_dir)
    global DISK_IMAGE
    DISK_IMAGE = vm_disk

    if os.path.exists(DISK_IMAGE):
        print("Saved VM detected!")
        print("1. Launch VM")
        print("2. Delete VM")
        print("3. Exit")
        action = input("Select an option [default: 1]: ").strip().lower()

        if action in {"", "1"}:
            config = load_config()

            if config:
                qemu_binary = config.get("qemu_binary")
                ram_size = config.get("ram_size", "4")
                cpu_cores = config.get("cpu_cores", "2")
                exit_action = config.get("exit_action", "none")
            else:
                host_machine = platform.machine().lower()
                qemu_binary = (
                    "qemu-system-aarch64"
                    if "aarch64" in host_machine
                    else "qemu-system-x86_64"
                )
                ram_size, cpu_cores, exit_action = "4", "2", "none"

            ensure_required_dependencies(qemu_binary, exit_action)

            kvm_flags = get_kvm_flags(qemu_binary)
            qemu_cmd = [
                qemu_binary,
                *kvm_flags,
                "-m",
                f"{ram_size}G",
                "-smp",
                f"{cpu_cores}",
                "-drive",
                f"file={DISK_IMAGE},if=virtio,format=qcow2",
                "-boot",
                "order=c",
                "-netdev",
                "user,id=net0",
                "-device",
                "virtio-net-pci,netdev=net0",
                *get_qemu_display_args(),
            ]
            launch_vm_process(qemu_cmd, exit_action)
            return

        if action == "2":
            confirm = input("Delete the saved VM and its config? (yes/no): ").strip().lower()
            if confirm in {"yes", "y"}:
                removed = delete_vm_data()
                if removed:
                    print(f"Deleted saved VM data: {', '.join(removed)}")
                else:
                    print("No saved VM data was found to delete.")
            else:
                print("Delete cancelled.")
            return

        print("Exiting...")
        return

    print("Welcome to the WoL project (Windows on Linux) setup script.")
    print("_________________________________________________________________")
    print(
        "Supported target architectures: x64, ARM64, x86, and only Windows 10/11"
        " versions are supported."
    )
    print(
        "⚠️  Please install QEMU and KVM on your system before running this script."
        " KVM is only turned on when the host and guest architectures match. If they"
        " differ, the VM will run in emulation mode without KVM, which may be"
        " slower. ⚠️"
    )

    custom_iso_choice = input("Do you want to use a custom Windows ISO file instead of downloading one? (yes/no): ").strip().lower()
    custom_iso_path = ""
    if custom_iso_choice in {"yes", "y"}:
        custom_iso_path = input("Enter the full path to your Windows ISO: ").strip()
        if not custom_iso_path:
            print("No custom ISO path entered. Exiting.")
            return
        if not os.path.exists(custom_iso_path):
            print(f"Custom ISO file not found: {custom_iso_path}")
            return

    selection = input(
        "Please select an option from the list below:\n"
        "1. WoL 23H2 x64 (Windows 11)\n"
        "2. WoL 23H2 ARM64 (Windows 11)\n"
        "3. WoL 23H1 x64 (Windows 10)\n"
        "4. WoL 2303 x86 (Windows 10)\n"
        "5. Exit\n"
    )

    if selection == "1":
        ITEM_ID = "tiny-11-NTDEV"
        EXACT_ISO_NAME = "tiny11 23H2 x64.iso"
        OUTPUT_FILE = ISO_PATH_WIN11_X64
        qemu_binary = "qemu-system-x86_64"
    elif selection == "2":
        ITEM_ID = "tiny11a64"
        EXACT_ISO_NAME = "tiny11a64 r1.iso"
        OUTPUT_FILE = ISO_PATH_ARM64
        qemu_binary = "qemu-system-aarch64"
    elif selection == "3":
        ITEM_ID = "tiny-10-NTDEV"
        EXACT_ISO_NAME = "tiny10 23h1 x64.iso"
        OUTPUT_FILE = ISO_PATH_WIN10_X64
        qemu_binary = "qemu-system-x86_64"
    elif selection == "4":
        ITEM_ID = "tiny-10-NTDEV"
        EXACT_ISO_NAME = "tiny10 2303 x86.iso"
        OUTPUT_FILE = ISO_PATH_X86
        qemu_binary = "qemu-system-x86_64"
    elif selection == "5":
        print("Exiting...")
        return
    else:
        print("Invalid selection. Exiting.")
        return

    ensure_required_dependencies(qemu_binary)
    qemu_binary = resolve_executable(qemu_binary) or qemu_binary

    if custom_iso_path:
        OUTPUT_FILE = custom_iso_path
        print(f"\nUsing custom Windows ISO: {OUTPUT_FILE}")
        validate_iso_file(OUTPUT_FILE)
    elif os.path.exists(OUTPUT_FILE):
        print("\nThis Windows ISO file already exists on your system.")
        proceed = (
            input("Use the existing file? (yes/no) no will redownload the ISO.: ")
            .strip()
            .lower()
        )
        if proceed in {"no", "n"}:
            print("Deleting existing ISO file and downloading a fresh copy...")
            os.remove(OUTPUT_FILE)
            prepare_install_media(ITEM_ID, EXACT_ISO_NAME, OUTPUT_FILE, VIRTIO_ITEM_ID, VIRTIO_ISO_NAME, VIRTIO_ISO_PATH)
        else:
            print("Using existing ISO file. Continuing...")
            prepare_install_media(ITEM_ID, EXACT_ISO_NAME, OUTPUT_FILE, VIRTIO_ITEM_ID, VIRTIO_ISO_NAME, VIRTIO_ISO_PATH)
    else:
        prepare_install_media(ITEM_ID, EXACT_ISO_NAME, OUTPUT_FILE, VIRTIO_ITEM_ID, VIRTIO_ISO_NAME, VIRTIO_ISO_PATH)

    start_vm = (
        input("\nProceed with virtual machine creation? Anything beyond this point may be permanent. (yes/no) no deletes the ISO file, if you do not want this to happen, exit the tab.: ").strip().lower()
    )
    if start_vm != "yes":
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
        else:
            print("The ISO file does not exist.")
        print("Exiting script.")
        return
    if os.path.exists(OUTPUT_FILE):
        try:
            validate_iso_file(OUTPUT_FILE)
            print("Continuing...")
        except ValueError as exc:
            print(f"ISO validation failed: {exc}")
            os.remove(OUTPUT_FILE)
            print("The ISO was removed because it was incomplete or corrupted.")
            return
    else:
        print("ISO file not found. Exiting script in 6 seconds.")
        time.sleep(6)
        return

    disk_size = (
        input("Enter desired disk size in GB [default: 20]: ").strip().rstrip("gG")
        or "20"
    )
    ram_size = (
        input("Enter desired RAM size in GB [default: 4]: ").strip().rstrip("gG")
        or "4"
    )
    cpu_cores = (
        input("Enter desired CPU cores [default: 2]: ").strip() or "2"
    )

    print("\nWhat should the host Linux system do when the VM shuts down?")
    print("1. Nothing (Return to desktop)")
    print("2. Shutdown host")
    print("3. Restart host")
    print("4. Sleep host")
    exit_choice = input("Select an option [default: 1]: ").strip()

    exit_action_map = {
        "1": "none",
        "2": "shutdown",
        "3": "restart",
        "4": "sleep",
    }
    exit_action = exit_action_map.get(exit_choice, "none")

    save_config(qemu_binary, ram_size, cpu_cores, exit_action, custom_iso_path=custom_iso_path)

    if not os.path.exists(DISK_IMAGE):
        qemu_img_path = resolve_executable("qemu-img") or "qemu-img"
        subprocess.run(
            [qemu_img_path, "create", "-f", "qcow2", DISK_IMAGE, f"{disk_size}G"],
            check=True,
        )
    else:
        print(f"\nUsing existing disk image: {DISK_IMAGE}")

    enable_autostart = (
        input("\nLaunch VM automatically on Linux login? (yes/no): ")
        .strip()
        .lower()
    )
    if enable_autostart == "yes":
        create_autostart_entry()

    ensure_required_dependencies(qemu_binary, exit_action)

    kvm_flags = get_kvm_flags(qemu_binary)
    qemu_cmd = [
        qemu_binary,
        *kvm_flags,
        "-m",
        f"{ram_size}G",
        "-smp",
        f"{cpu_cores}",
        "-drive",
        f"file={DISK_IMAGE},if=virtio,format=qcow2",
        "-drive",
        f"file={OUTPUT_FILE},media=cdrom,readonly=on",
    ]
    if not custom_iso_path:
        qemu_cmd.extend([
            "-drive",
            f"file={VIRTIO_ISO_PATH},media=cdrom,readonly=on",
        ])
    qemu_cmd.extend([
        "-boot",
        "order=c",
        "-netdev",
        "user,id=net0",
        "-device",
        "virtio-net-pci,netdev=net0",
        *get_qemu_display_args(),
    ])

    print("Cleaning up...")
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        print("Cleaned up unnecessary files.")
    time.sleep(2)
    print("\nLaunching QEMU virtual machine...")
    if not custom_iso_path:
        print(
            "💡 NOTE: When Windows asks where to install, click 'Load Driver' and select"
            " the VirtIO CD drive."
        )
    else:
        print("💡 NOTE: You selected a custom ISO, so the VirtIO drivers ISO was skipped.")
    print("Waiting 6 seconds before launching the VM for user attention...")
    print_all_prereqs_passed()
    time.sleep(6)
    launch_vm_process(qemu_cmd, exit_action)


def start_mode_selector():
    if tk is None:
        execute_cli_flow()
        return

    root = tk.Tk()
    selector = StartupSelector(root)
    root.mainloop()

    if selector.mode_choice == "gui":
        gui_root = tk.Tk()
        app = WoLGui(gui_root)
        gui_root.mainloop()
    elif selector.mode_choice == "cli":
        execute_cli_flow()


if __name__ == "__main__":
    start_mode_selector()
