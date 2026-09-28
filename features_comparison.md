# Why WoL? (Comparison)

Most scripts that try to do this are either over-engineered messes that crash in the background, or lazy command wrappers that leave you with no internet and no sound out-of-the-box. 

| Feature | `sandwich-makes-code/WoL` | Other Scripts & Broken Wrappers |
| :--- | :--- | :--- |
| **Internet** | **Works instantly (`e1000-82545em`)**.<br>Windows has built-in drivers for this card. You have internet the second you hit the desktop. | **Broken.** Forcing VirtIO cards leaves you completely offline on boot, forcing you to go dig through Device Manager manually. |
| **Sound** | **Works instantly (`ich9-intel-hda`)**.<br>Routes straight through your host's PipeWire/PulseAudio without extra software. | **Silent.** Lazy setups use old audio flags that 64-bit Windows completely ignores, leaving you with zero sound. |
| **Windows 11 Setup** | **Smart default constraints**.<br>Selecting Windows 11 immediately pushes the box to 64GB so Microsoft's installer checks don't block you. | **Installer Crashes.** Static 20GB defaults cause the Windows 11 installer to throw an error and refuse to install. |
| **Code Stability** | **Simple, linear execution**.<br>No messy background tracking loops to desync or lock up your Python threads. | **Brittle.** Trying to handle real-time background tracing loops that constantly freeze the GUI. |
| **Disk Speed** | **Fast VirtIO Engine (`if=virtio`)**.<br>Gets you near-native drive speeds instead of slow hardware throttling. | **Laggy.** Forces you back onto ancient IDE controllers just to get around writing driver documentation. |
| **Interface** | **Clean GUI + Terminal Fallback**.<br>Uses standard `tkinter` but drops back to a raw terminal loop if you run it without a desktop. | **Bloated.** Either has no menu at all, or forces you to install heavy external software frameworks that bloat your disk. |
| **VM Shuts Down** | **Tied to `systemctl`**.<br>Can automatically trigger a safe host shutdown, reboot, or sleep when the VM closes. | **Dead Ends.** Kills the window and drops you at a prompt, leaving you to type host power commands manually. |
