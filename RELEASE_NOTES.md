# JustIRC Release Notes

## v1.0.1 - Bug Fix Release

**Date:** 11 February 2026

This is a maintenance release that fixes critical bugs discovered in v1.0.0.

### 🐛 Bug Fixes

#### Client Stability
- **Fixed NameError in Exception Handlers:** Resolved issue where lambda functions in error handlers tried to capture exception variables after they went out of scope. This caused crashes when displaying error messages for:
  - Connection failures
  - PM decryption errors
  - PM sending failures
  - Image transfer errors

#### Server Stability
- **Fixed Syntax Error in Operator Authentication:** Corrected improper escape sequences in operator password request handlers that prevented the server from starting.

#### New Features
- **Unban Command:** Added `/unban` command to allow operators to remove users from channel ban lists.
  - Operator+ permission required
  - Notifies unbanned user and channel members
  - Persists changes to disk

### 📦 Installation

#### Windows
Download and run the executable for your preferred interface from the `dist/` directory:
- `JustIRC-GUI.exe` - Graphical client (15 MB)
- `JustIRC-CLI.exe` - Command-line client (12 MB)
- `JustIRC-Server.exe` - Server executable (8.2 MB)

#### Linux
Standalone executables available in `dist/` directory:
- `JustIRC-GUI` - Graphical client (18 MB)
- `JustIRC-CLI` - Command-line client (14 MB)
- `JustIRC-Server` - Server executable (9.2 MB)

Or install via pip:
```bash
pip install .
```

### 🔄 Upgrading from v1.0.0

Simply replace your existing executables with the new ones. All data files and configurations remain compatible.

---

## v1.0.0 - Initial Release

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
