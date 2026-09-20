![Python](https://img.shields.io/badge/python-3-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-green)
![Stars](https://img.shields.io/github/stars/sandwich-makes-code/WoL?style=social)

# WoL
Windows on Linux without the complicated stuff.

## Logo

<img alt=image src=https://github.com/sandwich-makes-code/WoL/blob/main/logo/current/Windows%20on%20Linux.png>

## Minimum specifications
- At least 8 GB of RAM for Linux (Windows requires 4GB of RAM.)
- A recommended disk size of 40 GB (on the host machine, not the guest machine.) (Windows requires at least a virtual disk size of 20 GB.)
- Around 4 or 8 CPU cores (Windows requires at least 2 CPU cores.)
- A decent GPU of any type.
Check your specifications with this command.
```bash
sudo lshw | less
```

## Before you continue

BEFORE YOU CONTINUE, MAKE SURE YOU DO THESE STEPS.
- Make sure you have a decent Wi-Fi speed to avoid errors.
- You have QEMU and KVM installed.
- You have Python interpreter installed.
- You have tkinkter installed, if not, run this command:
```bash
sudo apt update && sudo apt install python3-tk
```
## Installation
### Installation via the Releases tab
Go to the [Releases page](https://github.com/sandwich-makes-code/WoL/releases) then download the newest .PY or .ZIP file, both installation methids will be documented here.
#### .PY installation
Run this command so your Linux terminal moves to the Downloads folder (or wherever your .PY file got saved)
```bash
cd $HOME/Downloads
```
Then run this command inside your terminal.
```bash
python3 linuxWoL.py
```
The script should launch if you have Python and tkinter installed, if not, check if they are installed and if they're not, the instructions are [here](#before-you-continue) and look at the top of the README
#### .ZIP installation
Run this command so your Linux terminal moves to the Downloads folder (or wherever your .ZIP file got saved)
```bash
cd $HOME/Downloads
```
Then, run this command inside your terminal (replace the Xs with the file version name)
```bash
unzip WoL-X.X.zip
```
Run this command so your Linux terminal moves to the unzipped folder (change the Downloads folder to where it got saved, then change the Xs to the file version name)
```bash
cd $HOME/Downloads/WoL-X.X/WoL-X.X/current
```
Now run the Python script.
```bash
python3 linuxWoL.py
```

### Command-line installation
```bash
curl -sSL [https://raw.githubusercontent.com/sandwich-makes-code/WoL/main/current/linuxWoL.py](https://raw.githubusercontent.com/sandwich-makes-code/WoL/main/current/linuxWoL.py) -o ~/.local/bin/wol && chmod +x ~/.local/bin/wol
```

Then, run this command inside your terminal.
```bash
wol
```
# App Guide
You'll be greeted with this:


<img width="719" height="418" alt="image" src="https://github.com/user-attachments/assets/dbb996dd-ad56-46b4-b3a1-b6956e7af111" />

Select either CLI or GUI, it's your choice!

## Guide for GUI version
This is the GUI VM builder interface for the app:

<img width="1918" height="1008" alt="image" src="https://github.com/user-attachments/assets/ecf2b758-cfee-4fd4-be35-1ec2d1125371" />

On the top left, there will be buttons for any version of Windows it supports, and on the left center, you can choose your settings such as RAM, CPU cores, disk size, and what happens when the VM exits! Or even choose your own ISO file for it to emulate with the side panel or the bottom of the window where it says Saved ISOs. It looks like this.
<img width="156" height="34" alt="image" src="https://github.com/user-attachments/assets/15425cea-1d70-4a70-812b-d538a211d139" />
<img width="678" height="415" alt="Screenshot 2026-09-17 192510 png" src="https://github.com/user-attachments/assets/b04c87cc-f477-4dda-a603-5b6653c532cf" />


On the bottom center, there will be buttons such as Build VM, Delete VM (only use for corrupted VMs or VMs that you don't care about) and Back to mode switch.
Select your Windows version (e.g. WoL 11 x64) or Custom ISO.

Select your settings, such as 4GB RAM, 2 CPU cores, and 20GB disk size, then press Build VM.
Now it will be building the VM, such as downloading the ISO (ISO download will be skipped when you select a custom ISO.)
Check the terminal window in the background if you're wondering what is going on in the background. (like ISO download percentage.)
The program will work in the background, so sit back and wait. When it is done, it will launch QEMU and may play a noise.
Now it is finished! If you want to load the VM again, select Saved VMs to open and delete the VMs.
It looks like this:

<img width="675" height="420" alt="image" src="https://github.com/user-attachments/assets/95d75c9d-2124-4892-b1f8-0d3a16888063" />


## Guide for Legacy version (1.2 and below)

You will be asked to download a specific version of modified Windows designed for lower-end computers,
So select a version;

(e.g. WoL 23H2 x64 (Windows 11), so select the number 1.)

<img src="gifs/2026-09-03 15-25-11.gif" width="750" alt="Tutorial GIF">


and continue.
Wait until the ISO downloads, it takes around 3̲0̲ ̲~̲ ̲4̲0̲ ̲m̲i̲n̲u̲t̲e̲s̲,
It will also download virtualization technology to make your experience smoother. 

## ISO Setup
Now that the ISO is installed, it automatically runs the next batch of commands. 

It will setup your Windows installation and will ask you if you want it to startup on boot, what it should do when Windows shuts down, etc.
It will make a noise and may speak when the process is done.
Now it is ready!

## License

GPL-3.0 -- see [LICENSE](LICENSE).
## Issues

Please document any issues here -- [Issues](https://github.com/sandwich-makes-code/WoL/issues)
