# JustIRC Packaging Guide

This guide explains how to package JustIRC for distribution as standalone executables that don't require Python or dependencies to be installed.

## 📦 Available Packages

- **Windows**: `.exe` executables (single-file)
- **Linux**: `.deb` package (Debian/Ubuntu)
- **Cross-platform**: Python wheel package

## 🪟 Windows Packaging (.exe)

### Prerequisites
- Python 3.8 or higher
- Git Bash or Windows Terminal

### Build Process

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone <repository-url>
   cd justIRC
   ```

2. **Run the build script**:
   ```batch
   build-windows.bat
   ```

3. **Find your executables**:
   ```
   dist/
   ├── JustIRC-GUI.exe      (GUI client - 15-20 MB)
   ├── JustIRC-CLI.exe      (CLI client - 12-15 MB)
   └── JustIRC-Server.exe   (Server - 12-15 MB)
   ```

### Distribution

The `.exe` files are **completely standalone**:
- ✅ No Python installation needed
- ✅ No dependencies needed
- ✅ Just double-click to run
- ✅ Can be copied to any Windows PC

### Manual Build (Alternative)

If you want to customize the build:

```bash
# Install PyInstaller
pip install pyinstaller

# Build GUI client
pyinstaller justirc-gui.spec

# Build CLI client
pyinstaller justirc-cli.spec
```

## 🐧 Linux Packaging (.deb)

### Prerequisites
- Linux (Debian/Ubuntu-based)
- Python 3.8 or higher
- Build tools

### Build Process

1. **Make the script executable**:
   ```bash
   chmod +x build-linux.sh
   ```

2. **Run the build script**:
   ```bash
   ./build-linux.sh
   ```

   The script will:
   - Install build dependencies (`python3-stdeb`, `dh-python`, `python3-tk`)
   - Create a virtual environment
   - Build the .deb package

3. **Find your package**:
   ```
   deb_dist/python3-justirc_1.0.0-1_all.deb
   ```

### Installation

```bash
# Install the package
sudo dpkg -i deb_dist/python3-justirc_*.deb

# Fix any missing dependencies
sudo apt-get install -f
```

### Usage After Installation

```bash
# GUI Client
justirc-gui

# CLI Client
justirc-cli --server localhost --port 6667 --nickname YourName

# Server
justirc-server --host 0.0.0.0 --port 6667
```

### Uninstall

```bash
sudo apt-get remove python3-justirc
```

## 🍎 macOS Packaging

### Using PyInstaller (Recommended)

```bash
# Install dependencies
pip install pyinstaller

# Build GUI app bundle
pyinstaller --name "JustIRC" \
    --onefile \
    --windowed \
    --icon=JUSTIRC-logo.png \
    --add-data "JUSTIRC-logo.png:." \
    client_gui.py

# Result: dist/JustIRC.app
```

The `.app` bundle can be distributed as a DMG:

```bash
# Install create-dmg
brew install create-dmg

# Create DMG
create-dmg \
    --volname "JustIRC Installer" \
    --window-size 600 400 \
    --icon-size 100 \
    --app-drop-link 400 200 \
    "JustIRC-Installer.dmg" \
    "dist/JustIRC.app"
```

## 🐍 Python Wheel Package

For users who have Python installed:

```bash
# Build wheel
python setup.py bdist_wheel

# Result: dist/justirc-1.0.0-py3-none-any.whl

# Install
pip install dist/justirc-1.0.0-py3-none-any.whl
```

## 📦 Package Contents

All packages include:
- ✅ Client GUI (Tkinter-based)
- ✅ Client CLI (Terminal-based)
- ✅ Server
- ✅ All cryptography libraries
- ✅ Logo and documentation
- ✅ Configuration management

## 🔍 Package Sizes

| Package Type | Size | Notes |
|--------------|------|-------|
| Windows .exe (GUI) | ~15-20 MB | Single file, no dependencies |
| Windows .exe (CLI) | ~12-15 MB | Smaller, no GUI libs |
| Linux .deb | ~5-8 MB | Requires system Python |
| Python wheel | ~50 KB | Requires dependencies |

## 🚀 Quick Build Comparison

| Platform | Command | Output | Time |
|----------|---------|--------|------|
| Windows | `build-windows.bat` | 3 .exe files | ~2-3 min |
| Linux | `./build-linux.sh` | 1 .deb file | ~3-5 min |
| macOS | PyInstaller + create-dmg | .dmg installer | ~3-4 min |

## 🛠️ Advanced Configuration

### Customizing PyInstaller Builds

Edit `justirc-gui.spec` or `justirc-cli.spec`:

```python
# Add more data files
datas=[
    ('JUSTIRC-logo.png', '.'),
    ('custom-theme.json', '.'),
],

