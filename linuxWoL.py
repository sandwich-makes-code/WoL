#!/usr/bin/env python3
import os
import platform
import subprocess
import sys
import time
import urllib.parse
import urllib.request

CONFIG_FILE = "wol_vm.config"
DISK_IMAGE = "WoL_disk.qcow2"
ISO_PATH_X64 = os.path.expanduser("~/Downloads/WoL_x64.iso")
ISO_PATH_ARM64 = os.path.expanduser("~/Downloads/WoL_ARM64.iso")
VIRTIO_ISO_PATH = os.path.expanduser("~/Downloads/virtio-win-0.1.262.iso")
ISO_PATH_X86 = os.path.expanduser("~/Downloads/WoL_x86.iso")

# Updated Internet Archive details for version 0.1.262
VIRTIO_ITEM_ID = "virtio-win-0.1.262"  # or match the exact item ID page name
VIRTIO_ISO_NAME = "virtio-win-0.1.262.iso"


def get_kvm_flags(qemu_binary):
    """Returns KVM and host CPU flags only if host architecture matches guest binary."""
    host_arch = platform.machine().lower()
    is_x86_match = "x86_64" in host_arch and qemu_binary == "qemu-system-x86_64"
    is_arm_match = "aarch64" in host_arch and qemu_binary == "qemu-system-aarch64"

    if is_x86_match or is_arm_match:
        return ["-enable-kvm", "-cpu", "host"]
    print(
        "⚠️ Host and Guest architectures differ. Running in emulation mode"
        " without KVM."
    )
    return []


def create_autostart_entry():
    """Generates a desktop entry in ~/.config/autostart for automatic login boot."""
    autostart_dir = os.path.expanduser("~/.config/autostart")
    os.makedirs(autostart_dir, exist_ok=True)

    script_path = os.path.abspath(__file__)
    desktop_file_path = os.path.join(autostart_dir, "wol_vm.desktop")

    desktop_content = f"""[Desktop Entry]
Type=Application
Name=Windows on Linux VM
Exec=python3 {script_path}
Terminal=false
X-GNOME-Autostart-enabled=true
"""
    with open(desktop_file_path, "w") as f:
        f.write(desktop_content)

    print(f"\n✅ Autostart configuration written to: {desktop_file_path}")


def save_config(qemu_binary):
    """Saves chosen QEMU architecture binary to persist across auto-boots."""
    with open(CONFIG_FILE, "w") as f:
        f.write(qemu_binary)


