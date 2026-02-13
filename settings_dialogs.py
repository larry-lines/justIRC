"""
Settings and Help Dialogs
Handles settings UI and help text display
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox


class SettingsDialogs:
    """Static methods for settings and help dialogs"""
    
    @staticmethod
    def show_settings(root, config, history, chat_display, apply_theme_callback):
        """Show settings dialog
        
        Args:
            root: Parent window
            config: ConfigManager instance
            history: MessageHistory instance or None
            chat_display: Chat display widget
            apply_theme_callback: Callback to apply theme changes
        """
        dialog = tk.Toplevel(root)
        dialog.title("Settings")
        dialog.geometry("450x500")
        dialog.transient(root)
        dialog.grab_set()
        
        # Apply theme colors
        colors = config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Theme tab
        theme_frame = ttk.Frame(notebook, padding=20)
        notebook.add(theme_frame, text="Theme")
        
        ttk.Label(theme_frame, text="Select Theme:", font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        current_theme = config.get("theme", default="dark")
        theme_var = tk.StringVar(value=current_theme)
        
        theme_descriptions = {
            "dark": "Dark - Classic dark mode",
            "light": "Light - Bright clean interface",
            "classic": "Classic - Traditional IRC look",
            "cyber": "🛡️ Cyber - Security-themed",
            "custom": "🎨 Custom - User defined colors"
        }
        
        for theme_name in ["dark", "light", "classic", "cyber", "custom"]:
            ttk.Radiobutton(
                theme_frame,
                text=theme_descriptions[theme_name],
                variable=theme_var,
                value=theme_name
            ).pack(anchor=tk.W, pady=5)
            
        # Custom Colors Button
        def convert_color(prompt_title, initial_color):
            try:
                from tkinter.colorchooser import askcolor
                color = askcolor(color=initial_color, title=prompt_title)
                return color[1] if color[1] else initial_color
            except:
                return initial_color

        def open_custom_theme_editor():
            if theme_var.get() != 'custom':
                messagebox.showinfo("Info", "Select 'Custom' theme first to edit colors.")
                return
                
            editor = tk.Toplevel(dialog)
            editor.title("Custom Theme Editor")
            editor.geometry("400x500")
            editor.config(bg=colors['bg'])
            
            # Load current custom colors
            current_custom = config.get("colors", "custom")
            if not current_custom:
                current_custom = config.get("colors", "dark").copy()
            
            # Helper to create color picker row
            def create_picker(parent, name, key):
                f = ttk.Frame(parent)
                f.pack(fill=tk.X, pady=2)
                ttk.Label(f, text=name, width=20).pack(side=tk.LEFT)
                
                btn = tk.Button(f, bg=current_custom.get(key, '#000000'), width=10)
                
                def pick():
                    new_c = convert_color(f"Pick {name}", current_custom.get(key, '#000000'))
                    current_custom[key] = new_c
                    btn.config(bg=new_c)
                    
                btn.config(command=pick)
                btn.pack(side=tk.RIGHT)
                
            scroll_frame = ttk.Frame(editor)
            scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            keys_to_edit = [
                ("Background", "bg"), ("Foreground", "fg"),
                ("Chat BG", "chat_bg"), ("Chat FG", "chat_fg"),
                ("Accent", "accent"), ("Input BG", "input_bg"),
                ("Info Text", "info"), ("Error Text", "error"),
                ("Success Text", "success")
            ]
            
            for label, key in keys_to_edit:
                create_picker(scroll_frame, label, key)
                
            def save_custom():
                config.set("colors", "custom", value=current_custom)
                messagebox.showinfo("Saved", "Custom colors saved. Apply theme to see changes.")
                editor.destroy()
                
            ttk.Button(editor, text="Save Custom Colors", command=save_custom).pack(pady=10)

        editor_btn = ttk.Button(theme_frame, text="Customize Colors...", command=open_custom_theme_editor)
        editor_btn.pack(anchor=tk.W, pady=10)
        
        # Font tab
        font_frame = ttk.Frame(notebook, padding=20)
        notebook.add(font_frame, text="Font")
        
        ttk.Label(font_frame, text="Font Family:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        font_family_var = tk.StringVar(value=config.get("font", "family", default="Consolas"))
        font_entry = ttk.Entry(font_frame, textvariable=font_family_var, width=30)
        font_entry.pack(anchor=tk.W, pady=(0, 15))
        
        ttk.Label(font_frame, text="Chat Font Size:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        font_size_var = tk.IntVar(value=config.get("font", "chat_size", default=10))
        ttk.Scale(
            font_frame,
            from_=8,
            to=16,
            variable=font_size_var,
            orient=tk.HORIZONTAL,
            length=200
        ).pack(anchor=tk.W)
        
        # UI Options tab
        ui_frame = ttk.Frame(notebook, padding=20)
        notebook.add(ui_frame, text="UI Options")
        
        timestamps_var = tk.BooleanVar(value=config.get("ui", "show_timestamps", default=True))
        join_leave_var = tk.BooleanVar(value=config.get("ui", "show_join_leave", default=True))
        
        ttk.Checkbutton(ui_frame, text="Show timestamps", variable=timestamps_var).pack(anchor=tk.W, pady=5)
        ttk.Checkbutton(ui_frame, text="Show join/leave messages", variable=join_leave_var).pack(anchor=tk.W, pady=5)
        
        ttk.Label(ui_frame, text="Inactivity Timeout (minutes):", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(15, 5))
        timeout_var = tk.IntVar(value=config.get("ui", "inactivity_timeout", default=3600) // 60)
        timeout_frame = ttk.Frame(ui_frame)
        timeout_frame.pack(anchor=tk.W)
        ttk.Scale(
            timeout_frame,
            from_=1,
            to=120,
            variable=timeout_var,
            orient=tk.HORIZONTAL,
            length=200
        ).pack(side=tk.LEFT)
        timeout_label = ttk.Label(timeout_frame, text=f"{timeout_var.get()} min")
        timeout_label.pack(side=tk.LEFT, padx=10)
        
        def update_timeout_label(*args):
            timeout_label.config(text=f"{timeout_var.get()} min")
        timeout_var.trace('w', update_timeout_label)
        
        # History tab
        history_frame = ttk.Frame(notebook, padding=20)
        notebook.add(history_frame, text="History")
        
        ttk.Label(history_frame, text="Message History:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        history_enabled_var = tk.BooleanVar(value=config.get("history", "enabled", default=False))
        history_encrypted_var = tk.BooleanVar(value=config.get("history", "encrypted", default=False))
        
        ttk.Checkbutton(history_frame, text="Enable message history", variable=history_enabled_var).pack(anchor=tk.W, pady=5)
        ttk.Checkbutton(history_frame, text="Encrypt history (requires password)", variable=history_encrypted_var).pack(anchor=tk.W, pady=5)
        
        ttk.Label(history_frame, text="History password (optional):", font=('Arial', 9)).pack(anchor=tk.W, pady=(10, 5))
        history_password_var = tk.StringVar(value=config.get("history", "password", default=""))
        history_password_entry = ttk.Entry(history_frame, textvariable=history_password_var, show="*", width=30)
        history_password_entry.pack(anchor=tk.W)
        
        ttk.Label(
            history_frame, 
            text="Note: Restart required for history changes to take effect.",
            font=('Arial', 8, 'italic'),
            foreground="gray"
        ).pack(anchor=tk.W, pady=(10, 0))
        
        # Show history stats if enabled
        if history:
            stats = history.get_statistics()
            stats_text = f"\nCurrent History Stats:\n"
            stats_text += f"  • Total messages: {stats['total_messages']}\n"
            stats_text += f"  • Total channels: {stats['total_channels']}\n"
            if stats['oldest_message']:
                stats_text += f"  • Oldest message: {stats['oldest_message'].strftime('%Y-%m-%d %H:%M')}\n"
            if stats['newest_message']:
                stats_text += f"  • Newest message: {stats['newest_message'].strftime('%Y-%m-%d %H:%M')}\n"
            stats_text += f"  • Encrypted: {'Yes' if stats['encrypted'] else 'No'}"
            
            ttk.Label(history_frame, text=stats_text, font=('Arial', 9)).pack(anchor=tk.W, pady=(10, 0))
            
            # Clear history button
            def clear_history():
                if messagebox.askyesno("Clear History", "Are you sure you want to clear all message history? This cannot be undone."):
                    history.clear_history()
                    messagebox.showinfo("Success", "Message history cleared")
            
            ttk.Button(history_frame, text="Clear All History", command=clear_history).pack(anchor=tk.W, pady=(10, 0))
        
        # Notifications tab
        notif_frame = ttk.Frame(notebook, padding=20)
        notebook.add(notif_frame, text="Notifications")
        
        ttk.Label(notif_frame, text="Desktop Notifications:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        notif_enabled_var = tk.BooleanVar(value=config.get("notifications", "enabled", default=True))
        notif_mentions_var = tk.BooleanVar(value=config.get("notifications", "on_mention", default=True))
        notif_pm_var = tk.BooleanVar(value=config.get("notifications", "on_pm", default=True))
        notif_inactive_var = tk.BooleanVar(value=config.get("notifications", "only_when_inactive", default=True))
        sound_enabled_var = tk.BooleanVar(value=config.get("notifications", "sound_enabled", default=True))
        
        ttk.Checkbutton(notif_frame, text="Enable desktop notifications", variable=notif_enabled_var).pack(anchor=tk.W, pady=5)
        ttk.Checkbutton(notif_frame, text="Notify when mentioned (@you)", variable=notif_mentions_var).pack(anchor=tk.W, pady=5, padx=20)
        ttk.Checkbutton(notif_frame, text="Notify on private messages", variable=notif_pm_var).pack(anchor=tk.W, pady=5, padx=20)
        ttk.Checkbutton(notif_frame, text="Only notify when window is inactive", variable=notif_inactive_var).pack(anchor=tk.W, pady=5, padx=20)
        
        ttk.Label(notif_frame, text="Sound Alerts:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(15, 10))
        ttk.Checkbutton(notif_frame, text="Play sound on mentions", variable=sound_enabled_var).pack(anchor=tk.W, pady=5)
        
        ttk.Label(
            notif_frame,
            text="Note: Notification availability depends on your operating system.\nLinux requires 'notify-send'. Windows requires PowerShell.\nmacOS uses osascript.",
            font=('Arial', 8, 'italic'),
            foreground="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(15, 0))
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save_settings():
            config.set("theme", value=theme_var.get())
            config.set("font", "family", value=font_family_var.get())
            config.set("font", "chat_size", value=font_size_var.get())
            config.set("ui", "show_timestamps", value=timestamps_var.get())
            config.set("ui", "show_join_leave", value=join_leave_var.get())
            config.set("ui", "inactivity_timeout", value=timeout_var.get() * 60)
            config.set("history", "enabled", value=history_enabled_var.get())
            config.set("history", "encrypted", value=history_encrypted_var.get())
            if history_password_var.get():
                config.set("history", "password", value=history_password_var.get())
            config.set("notifications", "enabled", value=notif_enabled_var.get())
            config.set("notifications", "on_mention", value=notif_mentions_var.get())
            config.set("notifications", "on_pm", value=notif_pm_var.get())
            config.set("notifications", "only_when_inactive", value=notif_inactive_var.get())
            config.set("notifications", "sound_enabled", value=sound_enabled_var.get())
            apply_theme_callback()
            
            # Update font
            font_family = font_family_var.get()
            font_size = font_size_var.get()
            chat_display.config(font=(font_family, font_size))
            
            dialog.destroy()
            messagebox.showinfo("Settings", "Settings saved! Some changes may require restart.")
        
        ttk.Button(btn_frame, text="Save", command=save_settings, width=12).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=12).pack(side=tk.RIGHT)
    
    @staticmethod
    def show_help(root, config):
        """Show help dialog with command list
        
        Args:
            root: Parent window
            config: ConfigManager instance
        """
        help_text = """IRC Commands:
        
