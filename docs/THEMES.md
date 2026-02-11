# JustIRC Themes & Branding

## 🛡️ Logo Design

The JustIRC logo features a **cyber security shield** design with:
- **Hexagonal shield shape** representing protection and security
- **Blue-to-green gradient** symbolizing technology and encryption
- **Circuit-like connections** around the edges suggesting network connectivity
- **Center "C" symbol** for "Cryptography" or "Communication"

The logo appears in:
- Window icon (taskbar/title bar)
- About dialog with animated shield
- Application title with shield emoji 🛡️

## Available Themes

### 1. **Dark Theme** (Default)
Classic dark mode with VS Code-inspired colors:
- **Background**: `#2b2b2b` (dark gray)
- **Chat**: `#1e1e1e` (darker gray)
- **Accent**: `#0078d4` (blue)
- **Highlights**: Teal, pink, yellow tones

Best for: Extended use, low-light environments

---

### 2. **Light Theme**
Clean, bright interface:
- **Background**: `#f0f0f0` (light gray)
- **Chat**: `#ffffff` (white)
- **Accent**: `#0078d4` (blue)
- **Highlights**: Purple, orange, blue tones

Best for: Daytime use, bright environments

---

### 3. **Classic Theme**
Traditional IRC/retro computing look:
- **Background**: `#c0c0c0` (silver)
- **Chat**: `#ffffff` (white)
- **Accent**: `#000080` (navy)
- **Highlights**: Pure colors (red, blue, green, yellow, magenta)

Best for: Nostalgia, vintage IRC experience

---

### 4. **🛡️ Cyber Theme** ⭐ NEW
Modern cybersecurity-inspired design matching the logo:

#### Color Palette
| Element | Color | Hex Code | Usage |
|---------|-------|----------|-------|
| **Background** | Dark Navy | `#0a1929` | Main window background |
| **Chat BG** | Navy | `#1a2332` | Chat display area |
| **Input BG** | Steel Blue | `#243447` | Message entry field |
| **Accent** | Blue | `#2196F3` | Buttons, highlights |
| **Success** | Green | `#4CAF50` | Success messages |
| **Channel** | Lime Green | `#76FF03` | Channel messages |
| **PM** | Cyan | `#00BCD4` | Private messages |
| **Action** | Light Green | `#66BB6A` | /me action text |
| **Error** | Red | `#ff5252` | Error messages |
| **Info** | Light Blue | `#64B5F6` | Info messages |
| **System** | Gray | `#78909c` | Join/leave notifications |
| **Highlight** | Dark Blue | `#0d47a1` | Selected text |

#### Design Features
- **Blue-to-green gradient** inspired by the logo
- **High contrast** for readability in secure environments
- **Modern flat design** with subtle borders
- **Circuit/tech aesthetic** matching the shield logo

Best for: Security-conscious users, modern look, matching brand identity

---

## Changing Themes

### Via GUI
1. Click **File → Settings** (or press corresponding menu shortcut)
2. Select the **Theme** tab
3. Choose your preferred theme:
   - Dark - Classic dark mode
   - Light - Bright clean interface
   - Classic - Traditional IRC look
   - 🛡️ Cyber - Security-themed (Blue/Green)
4. Click **Apply** to see changes immediately

### Via Config File
Edit `~/.config/justirc/justirc_config.json`:

```json
{
  "theme": "cyber"
}
```

Valid values: `"dark"`, `"light"`, `"classic"`, `"cyber"`

---

## Theme Customization

### Font Settings
All themes support custom fonts:
- **Font Family**: Default is "Consolas" (monospace recommended)
- **Font Size**: Adjustable from 8-16pt (default: 10pt)

Configure in **Settings → Font** tab or edit config:

```json
{
  "font": {
    "family": "Consolas",
    "size": 10,
    "chat_size": 10
  }
}
```

### UI Options
Additional customization options:
- **Show Timestamps**: Display [HH:MM:SS] on messages
- **Show Join/Leave**: Display user join/leave notifications
- **Enable Sounds**: Audio notifications for events

Configure in **Settings → UI Options** tab

---

## Creating Custom Themes

To add your own theme, edit `config_manager.py`:

```python
"my_theme": {
    "bg": "#hexcolor",           # Main background
    "fg": "#hexcolor",           # Main text color
    "chat_bg": "#hexcolor",      # Chat area background
    "chat_fg": "#hexcolor",      # Chat text color
    "input_bg": "#hexcolor",     # Input field background
    "input_fg": "#hexcolor",     # Input text color
    "accent": "#hexcolor",       # Buttons, accents
    "info": "#hexcolor",         # Info messages
    "error": "#hexcolor",        # Error messages
    "success": "#hexcolor",      # Success messages
    "pm": "#hexcolor",           # Private messages
    "channel": "#hexcolor",      # Channel messages
    "system": "#hexcolor",       # System messages
    "action": "#hexcolor",       # /me actions
    "highlight": "#hexcolor"     # Highlighted text
}
```

Then add the theme name to the selection list in `client_gui.py`.

---

## Theme Preview

### Cyber Theme Screenshot Description
```
┌─────────────────────────────────────────────┐
│ 🛡️ JustIRC - Secure Encrypted IRC         │  ← Dark navy header
├─────────────────────────────────────────────┤
│ File  Help                                  │
├──────┬──────────────────────────────┬───────┤
│📁 Ch │ 💭 Chat Display              │👥 Usr │
│annls │                              │ List  │
│      │ [#general] Alice: Hey!      │       │  ← Lime green channel msg
│#gen  │ * Bob waves                 │       │  ← Light green action
│#tech │ [PM from Carol] Hi there    │       │  ← Cyan PM
│      │ System: Bob joined          │       │  ← Gray system msg
│      │                              │ Alice │
│      │                              │ Bob   │
│      │                              │ Carol │
├──────┴──────────────────────────────┴───────┤
│ Message: ____________________________  Send │  ← Steel blue input
└─────────────────────────────────────────────┘
         Blue #2196F3 to Green #4CAF50 gradient
```

---

## Accessibility

All themes are designed with accessibility in mind:
- **Sufficient contrast ratios** for text readability
- **Color-blind friendly** with non-color indicators
- **Scalable fonts** from 8-16pt
- **Clear visual hierarchy** with semantic colors

The **Cyber theme** specifically uses:
- Blue/Green: High contrast against dark navy
- Lime green: Maximum visibility for important messages
- Distinct colors: Each message type has unique hue

---

## Technical Details

### Implementation
- **Config Manager**: `config_manager.py` - Theme definitions
- **GUI Client**: `client_gui.py` - Theme application
- **Logo Icon**: Generated programmatically using Tkinter PhotoImage
- **About Dialog**: Custom shield logo with Canvas drawing

### Theme Application
Themes are applied via:
1. `apply_theme()` method updates all widget colors
2. Text tags for chat display (`tag_config()`)
3. TTK style configuration for widgets
4. Dynamic color loading from config

### Performance
- Themes switch instantly (< 100ms)
- No image assets required (pure code generation)
- Minimal memory footprint
- GPU-accelerated rendering (system-dependent)

---

## Support

For questions or custom theme requests:
- Check the GitHub repository
- Review the source code in `config_manager.py`
- Experiment with your own color schemes!

**Remember**: The cyber theme represents the security and encryption at the heart of JustIRC! 🛡️🔐
