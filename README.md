<div align="center">

# WoL (Windows on Linux)

**Windows on Linux without the complicated stuff.**

[![Python](https://img.shields.io/badge/python-3-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/sandwich-makes-code/WoL?style=social)](https://github.com/sandwich-makes-code/WoL)

<img src="https://raw.githubusercontent.com/sandwich-makes-code/WoL/main/logo/current/Windows%20on%20Linux.png" alt="WoL Logo" width="450"/>

</div>

---

## 📋 Table of Contents
- [Minimum Specifications](#-minimum-specifications)
- [Before You Continue](#-before-you-continue)
- [Installation](#-installation)
  - [Installation via the Releases Tab](#installation-via-the-releases-tab)
  - [Command-Line Installation](#command-line-installation)
- [App Guide](#-app-guide)
  - [Guide for GUI Version](#guide-for-gui-version)
  - [Guide for Legacy Version (1.2 and below)](#guide-for-legacy-version-12-and-below)
  - [ISO Setup](#iso-setup)
- [Windows Setup](#-windows-setup)
  - [Start Screen](#start-screen)
  - [Drive Setup](#drive-setup)
- [License](#-license)
- [Issues](#-issues)

---

## 💻 Minimum Specifications

- At least **8 GB of RAM** for Linux (Windows requires at least 4 GB).
- Recommended disk size of **40 GB** on the host machine (Windows requires at least a virtual disk size of 20 GB).
- Around **4 or 8 CPU cores** (Windows requires at least 2 CPU cores).
- A decent **GPU** of any type.

Check your specifications with this command:
```bash
sudo lshw | less
```

---

## ⚡ Before You Continue

**BEFORE YOU CONTINUE, MAKE SURE YOU DO THESE STEPS:**
- Make sure you have a decent Wi-Fi speed to avoid errors.
- Ensure you have **QEMU** and **KVM** installed.
- Ensure you have the **Python** interpreter installed.
- Ensure you have **tkinter** installed. If not, run this command:
```bash
sudo apt update && sudo apt install python3-tk
```

---

## 🚀 Installation

### Installation via the Releases Tab
Go to the [Releases page](https://github.com/sandwich-makes-code/WoL/releases) then download the newest `.py` or `.zip` file. Both installation methods are documented here.

#### .PY Installation
Run this command so your Linux terminal moves to the Downloads folder (or wherever your `.py` file got saved):
```bash
cd $HOME/Downloads
```
Then run this command inside your terminal:
```bash
python3 linuxWoL.py
```
> The script should launch if you have Python and `tkinter` installed. If not, check the instructions in [Before You Continue](#-before-you-continue).

#### .ZIP Installation
Run this command so your Linux terminal moves to the Downloads folder:
```bash
cd $HOME/Downloads
```
Then, run this command inside your terminal (replace the `X.X`s with the file version name):
```bash
unzip WoL-X.X.zip
```
Run this command so your Linux terminal moves to the unzipped folder:
```bash
cd $HOME/Downloads/WoL-X.X/WoL-X.X/current
```
Now run the Python script:
```bash
python3 linuxWoL.py
```

---

### Command-Line Installation

Run this command inside your terminal:
```bash
curl -sSL [https://raw.githubusercontent.com/sandwich-makes-code/WoL/main/current/linuxWoL.py](https://raw.githubusercontent.com/sandwich-makes-code/WoL/main/current/linuxWoL.py) -o ~/.local/bin/wol && chmod +x ~/.local/bin/wol
```

Then, run this command inside your terminal:
```bash
wol
```

---

## 📖 App Guide

You'll be greeted with this:

<p align="center">
  <img width="719" alt="WoL Launcher Screen" src="https://github.com/user-attachments/assets/dbb996dd-ad56-46b4-b3a1-b6956e7af111" />
</p>

Select either **CLI** or **GUI**, it's your choice!

---

### Guide for GUI Version

This is the GUI VM builder interface for the app:

<p align="center">
  <img width="900" alt="WoL GUI VM Builder Interface" src="https://github.com/user-attachments/assets/ecf2b758-cfee-4fd4-be35-1ec2d1125371" />
</p>

1. **OS / ISO Selection:** On the top left, there will be buttons for any version of Windows it supports. On the left center or bottom panel where it says **Saved ISOs**, you can choose your own ISO file to emulate.
   
   <p align="center">
     <img width="156" alt="Saved ISOs button" src="https://github.com/user-attachments/assets/15425cea-1d70-4a70-812b-d538a211d139" />
     &nbsp;&nbsp;&nbsp;&nbsp;
     <img width="500" alt="Saved ISOs Panel" src="https://github.com/user-attachments/assets/b04c87cc-f477-4dda-a603-5b6653c532cf" />
   </p>

2. **Settings:** Choose your settings such as RAM, CPU cores, disk size, and what happens when the VM exits.
3. **Build VM:** On the bottom center, there will be buttons such as **Build VM**, **Delete VM** (only use for corrupted VMs or VMs that you don't care about), and **Back to mode switch**.
   - Select your Windows version (e.g. WoL 11 x64) or Custom ISO.
   - Select your settings (e.g. 4GB RAM, 2 CPU cores, and 20GB disk size), then press **Build VM**.
   - It will now build the VM, such as downloading the ISO (ISO download will be skipped when you select a custom ISO).
   - Check the terminal window in the background if you're wondering what is going on in the background (like ISO download percentage).
4. **Completion:** The program will work in the background, so sit back and wait. When it is done, it will launch QEMU and may play a noise.
5. **Saved VMs:** If you want to load the VM again, select **Saved VMs** to open and delete the VMs:

   <p align="center">
     <img width="675" alt="Saved VMs Panel" src="https://github.com/user-attachments/assets/95d75c9d-2124-4892-b1f8-0d3a16888063" />
   </p>

---

### Guide for Legacy Version (1.2 and below)

You will be asked to download a specific version of modified Windows designed for lower-end computers, so select a version (e.g. WoL 23H2 x64 (Windows 11), select number `1`) and continue.

<p align="center">
  <img src="gifs/2026-09-03 15-25-11.gif" width="750" alt="Tutorial GIF">
</p>

Wait until the ISO downloads (it takes around 30 ~ 40 minutes). It will also download virtualization technology to make your experience smoother.

---

### ISO Setup

Now that the ISO is installed, it automatically runs the next batch of commands:
- It will set up your Windows installation and will ask you if you want it to startup on boot, what it should do when Windows shuts down, etc.
- It will make a noise and may speak when the process is done. Now it is ready!

---

## 🪟 Windows Setup

### Start Screen
You'll be greeted with the start screen asking your preferences. Select your preferences to continue.

### Drive Setup
Windows cannot read the drives because the drives use a method that isn't supported by Windows by default. Follow these steps:

#### Step 1: Click "Load driver"
On the Windows Setup screen asking **"Where do you want to install Windows?"**, click **Load driver** in the bottom-left corner.

#### Step 2: Browse to the VirtIO CD Drive
In the pop-up prompt, click **Browse**, then expand the virtual CD/DVD drive containing the VirtIO drivers (typically labeled `virtio-win` or assigned drive letter `D:` or `E:`).

#### Step 3: Navigate to the Storage Driver Folder
1. Open the **`viostor`** folder.
2. Select the folder matching your target OS (e.g., **`w11`** for Windows 11, **`w10`** for Windows 10).
3. Select your architecture folder (e.g., **`amd64`** for 64-bit systems).
4. Click **OK**.

#### Step 4: Install the Driver
Highlight **Red Hat VirtIO SCSI Controller** (or **Red Hat VirtIO Block Driver**) from the driver selection list and click **Next**.

---

*Once the driver finishes loading, your virtual disk will appear in the list, allowing you to select it and continue installation as you normally would on a regular setup.*

---

## 📜 License

Distributed under the **GPL-3.0 License**. See [`LICENSE`](LICENSE) for full details.

---

## 🐛 Issues

Please document any issues here: [GitHub Issues](https://github.com/sandwich-makes-code/WoL/issues)