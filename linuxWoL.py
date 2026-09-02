#!/usr/bin/env python3
import ctypes
import json
import os
import platform
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

CONFIG_FILE = "wol_vm.config"
DISK_IMAGE = "WoL_disk.qcow2"
ISO_PATH_WIN11_X64 = os.path.expanduser("~/Downloads/WoL_Win11_x64.iso")
ISO_PATH_ARM64 = os.path.expanduser("~/Downloads/WoL_ARM64.iso")
ISO_PATH_WIN10_X64 = os.path.expanduser("~/Downloads/WoL_Win10_x64.iso")
ISO_PATH_X86 = os.path.expanduser("~/Downloads/WoL_x86.iso")
VIRTIO_ISO_PATH = os.path.expanduser("~/Downloads/virtio-win-0.1.262.iso")

VIRTIO_ITEM_ID = "virtio-win-0.1.262"
VIRTIO_ISO_NAME = "virtio-win-0.1.262.iso"
DOWNLOAD_IN_PROGRESS = False
CTRL_CLOSE_EVENT = 2


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


def play_vm_launch_notification():
    # Plays a bell and tries to speak a status message for the VM launch.
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
    # Executes the chosen host system action after the VM exits.
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


def save_config(qemu_binary, ram_size, cpu_cores, exit_action):
    # Saves chosen binary, specs, and exit action to persist across auto-boots.
    config_data = {
        "qemu_binary": qemu_binary,
        "ram_size": ram_size,
        "cpu_cores": cpu_cores,
        "exit_action": exit_action,
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f)


def load_config():
    # Loads saved VM specs if config exists.
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            content = f.read().strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {
                    "qemu_binary": content,
                    "ram_size": "4",
                    "cpu_cores": "2",
                    "exit_action": "none",
                }
    return None


def clear_terminal():
    # Clears the terminal before printing a fresh download progress line.
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


def print_linux_readiness_report(qemu_binary):
    """Shows the Linux VM prerequisites and any missing KVM access information."""
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

    groups = set()
    try:
        groups = set(subprocess.check_output(["groups"], text=True).split())
    except Exception:
        groups = set()

    if "kvm" in groups:
        print(" - user group membership: member of kvm group")
    else:
        print(" - user group membership: not in kvm group")

    if not shutil.which("systemctl"):
        print(" - init system: non-systemd fallback mode enabled")


def ensure_required_dependencies(qemu_binary, exit_action="none"):
    """Verifies the required runtime tools are installed before starting the VM."""
    if os.name == "nt":
        return

    print_linux_readiness_report(qemu_binary)

    required = ["qemu-img", qemu_binary]
    if exit_action in {"shutdown", "restart", "sleep"}:
        required.append("systemctl")

    missing = [cmd for cmd in required if shutil.which(cmd) is None]
    if not missing:
        return

    missing_list = ", ".join(missing)
    print(f"\nMissing required dependency/dependencies: {missing_list}")
    print("Install them before continuing, for example:")
    print("  sudo apt install qemu-system-x86 qemu-utils systemd")
    print("  # or on Fedora/RHEL: sudo dnf install qemu-system-x86 qemu-img systemd")
    print("  # or on Arch: sudo pacman -S qemu-system-x86 qemu-img systemd")
    sys.exit(1)


def monitor_download_cancel(cancel_flag):
    """Listens for user input and sets a cancel flag when they press c or q."""
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


def download_with_eta(item_id, iso_name, output_filename):
    global DOWNLOAD_IN_PROGRESS

    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    install_console_close_guard()

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
                    CHUNK_SIZE = 10 * 1024 * 1024
                    start_time = time.time()

                    while True:
                        if cancel_flag[0]:
                            raise KeyboardInterrupt

                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break

                        out_file.write(chunk)
                        downloaded += len(chunk)

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
                CHUNK_SIZE = 10 * 1024 * 1024
                start_time = time.time()

                while True:
                    if cancel_flag[0]:
                        raise KeyboardInterrupt

                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    out_file.write(chunk)
                    downloaded += len(chunk)

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
        if os.path.exists(output_filename):
            os.remove(output_filename)
        print("\nDownload cancelled by user. Partial file removed.")
        sys.exit(0)
    except Exception as e:
        print(f"\nFailed to download: {e}")
        sys.exit(1)
    finally:
        DOWNLOAD_IN_PROGRESS = False


# -------------------------------------------------------------------
# AUTOMATED STARTUP PATH (If VM disk already exists)
# -------------------------------------------------------------------
if os.path.exists(DISK_IMAGE):
    print("Saved VM detected! Launching automatically with VirtIO drivers...")
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
        "-netdev",
        "user,id=net0",
        "-device",
        "virtio-net-pci,netdev=net0",
        "-full-screen",
    ]
    subprocess.run(qemu_cmd)
    handle_host_exit_action(exit_action)
    sys.exit()

# -------------------------------------------------------------------
# FIRST-TIME SETUP PATH
# -------------------------------------------------------------------
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
    sys.exit()
else:
    print("Invalid selection. Exiting.")
    sys.exit()

ensure_required_dependencies(qemu_binary)

if os.path.exists(OUTPUT_FILE):
    print("\nThis Windows ISO file already exists on your system.")
    proceed = (
        input("Use the existing file? (yes/no) no will redownload the ISO.: ")
        .strip()
        .lower()
    )
    if proceed in {"no", "n"}:
        print("Deleting existing ISO file and downloading a fresh copy...")
        os.remove(OUTPUT_FILE)
        download_with_eta(ITEM_ID, EXACT_ISO_NAME, OUTPUT_FILE)
    else:
        print("Using existing ISO file. Continuing...")
else:
    download_with_eta(ITEM_ID, EXACT_ISO_NAME, OUTPUT_FILE)

if not os.path.exists(VIRTIO_ISO_PATH):
    print("\nDownloading VirtIO drivers ISO for disk and network performance...")
    download_with_eta(VIRTIO_ITEM_ID, VIRTIO_ISO_NAME, VIRTIO_ISO_PATH)

start_vm = (
    input("\nProceed with virtual machine creation? Anything beyond this point may be permanent. (yes/no) no deletes the ISO file, if you do not want this to happen, exit the tab.: ").strip().lower()
)
if start_vm != "yes":
    # Deletes the ISO file and exits the tab.
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    else:
        print("The ISO file does not exist.")
    print("Exiting script.")
    sys.exit()
if os.path.exists(OUTPUT_FILE):
    print("Continuing...")
else: 
    print("ISO file not found. Exiting script in 6 seconds.")
    time.sleep(6)
    sys.exit()

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
    "4": "sleep"
}
exit_action = exit_action_map.get(exit_choice, "none")

save_config(qemu_binary, ram_size, cpu_cores, exit_action)

if not os.path.exists(DISK_IMAGE):
    subprocess.run(
        ["qemu-img", "create", "-f", "qcow2", DISK_IMAGE, f"{disk_size}G"],
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
    f"file={OUTPUT_FILE},media=cdrom",
    "-drive",
    f"file={VIRTIO_ISO_PATH},media=cdrom",
    "-boot",
    "d",
    "-netdev",
    "user,id=net0",
    "-device",
    "virtio-net-pci,netdev=net0",
    "-full-screen",
]

print("\nLaunching QEMU virtual machine...")
print(
    "💡 NOTE: When Windows asks where to install, click 'Load Driver' and select"
    " the VirtIO CD drive."
)
print("Waiting 6 seconds before launching the VM for user attention...")
print_all_prereqs_passed()
time.sleep(6)
subprocess.run(qemu_cmd)
handle_host_exit_action(exit_action)
sys.exit()