🔹 Basic Commands:
  /join #channel [join_pwd] [creator_pwd]  - Join/create channel
    • For new channels: creator_pwd required (4+ chars) to regain operator later
    • For existing: use creator_pwd to regain operator status  
    • If only one password: used for both join and creator access
    • Channel names automatically converted to lowercase
    • Spaces in names replaced with hyphens
  /leave [#channel]          - Leave current or specified channel
  /msg user message          - Send private message
  /nick newnick              - Change nickname (future)
  /quit                      - Disconnect and quit
  
🔹 Actions & Formatting:
  /me action                 - Send action (*user does something*)
  
  Markdown Support:
  **bold** or *bold*         - Bold text
  _italic_ or __italic__     - Italic text  
  `code`                     - Inline code
  ~~strikethrough~~          - Strikethrough text
  [text](url)                - Links
  # Header                   - Headers (# to ######)
  > quote                    - Blockquotes
  - item or * item           - Bullet lists
  1. item                    - Numbered lists
  --- or ***                 - Horizontal rule
  
🔹 Channel Management:
  Mods - Can kick users
  Operators - Can kick, ban, give mod status
  Owners - All operator powers + give operator status + transfer ownership
  
  /op user                   - Grant operator (owner only, requires setting op password)
  /unop user                 - Remove operator status (owner only)
  /mod user                  - Grant mod status (operators+)
  /unmod user                - Remove mod status (operators+)
  /kick user [reason]        - Kick user from channel (mods+)
  /ban user [duration] [reason] - Ban user from channel (operators+)
                                  Duration: 30m, 1h, 2h30m (optional, permanent if omitted)
  /unban user                - Unban user from channel (operators+)
  /kickban user [reason]     - Kick and ban user (operators+)
  /invite user               - Invite user to current channel (operators+)
  /mode +/-mode              - Set channel mode (operators+)
                                  Modes: m=moderated, s=secret, i=invite-only, n=no external msgs, p=private
  /transfer user             - Transfer channel ownership (owner only, target must be op)
  /topic new topic           - Set channel topic (operators+)
  
🔹 Information:
  /users                     - List all online users
  /whois user                - Get user information and channels
  /list                      - List all available channels (🔒 = password-protected)
  
🔹 Message History (if enabled):
  /history [limit]           - Show message history (default: 50 messages)
  /search query              - Search message history
  /export                    - Export message history to file
  
🔹 File Transfer:
  /image user path           - Send encrypted image
  
🔹 User Management:
  /register password         - Register your current nickname
  /profile                   - View your profile
  /profile view nickname     - View another user's profile
  /profile bio text          - Update your bio (max 500 chars)
  /profile status message    - Update your status message (max 100 chars)
  /block nickname            - Block user (hide their messages)
  /unblock nickname          - Unblock user
  /blocked                   - List blocked users
  
💡 Tip: Double-click a user to start private chat
💡 Tip: Right-click a channel user for quick actions
💡 Tip: Press Tab to autocomplete nicknames
💡 Tip: Channel messages are filtered - switch channels to see different conversations
💡 Tip: Operators need a password - set it when granted op, provide it when rejoining
"""
        
        dialog = tk.Toplevel(root)
        dialog.title("IRC Commands Help")
        dialog.geometry("600x500")
        dialog.transient(root)
        
        # Apply theme colors
        colors = config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Consolas', 10),
                                         bg=colors['chat_bg'], fg=colors['chat_fg'])
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert('1.0', help_text)
        text.config(state=tk.DISABLED)
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
