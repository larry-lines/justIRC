# JustIRC Release Notes - v1.0.0

**Date:** 11 February 2026

We are proud to announce the release of **JustIRC v1.0.0**. This release marks a significant milestone in providing a secure, end-to-end encrypted IRC client and server, now with robust cross-platform support.

## 🚀 Highlights

### Cross-Platform Deployment
- **Windows Support:** Full support for Windows 10/11 with standalone executables. No Python installation required for end-users.
  - `JustIRC-GUI.exe`: The graphical client.
  - `JustIRC-CLI.exe`: Command-line interface.
  - `JustIRC-Server.exe`: Standalone server executable.
- **Linux Packaging:** Native `.deb` packaging support for Debian/Ubuntu systems.

### 🔒 Security Enhancements
- **Development Hygiene:** Sensitive configuration files (`justirc_config.json`, `server_config.json`) are now strictly excluded from version control.
- **Dependency Isolation:** Build environments are sandboxed.

### 🎨 User Experience
- **Cyber Theme Polish:** Fixed inconsistencies in the "Cyber" theme for a more immersive experience.
- **Documentation:** Comprehensive guides added to `docs/` covering theming, packaging, and architecture.

## 🛠 Technical Changes for Developers

- **Refactoring:** Extracted `ImageTransfer` logic into `image_transfer.py` to resolve circular imports and improve testability.
- **Build System:**
  - Added `MANIFEST.in` for robust packaging.
  - Improved `setup.py` error handling.
  - Enhanced `build-windows.bat` for Wine compatibility to allow building Windows binaries from Linux.
- **Dependencies:** Updated `requirements.txt` to lock core dependencies.

## 📦 Installation

### Windows
Download and run the executable for your preferred interface from the `dist/` directory.

### Linux
Install via pip:
```bash
pip install .
```

Or build a Debian package:
```bash
python3 setup.py --command-packages=stdeb.command bdist_deb
```
