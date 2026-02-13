"""
UI Dialogs for JustIRC
Contains all dialog windows and popups
"""

import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
from protocol import Protocol


class UIDialogs:
    """Collection of UI dialog methods for JustIRC client"""
    
    @staticmethod
    def show_status_dialog(parent, config, current_status, current_status_message, 
                          connected, loop, running, send_status_callback):
        """Show dialog to set user status"""
        if not connected:
            messagebox.showwarning("Not Connected", "You must be connected to set your status")
            return
        
        dialog = tk.Toplevel(parent)
        dialog.title("Set Status")
        dialog.geometry("400x350")
        dialog.transient(parent)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Apply theme colors
        colors = config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Select Your Status:", font=('Segoe UI', 11, 'bold')).pack(anchor=tk.W, pady=(0, 15))
        
        status_var = tk.StringVar(value=current_status)
        
        status_options = {
            "online": ("🟢 Online", "You are active and available"),
            "away": ("🟡 Away", "You are away from keyboard"),
            "busy": ("🔴 Busy", "You are busy, do not disturb"),
            "dnd": ("⛔ Do Not Disturb", "You do not want to be disturbed")
        }
        
        # Status radio buttons
        for status_key, (display, description) in status_options.items():
            frame = ttk.Frame(main_frame)
            frame.pack(fill=tk.X, pady=5)
            
            radio = ttk.Radiobutton(
                frame,
                text=display,
                variable=status_var,
                value=status_key
            )
            radio.pack(anchor=tk.W)
            
            ttk.Label(
                frame,
                text=description,
                font=('Segoe UI', 8),
                foreground="gray"
            ).pack(anchor=tk.W, padx=(25, 0))
        
        # Custom status message
        ttk.Label(main_frame, text="Custom Message (optional):", font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(15, 5))
        
        message_var = tk.StringVar(value=current_status_message)
        message_entry = ttk.Entry(main_frame, textvariable=message_var, width=40)
        message_entry.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(
            main_frame,
            text="Max 100 characters",
            font=('Segoe UI', 8),
            foreground="gray"
        ).pack(anchor=tk.W)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))
        
        def apply_status():
            new_status = status_var.get()
            new_message = message_var.get()[:100]  # Limit to 100 chars
            
            # Send to server via callback
            if loop and running:
                asyncio.run_coroutine_threadsafe(
                    send_status_callback(new_status, new_message),
                    loop
                )
            
            dialog.destroy()
            messagebox.showinfo("Status Updated", f"Your status has been set to: {status_options[new_status][0]}")
        
        ttk.Button(btn_frame, text="Apply", command=apply_status, width=12).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=12).pack(side=tk.RIGHT)
    
    @staticmethod
    def show_emoji_picker(parent, config, message_entry):
        """Show emoji picker dialog"""
        dialog = tk.Toplevel(parent)
        dialog.title("Emoji Picker")
        dialog.geometry("450x400")
        dialog.transient(parent)
        dialog.resizable(False, False)
        
        # Apply theme colors
        colors = config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        # Emoji categories
        emoji_categories = {
            "😊 Smileys": ["😀", "😃", "😄", "😁", "😆", "😅", "🤣", "😂", "🙂", "🙃", 
                          "😉", "😊", "😇", "🥰", "😍", "🤩", "😘", "😗", "😚", "😙",
                          "😋", "😛", "😜", "🤪", "😝", "🤑", "🤗", "🤭", "🤫", "🤔"],
            "😢 Emotions": ["🤐", "🤨", "😐", "😑", "😶", "😏", "😒", "🙄", "😬", "🤥",
                           "😌", "😔", "😪", "🤤", "😴", "😷", "🤒", "🤕", "🤢", "🤮",
                           "🤧", "🥵", "🥶", "🥴", "😵", "🤯", "🤠", "🥳", "😎", "🤓"],
            "😡 Reactions": ["😕", "😟", "🙁", "☹️", "😮", "😯", "😲", "😳", "🥺", "😦",
                            "😧", "😨", "😰", "😥", "😢", "😭", "😱", "😖", "😣", "😞",
                            "😓", "😩", "😫", "🥱", "😤", "😡", "😠", "🤬", "😈", "👿"],
            "👍 Gestures": ["👋", "🤚", "🖐️", "✋", "🖖", "👌", "🤏", "✌️", "🤞", "🤟",
                           "🤘", "🤙", "👈", "👉", "👆", "🖕", "👇", "☝️", "👍", "👎",
                           "✊", "👊", "🤛", "🤜", "👏", "🙌", "👐", "🤲", "🤝", "🙏"],
            "❤️ Hearts": ["💘", "💝", "💖", "💗", "💓", "💞", "💕", "💟", "❣️", "💔",
                         "❤️", "🧡", "💛", "💚", "💙", "💜", "🤎", "🖤", "🤍", "💯"],
            "🎉 Objects": ["💬", "💭", "💤", "💥", "💨", "💫", "💦", "💢", "🔥", "⭐",
                          "✨", "🌟", "💫", "🎉", "🎊", "🎈", "🎁", "🏆", "🥇", "🥈"],
            "😺 Animals": ["🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯",
                          "🦁", "🐮", "🐷", "🐸", "🐵", "🐔", "🐧", "🐦", "🐤", "🦄"],
            "🍕 Food": ["🍔", "🍕", "🌭", "🍟", "🍿", "🥓", "🥞", "🧇", "🥖", "🥐",
                       "🍩", "🍪", "🎂", "🍰", "🧁", "🍫", "🍬", "🍭", "🍮", "☕"]
        }
        
        # Category buttons frame
        cat_frame = ttk.Frame(dialog)
        cat_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Emoji display frame with scrollbar
        emoji_frame_container = ttk.Frame(dialog)
        emoji_frame_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        canvas = tk.Canvas(emoji_frame_container, bg=colors['chat_bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(emoji_frame_container, orient="vertical", command=canvas.yview)
        emoji_frame = ttk.Frame(canvas)
        
        emoji_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=emoji_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def insert_emoji(emoji):
            """Insert emoji at cursor position"""
            cursor_pos = message_entry.index(tk.INSERT)
            message_entry.insert(cursor_pos, emoji)
            message_entry.focus()
            dialog.destroy()
        
        def show_category(category_name):
            """Display emojis for selected category"""
            # Clear current emojis
            for widget in emoji_frame.winfo_children():
                widget.destroy()
            
            emojis = emoji_categories[category_name]
            row = 0
            col = 0
            max_cols = 8
            
            for emoji in emojis:
                btn = tk.Button(
                    emoji_frame,
                    text=emoji,
                    font=('Arial', 20),
                    width=2,
                    height=1,
                    bd=1,
                    relief=tk.RAISED,
                    bg=colors['chat_bg'],
                    fg=colors['fg'],
                    activebackground=colors['highlight'],
                    command=lambda e=emoji: insert_emoji(e)
                )
                btn.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            
            # Configure grid weights for equal sizing
            for i in range(max_cols):
                emoji_frame.grid_columnconfigure(i, weight=1)
        
        # Create category buttons
        for i, category in enumerate(emoji_categories.keys()):
            btn = ttk.Button(
                cat_frame,
                text=category.split()[0],  # Just the emoji
                command=lambda c=category: show_category(c),
                width=4
            )
            btn.grid(row=0, column=i, padx=2)
        
        # Show first category by default
        show_category(list(emoji_categories.keys())[0])
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=(0, 10))
    
    @staticmethod
    def show_invite_dialog(parent, config, channel, inviter_nickname, inviter_id, 
                          loop, send_to_server_callback, log_callback):
        """Show dialog when invited to a channel"""
        dialog = tk.Toplevel(parent)
        dialog.title("Channel Invite")
        dialog.geometry("400x200")
        dialog.transient(parent)
        dialog.resizable(False, False)
        
        # Apply theme colors
        colors = config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Invite message
        msg_frame = tk.Frame(dialog, bg=colors['bg'])
        msg_frame.pack(pady=30, padx=20, fill='x')
        
        tk.Label(
            msg_frame,
            text=f"{inviter_nickname} has invited you to:",
            font=('Arial', 12),
            bg=colors['bg'],
            fg=colors['fg']
        ).pack()
        
        tk.Label(
            msg_frame,
            text=f"#{channel}",
            font=('Arial', 16, 'bold'),
            bg=colors['bg'],
            fg=colors['accent']
        ).pack(pady=10)
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=colors['bg'])
        btn_frame.pack(pady=20)
        
        def accept():
            dialog.destroy()
            # Send accept response
            msg = Protocol.invite_response(channel, inviter_nickname, True)
            asyncio.run_coroutine_threadsafe(
                send_to_server_callback(msg),
                loop
            )
            log_callback(f"Joined {channel}", "success")
        
        def decline():
            dialog.destroy()
            # Send decline response
            msg = Protocol.invite_response(channel, inviter_nickname, False)
            asyncio.run_coroutine_threadsafe(
                send_to_server_callback(msg),
                loop
            )
            log_callback(f"Declined invite to {channel}", "system")
        
        accept_btn = tk.Button(
            btn_frame,
            text="Accept",
            command=accept,
            font=('Arial', 11, 'bold'),
            bg='#28a745',
            fg='white',
            padx=30,
            pady=8
        )
        accept_btn.pack(side='left', padx=10)
        
        decline_btn = tk.Button(
            btn_frame,
            text="Decline",
            command=decline,
            font=('Arial', 11),
            bg='#dc3545',
            fg='white',
            padx=30,
            pady=8
        )
        decline_btn.pack(side='left', padx=10)
    
    @staticmethod
    def show_about(parent, config):
        """Show about dialog with logo"""
        dialog = tk.Toplevel(parent)
        dialog.title("About JustIRC")
        dialog.geometry("450x550")
        dialog.transient(parent)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Get theme colors
        colors = config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        # Create logo area
        logo_frame = tk.Frame(dialog, bg=colors['bg'], height=120)
        logo_frame.pack(fill=tk.X, pady=20)
        
        # Create a simple shield logo
        try:
            canvas = tk.Canvas(logo_frame, width=100, height=100, 
                             bg=colors['bg'], highlightthickness=0)
            canvas.pack()
            
            # Draw cyber shield logo
            points = [
                50, 10,   # Top
                80, 30,   # Top right
                80, 70,   # Bottom right
                50, 90,   # Bottom
                20, 70,   # Bottom left
                20, 30    # Top left
            ]
            
            canvas.create_polygon(points, fill='#2196F3', outline='#66BB6A', width=3)
            canvas.create_oval(30, 30, 70, 70, outline='#4CAF50', width=2)
            canvas.create_line(50, 20, 50, 40, fill='#76FF03', width=2)
            canvas.create_line(50, 60, 50, 80, fill='#76FF03', width=2)
            canvas.create_line(30, 50, 40, 50, fill='#76FF03', width=2)
            canvas.create_line(60, 50, 70, 50, fill='#76FF03', width=2)
            canvas.create_arc(40, 40, 60, 60, start=45, extent=270,
                            outline='#66BB6A', width=3, style=tk.ARC)
        except:
            pass
        
        # App title
        title_label = tk.Label(
            dialog,
            text="🛡️ JustIRC",
            font=('Arial', 24, 'bold'),
            bg=colors['bg'],
            fg=colors['accent']
        )
        title_label.pack(pady=(0, 10))
        
        subtitle_label = tk.Label(
            dialog,
            text="Secure Encrypted IRC",
            font=('Arial', 12),
            bg=colors['bg'],
            fg=colors['fg']
        )
        subtitle_label.pack(pady=(0, 20))
        
        # Info frame
        info_frame = tk.Frame(dialog, bg=colors['chat_bg'], relief=tk.RIDGE, borderwidth=2)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        info_text = (
            "Version 1.0.1\n\n"
            "🔐 End-to-End Encrypted IRC Client\n\n"
            "Features:\n"
            "  • X25519 ECDH key exchange\n"
            "  • ChaCha20-Poly1305 AEAD encryption\n"
            "  • Zero-knowledge routing server\n"
            "  • Secure image transfer\n"
            "  • Password-protected channels\n"
            "  • Channel operators\n"
            "  • Modern themeable UI\n\n"
            "🔒 Your messages are encrypted end-to-end.\n"
            "The server cannot decrypt your communications!"
        )
        
        info_label = tk.Label(
            info_frame,
            text=info_text,
            justify=tk.LEFT,
            font=('Consolas', 10),
            bg=colors['chat_bg'],
            fg=colors['chat_fg'],
            padx=20,
            pady=20
        )
        info_label.pack()
        
        # Close button
        close_btn = tk.Button(
            dialog,
            text="Close",
            command=dialog.destroy,
            font=('Arial', 10),
            bg=colors['accent'],
            fg='white',
            padx=30,
            pady=5
        )
        close_btn.pack(pady=20)
