![Python](https://img.shields.io/badge/python-3-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-green)
![Stars](https://img.shields.io/github/stars/sandwich-makes-code/WoL?style=social)

# WoL
Windows on Linux without the complicated stuff.

# Before you continue

BEFORE YOU CONTINUE, MAKE SURE YOU DO THESE STEPS.
- Make sure you have a decent Wi-Fi speed to avoid errors.
- You have QEMU and KVM installed.
- You have Python interpreter installed.
- You have tkinkter installed, if not, run this command:
```bash
sudo apt update && sudo apt install python3-tk
```
# Commands
```bash
curl -sSL [https://raw.githubusercontent.com/sandwich-makes-code/WoL/main/linuxWoL.py](https://raw.githubusercontent.com/sandwich-makes-code/WoL/main/linuxWoL.py) -o ~/.local/bin/wol && chmod +x ~/.local/bin/wol
```

Then, run this command inside your terminal.
```bash
wol
```
# App Guide
You'll be greeted with this:


<img width="719" height="418" alt="image" src="https://github.com/user-attachments/assets/dbb996dd-ad56-46b4-b3a1-b6956e7af111" />

Select either CLI or GUI, it's your choice!

# Guide for GUI version
This is the GUI VM builder interface for the app:

<img width="1919" height="1003" alt="image" src="https://github.com/user-attachments/assets/67a751f5-648b-493b-b9b9-376816bd6e45" />

On the top left, there will be buttons for any version of Windows it supports, and on the left center, you can choose your settings such as RAM, CPU cores, disk size, and what happens when the VM exits! Or even choose your own ISO file for it to emulate.
On the bottom center, there will be buttons such as Build VM, Delete VM (only use for corrupted VMs or VMs that you don't care about) and Back to mode switch.
Select your Windows version (e.g. WoL 11 x64) or Custom ISO.

Select your settings, such as 4GB RAM, 2 CPU cores, and 20GB disk size, then press Build VM.
Now it will be building the VM, such as downloading the ISO (ISO download will be skipped when you select a custom ISO.)
Check the terminal window in the background if you're wondering what is going on in the background. (like ISO download percentage.)
The program will work in the background, so sit back and wait. When it is done, it will launch QEMU and may play a noise.
Now it is finished! If you want to load the VM again, select Saved VMs to open and delete the VMs.
It looks like this:

<img width="675" height="420" alt="image" src="https://github.com/user-attachments/assets/95d75c9d-2124-4892-b1f8-0d3a16888063" />


# Guide for CLI version

You will be asked to download a specific version of modified Windows designed for lower-end computers,
So select a version;

(e.g. WoL 23H2 x64 (Windows 11), so select the number 1.)

<img src="gifs/2026-09-03 15-25-11.gif" width="750" alt="Tutorial GIF">


and continue.
Wait until the ISO downloads, it takes around 3̲0̲ ̲~̲ ̲4̲0̲ ̲m̲i̲n̲u̲t̲e̲s̲,
It will also download virtualization technology to make your experience smoother. 

# ISO Setup
Now that the ISO is installed, it automatically runs the next batch of commands. 

It will setup your Windows installation and will ask you if you want it to startup on boot, what it should do when Windows shuts down, etc.
It will make a noise and may speak when the process is done.
Now it is ready!