# Add hidden imports if needed
hiddenimports=['module_name'],

# Optimize with UPX compression
upx=True,
```

### Customizing .deb Package

Edit `setup.py`:

```python
# Change version
version='1.0.1',

# Add scripts
scripts=['justirc-launcher.sh'],

# Add desktop entry
data_files=[
    ('share/applications', ['justirc.desktop']),
    ('share/icons', ['JUSTIRC-logo.png']),
],
```

## 📋 Build Requirements

### Windows
- Python 3.8+
- pip
- PyInstaller 5.0+

### Linux
- Python 3.8+
- pip
- python3-stdeb
- dh-python
- python3-tk
- dpkg-dev

### Install Build Dependencies

**Windows:**
```batch
pip install pyinstaller
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install -y python3-stdeb dh-python python3-tk
pip install pyinstaller  # Optional, for PyInstaller builds
```

**macOS:**
```bash
brew install python-tk
pip install pyinstaller
```

## 🐛 Troubleshooting

### Windows: "Missing DLL" Error
- Install Visual C++ Redistributable 2015-2022
- Try building with `--onedir` instead of `--onefile`

### Linux: "Package not found" During Build
```bash
sudo apt-get install -f
sudo apt-get install python3-dev
```

### macOS: "App is damaged" Warning
```bash
# Remove quarantine attribute
xattr -cr dist/JustIRC.app
```

### Large Executable Size
- Use `--exclude-module` for unused libraries
- Enable UPX compression: `--upx-dir=/path/to/upx`
- Build with `--strip` option (Linux/macOS)

## 📤 Distribution Checklist

Before distributing:

- [ ] Test executable on clean system (no Python/dependencies)
- [ ] Include README.md and LICENSE
- [ ] Test connection to server
- [ ] Verify all features work (chat, images, channels)
- [ ] Check theme switching works
- [ ] Verify connection timeout (10 seconds)
- [ ] Test on target OS version
- [ ] Include changelog/version info

## 🔐 Code Signing (Optional)

### Windows
```bash
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com JustIRC-GUI.exe
```

### macOS
```bash
codesign --force --deep --sign "Developer ID Application: Your Name" dist/JustIRC.app
```

### Linux
```bash
debsigs --sign=origin --default-key=KEYID package.deb
```

## 📊 Testing Packaged Applications

```bash
# Test GUI on clean system
./JustIRC-GUI.exe  # Windows
./JustIRC          # Linux/macOS

# Test CLI
./JustIRC-CLI.exe --server localhost --port 6667 --nickname TestUser

# Test server
./JustIRC-Server.exe --host 0.0.0.0 --port 6667

# Verify connection timeout (should timeout in 10 seconds)
./JustIRC-CLI.exe --server 192.0.2.1 --port 9999 --nickname Test
```

## 🎯 Continuous Integration

Add to GitHub Actions `.github/workflows/build.yml`:

```yaml
name: Build Packages

on: [push, pull_request]

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pyinstaller
      - run: build-windows.bat
      - uses: actions/upload-artifact@v2
        with:
          name: windows-executables
          path: dist/*.exe

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: ./build-linux.sh
      - uses: actions/upload-artifact@v2
        with:
          name: linux-deb-package
          path: deb_dist/*.deb
```

## 📚 Additional Resources

- [PyInstaller Documentation](https://pyinstaller.readthedocs.io/)
- [stdeb Documentation](https://github.com/astraw/stdeb)
- [Python Packaging Guide](https://packaging.python.org/)

---

**Ready to package?** Choose your platform and run the appropriate build script! 🚀