def load_config():
    """Loads saved QEMU architecture binary if config exists."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return f.read().strip()
    return None


def download_with_eta(item_id, iso_name, output_filename):
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)

    encoded_name = urllib.parse.quote(iso_name)
    direct_url = f"https://archive.org/download/{item_id}/{encoded_name}"

    print(f"Targeting URL: {direct_url}")
    print(f"Saving to: {output_filename}")
    print("Starting download...\n")

    req = urllib.request.Request(
        direct_url, headers={"User-Agent": "Mozilla/5.0"}
    )

    try:
        with urllib.request.urlopen(req) as response, open(
            output_filename, "wb"
        ) as out_file:
            total_size = int(response.getheader("Content-Length", 0))
            downloaded = 0
            CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB chunks
            start_time = time.time()

            while True:
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

                        mb_dl = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        print(
                            f"Progress: {mb_dl:.1f}/{mb_total:.1f} MB"
                            f" ({percent:.1f}%) | Speed: {speed_mbps:.2f} MB/s"
                            f" | ETA: {eta_str}   ",
                            end="\r",
                        )

        print("\n\nDownload complete! File saved successfully.")

    except Exception as e:
        print(f"\nFailed to download: {e}")
        sys.exit(1)


# -------------------------------------------------------------------
# AUTOMATED STARTUP PATH (If VM disk already exists)
# -------------------------------------------------------------------
if os.path.exists(DISK_IMAGE):
    print("Saved VM detected! Launching automatically with VirtIO drivers...")
    qemu_binary = load_config()
    if not qemu_binary:
        host_machine = platform.machine().lower()
        qemu_binary = (
            "qemu-system-aarch64"
            if "aarch64" in host_machine
            else "qemu-system-x86_64"
        )

    kvm_flags = get_kvm_flags(qemu_binary)
    qemu_cmd = [
        qemu_binary,
        *kvm_flags,
        "-m", "4G",
        "-smp", "2",
        "-drive", f"file={DISK_IMAGE},if=virtio,format=qcow2",
        "-netdev", "user,id=net0",
        "-device", "virtio-net-pci,netdev=net0",
        "-full-screen",
    ]
    subprocess.run(qemu_cmd)
    sys.exit()

# -------------------------------------------------------------------
# FIRST-TIME SETUP PATH
# -------------------------------------------------------------------
print("Welcome to the WoL project (Windows on Linux) setup script.")
print("_________________________________________________________________")
print("Supported target architectures: x64, ARM64, x86, and only Windows 10/11 versions are supported.")
print(
    "⚠️ Please install QEMU and KVM on your system before running this script."
    " ⚠️"
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
    OUTPUT_FILE = ISO_PATH_X64
    qemu_binary = "qemu-system-x86_64"
elif selection == "2":
    ITEM_ID = "tiny11a64"
    EXACT_ISO_NAME = "tiny11a64 r1.iso"
    OUTPUT_FILE = ISO_PATH_ARM64
    qemu_binary = "qemu-system-aarch64"
elif selection == "3":
    ITEM_ID = "tiny-10-NTDEV"
    EXACT_ISO_NAME = "tiny10 23h1 x64.iso"
    OUTPUT_FILE = ISO_PATH_X64
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

# Windows ISO Download check
if os.path.exists(OUTPUT_FILE):
    print("\nThis Windows ISO file already exists on your system.")
    proceed = (
        input("Skip downloading and use existing file? (yes/no): ")
        .strip()
        .lower()
    )
    if proceed != "yes":
        print("Exiting script...")
        sys.exit()
else:
    download_with_eta(ITEM_ID, EXACT_ISO_NAME, OUTPUT_FILE)

# VirtIO ISO Download check (Needed for storage/network drivers during Windows setup)
if not os.path.exists(VIRTIO_ISO_PATH):
    print("\nDownloading VirtIO drivers ISO for disk and network performance...")
    download_with_eta(VIRTIO_ITEM_ID, VIRTIO_ISO_NAME, VIRTIO_ISO_PATH)

start_vm = (
    input("\nProceed with virtual machine creation? (yes/no): ").strip().lower()
)
if start_vm != "yes":
    print("Exiting script.")
    sys.exit()

# Gather specs with default fallbacks
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

# Save target architecture configuration for future auto-boots
save_config(qemu_binary)

# Create virtual disk
if not os.path.exists(DISK_IMAGE):
    subprocess.run(
        ["qemu-img", "create", "-f", "qcow2", DISK_IMAGE, f"{disk_size}G"],
        check=True,
    )
else:
    print(f"\nUsing existing disk image: {DISK_IMAGE}")

# Configure login autostart
enable_autostart = (
    input("\nLaunch VM automatically on Linux login? (yes/no): ")
    .strip()
    .lower()
)
if enable_autostart == "yes":
    create_autostart_entry()

# Evaluate KVM support dynamically based on guest/host match
kvm_flags = get_kvm_flags(qemu_binary)

qemu_cmd = [
    qemu_binary,
    *kvm_flags,
    "-m", f"{ram_size}G",
    "-smp", f"{cpu_cores}",
    # VirtIO Primary Storage
    "-drive", f"file={DISK_IMAGE},if=virtio,format=qcow2",
    # Windows Installation Media
    "-drive", f"file={OUTPUT_FILE},media=cdrom",
    # VirtIO Driver Media (Load storage drivers from here during Windows setup)
    "-drive", f"file={VIRTIO_ISO_PATH},media=cdrom",
    "-boot", "d",
    # VirtIO Networking
    "-netdev", "user,id=net0",
    "-device", "virtio-net-pci,netdev=net0",
    "-full-screen",
]

print("\nLaunching QEMU virtual machine...")
print("💡 NOTE: When Windows asks where to install, click 'Load Driver' and select the VirtIO CD drive.")
subprocess.run(qemu_cmd)