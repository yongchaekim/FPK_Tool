#!/usr/bin/env python3
"""
CMD GUI Tool - Windows command execution GUI program
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import subprocess
import threading
import os
import sys
from datetime import datetime
import re

class CMDGui:
    def __init__(self, root):
        self.root = root
        self.root.title("FPK ADB CMD Sender 1.10")
        self.root.geometry("550x550")
        self.root.minsize(450, 450)
        
        # Style setup
        self.setup_styles()
        
        # Create GUI components
        self.create_widgets()
        
        # Event bindings
        self.bind_events()
        
        # Initial setup
        self.current_directory = os.getcwd()
        self.dir_history = []  # Directory history
        self.adb_folder = ""  # ADB folder path (empty = use PATH)
        self.settings_file = os.path.join(self.current_directory, "adb_settings.txt")
        self.settings_window = None  # Settings window reference
        self.device_id = "ABC-0123456789"  # Fixed device ID

        # Load saved ADB folder settings
        self.load_adb_settings()

        # Check ADB status on startup (run after 0.5s)
        self.root.after(500, self.update_all_adb_status)
        
        # Periodic overall connection check
        self.all_connected = False  # Track overall connection state
        self.start_periodic_connection_check()
        
    def setup_styles(self):
        """Configure GUI styles."""
        style = ttk.Style()
        style.theme_use('winnative')
        
    def create_widgets(self):
        """Create GUI widgets (keypad layout)."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Top settings button and status text
        settings_frame = ttk.Frame(main_frame)
        settings_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))

        # Settings button (increased height)
        settings_btn = ttk.Button(settings_frame, text="Settings",
                                 command=self.open_settings)
        settings_btn.grid(row=0, column=0, pady=5, padx=(0, 10), ipady=8)

        # Connection status message
        self.connection_status_label = ttk.Label(settings_frame, text="Checking connection...",
                 foreground="orange", font=('Arial', 9, 'bold'))
        self.connection_status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

        # ADB Shell status indicator (traffic light)
        status_frame = ttk.Frame(settings_frame)
        status_frame.grid(row=0, column=2, sticky=tk.E, padx=5)
        
        ttk.Label(status_frame, text="ADB Shell:", font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_canvas = tk.Canvas(status_frame, width=20, height=20, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT)
        
        # Initial state: gray (Unknown)
        self.status_light = self.status_canvas.create_oval(2, 2, 18, 18, fill="gray", outline="gray")

        # Hidden command input field (used by keypad)
        self.cmd_entry = ttk.Entry(main_frame, width=1)
        self.cmd_entry.grid(row=1, column=0, sticky="w")
        self.cmd_entry.grid_remove()  # Hidden from view

        # Keypad button frame (3x4 grid)
        keypad_frame = ttk.Frame(main_frame)
        keypad_frame.grid(row=2, column=0, columnspan=3, pady=(10, 10))

        # Keypad button definitions
        # 1 2 3
        # 4 5 6
        # 7 8 9
        # 10 0 11
        keypad_buttons = {
            # First row (1, 2, 3)
            (0, 0): ("FAS\n1 (Home)", self.go_home),
            (0, 1): ("UP\n2 (▲)", self.move_up),
            (0, 2): ("ADAS\n3", self.send_adas_preset),

            # Second row (4, 5, 6)
            (1, 0): ("MENU UP\n4 (◀)", self.move_left),
            (1, 1): ("OK\n5 (Enter)", self.run_command),
            (1, 2): ("MENU DOWN\n6 (▶)", self.move_right),

            # Third row (7, 8, 9)
            (2, 0): ("SIGNAL\n7", self.focus_signal_input),
            (2, 1): ("DOWN\n8 (▼)", self.move_down),
            (2, 2): ("VIEW\n9 (PgDn)", self.save_output),

            # Fourth row (0)
            (3, 0): ("Navigation\n10", self.send_navigation_preset),
            (3, 1): ("Clear Log\n0", self.clear_output),
            (3, 2): ("LONG VIEW\n11", self.send_long_view_preset),
        }

        # Create keypad buttons (1.3x larger, show action name)
        self.keypad_btns = {}
        for (row, col), (text, command) in keypad_buttons.items():
            if command is None:  # Disabled button
                btn = ttk.Button(keypad_frame, text=text, state=tk.DISABLED, width=16)
            else:
                btn = ttk.Button(keypad_frame, text=text, command=command, width=16)
            btn.grid(row=row, column=col, padx=8, pady=8, sticky=(tk.W, tk.E), ipady=8)
            self.keypad_btns[(row, col)] = btn

        # Custom Signal send input (signal name + value)
        signal_frame = ttk.Frame(main_frame)
        signal_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(signal_frame, text="Signal:").grid(row=0, column=0, sticky=tk.W)

        self.signal_name_var = tk.StringVar()
        self.signal_value_var = tk.StringVar()

        self.signal_name_entry = ttk.Entry(signal_frame, textvariable=self.signal_name_var, width=28)
        self.signal_name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(6, 6))
        self.signal_name_entry.insert(0, "DP_ID_")

        ttk.Label(signal_frame, text="Value:").grid(row=0, column=2, sticky=tk.W, padx=(6, 0))

        self.signal_value_entry = ttk.Entry(signal_frame, textvariable=self.signal_value_var, width=10)
        self.signal_value_entry.grid(row=0, column=3, sticky=tk.W, padx=(6, 6))
        self.signal_value_entry.bind('<Return>', lambda e: self.send_custom_signal())

        send_signal_btn = ttk.Button(signal_frame, text="Send", command=self.send_custom_signal)
        send_signal_btn.grid(row=0, column=4, sticky=tk.E, padx=(0, 0), ipady=4)

        navigation_btn = ttk.Button(
            signal_frame,
            text="Navigation",
            command=self.send_navigation_preset,
        )
        navigation_btn.grid(
            row=1,
            column=0,
            columnspan=5,
            sticky=(tk.W, tk.E),
            pady=(8, 0),
            ipady=3,
        )

        signal_frame.columnconfigure(1, weight=1)

        # Output display
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        ttk.Label(output_frame, text="Output:").grid(row=0, column=0, sticky=tk.W)

        # Scrollable text widget (reduced height)
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            height=8,
            width=80,
            font=('Consolas', 9),
            wrap=tk.WORD
        )
        self.output_text.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))



        # Grid weight configuration
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)  # Output frame is row=4
        settings_frame.columnconfigure(1, weight=1)  # Settings button + status text
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)
    
    def bind_events(self):
        """Event bindings (including numpad keys)."""
        # Basic key bindings
        self.cmd_entry.bind('<Return>', lambda e: self.run_command())
        self.cmd_entry.bind('<Control-l>', lambda e: self.clear_command())
        self.root.bind('<Control-r>', lambda e: self.run_command())
        self.root.bind('<F5>', lambda e: self.run_command())
        self.root.bind('<F6>', lambda e: self.send_navigation_preset())
        self.root.bind('<Control-n>', lambda e: self.send_navigation_preset())


    # Keypad number key bindings
        self.root.bind('<KeyPress-KP_1>', lambda e: self.go_home())
        self.root.bind('<KeyPress-KP_2>', lambda e: self.move_up())
        self.root.bind('<KeyPress-KP_3>', lambda e: self.send_adas_preset())
        self.root.bind('<KeyPress-KP_4>', lambda e: self.move_left())
        self.root.bind('<KeyPress-KP_5>', lambda e: self.run_command())
        self.root.bind('<KeyPress-KP_6>', lambda e: self.move_right())
        self.root.bind('<KeyPress-KP_7>', lambda e: self.focus_signal_input())
        self.root.bind('<KeyPress-KP_8>', lambda e: self.move_down())
        self.root.bind('<KeyPress-KP_9>', lambda e: self.save_output())
        self.root.bind('<KeyPress-KP_0>', lambda e: self.clear_output())

    # Also support regular number keys (if no numpad)
        self.root.bind('<KeyPress-1>', lambda e: self.go_home())
        self.root.bind('<KeyPress-2>', lambda e: self.move_up())
        self.root.bind('<KeyPress-3>', lambda e: self.send_adas_preset())
        self.root.bind('<KeyPress-4>', lambda e: self.move_left())
        self.root.bind('<KeyPress-5>', lambda e: self.run_command())
        self.root.bind('<KeyPress-6>', lambda e: self.move_right())
        self.root.bind('<KeyPress-7>', lambda e: self.focus_signal_input())
        self.root.bind('<KeyPress-8>', lambda e: self.move_down())
        self.root.bind('<KeyPress-9>', lambda e: self.save_output())
        self.root.bind('<KeyPress-0>', lambda e: self.clear_output())

        # Special key bindings
        self.root.bind('<Home>', lambda e: self.go_home())          # 1 - Home
        self.root.bind('<Up>', lambda e: self.move_up())            # 2 - Up arrow
        self.root.bind('<Left>', lambda e: self.move_left())        # 4 - Left arrow
        self.root.bind('<Return>', lambda e: self.run_command())    # 5 - Enter
        self.root.bind('<Right>', lambda e: self.move_right())      # 6 - Right arrow
        self.root.bind('<Down>', lambda e: self.move_down())        # 8 - Down arrow
        self.root.bind('<Next>', lambda e: self.save_output())      # 9 - Page Down
    
    def update_directory_label(self):
        """Update current directory state (no label)."""
        # Display current directory in the output area
        pass

    def change_directory(self):
        """Change directory (keypad-only)."""
        from tkinter import filedialog
        directory = filedialog.askdirectory(initialdir=self.current_directory)
        if directory:
            self.current_directory = directory
            os.chdir(directory)
            self.output_text.insert(tk.END, f"Changed directory: {directory}\n")
            self.output_text.see(tk.END)
    
    def set_command(self, command):
        """Set a command into the command input field."""
        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.insert(0, command)
        self.cmd_entry.focus()
    
    def clear_command(self):
        """Clear the command input field."""
        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.focus()

    def log_to_output(self, message):
        """Append a log message to the output area."""
        self.output_text.insert(tk.END, f"{message}\n")
        self.output_text.see(tk.END)
        # Small wait to ensure GUI updates
        self.root.update_idletasks()

    def load_adb_settings(self):
        """Load saved ADB settings."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    saved_folder = f.read().strip()
                    if saved_folder and os.path.exists(saved_folder):
                        self.adb_folder = saved_folder
                        self.log_to_output(f"[Settings Load] Saved ADB folder: {self.adb_folder}")
                    else:
                        self.log_to_output("[Settings Load] Saved ADB folder not found; using default")
        except Exception as e:
            self.log_to_output(f"[Settings Load Error] {str(e)}")

    def save_adb_settings(self):
        """Save ADB settings."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                f.write(self.adb_folder)
            self.log_to_output(f"[Settings Save] ADB folder setting saved: {self.adb_folder}")
        except Exception as e:
            self.log_to_output(f"[Settings Save Error] {str(e)}")

    def get_adb_command(self, command=""):
        """Build an ADB command (includes device id, optional custom adb folder)."""
        # Determine base adb path
        if self.adb_folder and os.path.exists(self.adb_folder):
            # Use adb.exe from the specified folder
            adb_exe = os.path.join(self.adb_folder, "adb.exe")
            if os.path.exists(adb_exe):
                base_cmd = f'"{adb_exe}"'
            else:
                # Fall back to default command if adb.exe isn't found
                self.log_to_output(f"[Warning] adb.exe not found in the specified folder: {self.adb_folder}")
                base_cmd = "adb"
        else:
            # Use default adb command (search on PATH)
            base_cmd = "adb"
        
        # Add device id
        if command:
            return f"{base_cmd} -s {self.device_id} {command}"
        else:
            return f"{base_cmd} -s {self.device_id}"

    def check_adb_installation(self):
        """Check whether ADB is installed/available."""
        try:
            # Run adb command to verify installation
            adb_cmd = self.get_adb_command()
            if self.adb_folder:
                self.log_to_output(f"[ADB Check] Selected ADB folder: {self.adb_folder}")
            else:
                self.log_to_output("[ADB Check] Using default ADB command (searching PATH)")
            self.log_to_output(f"[ADB Check] Command: {adb_cmd}")

            process = subprocess.Popen(
                adb_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=10)

            # Log outputs
            self.log_to_output(f"[ADB Check] Return code: {process.returncode}")
            if stdout.strip():
                self.log_to_output(f"[ADB Check] STDOUT:\n{stdout}")
            if stderr.strip():
                self.log_to_output(f"[ADB Check] STDERR:\n{stderr}")

            # Determine ADB availability
            # 1) Return code 9009 = command not found (Windows)
            if process.returncode == 9009:
                self.log_to_output("[ADB Check] ❌ Command not found (return code: 9009)")
                return False, "Cannot find the ADB command. It may not be installed or not on PATH."

            # 2) Specific error message in stderr
            if "'adb' is not recognized" in stderr:
                self.log_to_output("[ADB Check] ❌ Command not recognized")
                return False, "ADB command is not recognized. It may not be installed or not on PATH."

            # 3) If it prints "Android Debug Bridge", it's installed
            if "Android Debug Bridge" in stdout or "Android Debug Bridge" in stderr:
                self.log_to_output("[ADB Check] ✅ ADB detected (" + "Android Debug Bridge" + " found)")
                return True, "ADB is installed and available."

            # 4) If return code is 1 and help/usage is shown, treat as installed
            if process.returncode == 1 and ("usage:" in stdout.lower() or "usage:" in stderr.lower()):
                self.log_to_output("[ADB Check] ✅ ADB detected (usage/help shown)")
                return True, "ADB is installed and available."

            # 5) Extra verification: run `adb version`
            self.log_to_output("[ADB Check] Extra verification: running `adb version`...")
            try:
                version_cmd = self.get_adb_command("version")
                version_process = subprocess.Popen(
                    version_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='cp949',
                    cwd=self.current_directory
                )
                version_stdout, version_stderr = version_process.communicate(timeout=5)

                self.log_to_output(f"[ADB Check] adb version return code: {version_process.returncode}")
                if version_stdout.strip():
                    self.log_to_output(f"[ADB Check] adb version STDOUT:\n{version_stdout}")
                if version_stderr.strip():
                    self.log_to_output(f"[ADB Check] adb version STDERR:\n{version_stderr}")

                if version_process.returncode == 0 and ("Android Debug Bridge" in version_stdout or "version" in version_stdout.lower()):
                    self.log_to_output("[ADB Check] ✅ ADB detected (`adb version` succeeded)")
                    return True, "ADB is installed and available."

            except Exception as ve:
                self.log_to_output(f"[ADB Check] adb version failed: {str(ve)}")

            # 6) Otherwise assume not installed/available
            self.log_to_output(f"[ADB Check] ❌ ADB check failed (return code: {process.returncode})")
            return False, f"Cannot determine ADB installation status. (return code: {process.returncode})"

        except subprocess.TimeoutExpired:
            self.log_to_output("[ADB Check] ❌ Timeout")
            return False, "ADB command timed out"
        except FileNotFoundError:
            self.log_to_output("[ADB Check] ❌ File not found (FileNotFoundError)")
            return False, "ADB may not be installed or not on PATH."
        except OSError as e:
            if e.errno == 2:  # No such file or directory
                self.log_to_output("[ADB Check] ❌ File not found (OSError)")
                return False, "Cannot find the ADB executable."
            else:
                self.log_to_output(f"[ADB Check] ❌ OS error: {str(e)}")
                return False, f"System error: {str(e)}"
        except Exception as e:
            self.log_to_output(f"[ADB Check] ❌ Exception: {str(e)}")
            return False, f"Error while checking ADB: {str(e)}"

    def check_adb_devices(self):
        """Check ADB device connection status."""
        try:
            # Check connected devices via `adb devices`
            self.log_to_output("[Device Check] Running `adb devices`...")

            devices_cmd = self.get_adb_command("devices")
            process = subprocess.Popen(
                devices_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=15)

            # Log outputs
            self.log_to_output(f"[Device Check] Return code: {process.returncode}")
            if stdout.strip():
                self.log_to_output(f"[Device Check] STDOUT:\n{stdout}")
            if stderr.strip():
                self.log_to_output(f"[Device Check] STDERR:\n{stderr}")

            if process.returncode == 0:
                lines = stdout.strip().split('\n')
                devices = []
                for line in lines[1:]:  # First line is "List of devices attached"
                    if line.strip() and '\t' in line:
                        device_info = line.strip().split('\t')
                        if len(device_info) >= 2:
                            devices.append((device_info[0], device_info[1]))

                if devices:
                    device_list = []
                    for device_id, status in devices:
                        device_list.append(f"{device_id} ({status})")
                    self.log_to_output(f"[Device Check] ✅ Devices found: {len(devices)}")
                    return True, f"Connected devices: {', '.join(device_list)}"
                else:
                    self.log_to_output("[Device Check] ❌ No connected devices")
                    return False, "No devices are connected."
            else:
                self.log_to_output("[Device Check] ❌ Failed to run `adb devices`")
                return False, f"Failed to run `adb devices`: {stderr}"

        except subprocess.TimeoutExpired:
            self.log_to_output("[Device Check] ❌ Timeout")
            return False, "`adb devices` timed out"
        except Exception as e:
            self.log_to_output(f"[Device Check] ❌ Exception: {str(e)}")
            return False, f"Error while checking devices: {str(e)}"

    def check_adb_shell(self):
        """Test ADB shell connectivity."""
        try:
            # Test shell connectivity using `adb shell echo`
            self.log_to_output('[Shell Test] Running `adb shell echo "ADB Shell Test"`...')

            shell_cmd = self.get_adb_command('shell echo "ADB Shell Test"')
            process = subprocess.Popen(
                shell_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=15)

            # Log outputs
            self.log_to_output(f"[Shell Test] Return code: {process.returncode}")
            if stdout.strip():
                self.log_to_output(f"[Shell Test] STDOUT:\n{stdout}")
            if stderr.strip():
                self.log_to_output(f"[Shell Test] STDERR:\n{stderr}")

            if process.returncode == 0 and "ADB Shell Test" in stdout:
                self.log_to_output("[Shell Test] ✅ Shell connected")
                return True, "ADB Shell connectivity is working."
            elif "no devices/emulators found" in stderr:
                self.log_to_output("[Shell Test] ❌ No device")
                return False, "No connected device; cannot run the shell test."
            elif "device unauthorized" in stderr:
                self.log_to_output("[Shell Test] ❌ Device unauthorized")
                return False, "Device is unauthorized. Confirm USB debugging authorization."
            elif "device offline" in stderr:
                self.log_to_output("[Shell Test] ❌ Device offline")
                return False, "Device is offline."
            else:
                self.log_to_output("[Shell Test] ❌ Shell connection failed")
                return False, f"ADB Shell connection failed: {stderr}"

        except subprocess.TimeoutExpired:
            self.log_to_output("[Shell Test] ❌ Timeout")
            return False, "ADB Shell command timed out"
        except Exception as e:
            self.log_to_output(f"[Shell Test] ❌ Exception: {str(e)}")
            return False, f"Error while testing ADB Shell: {str(e)}"

    def open_settings(self):
        """Open the settings window."""
        # If the settings window is already open, just focus it
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.focus()
            self.settings_window.lift()
            return
        
        settings_window = tk.Toplevel(self.root)
        self.settings_window = settings_window
        settings_window.title("Settings - ADB Status")
        settings_window.geometry("510x480")
        settings_window.resizable(False, False)

        # Clear reference when the window closes
        def on_close():
            self.settings_window = None
            settings_window.destroy()
        
        settings_window.protocol("WM_DELETE_WINDOW", on_close)

        # Keep settings window on top of the main window
        settings_window.transient(self.root)
        settings_window.grab_set()

        # Position settings window relative to main window
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()

        # Center the settings window over the main window
        settings_x = main_x + (main_width - 510) // 2
        settings_y = main_y + (main_height - 480) // 2

        settings_window.geometry(f"510x480+{settings_x}+{settings_y}")

        # Settings content frame
        settings_frame = ttk.Frame(settings_window, padding="20")
        settings_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(settings_frame, text="FPK ADB CMD Sender Settings",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        # ADB folder settings frame
        path_frame = ttk.LabelFrame(settings_frame, text="ADB Folder", padding="10")
        path_frame.pack(fill=tk.X, pady=(0, 5))

        # Show current ADB folder
        current_path_frame = ttk.Frame(path_frame)
        current_path_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(current_path_frame, text="Current ADB folder:").pack(side=tk.LEFT)
        current_folder_text = self.adb_folder if self.adb_folder else "Default (search on PATH)"
        self.current_adb_folder_label = ttk.Label(current_path_frame, text=current_folder_text,
                                                 foreground="blue", font=('Consolas', 9))
        self.current_adb_folder_label.pack(side=tk.LEFT, padx=(5, 0))

        # ADB folder selection buttons
        path_buttons_frame = ttk.Frame(path_frame)
        path_buttons_frame.pack(fill=tk.X)

        ttk.Button(path_buttons_frame, text="Choose Folder",
                  command=self.browse_adb_folder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(path_buttons_frame, text="Use Default",
                  command=self.reset_adb_folder).pack(side=tk.LEFT)

        # ADB installation status frame
        adb_frame = ttk.LabelFrame(settings_frame, text="ADB Status", padding="10")
        adb_frame.pack(fill=tk.X, pady=(0, 5))

        # ADB status label
        self.adb_status_label = ttk.Label(adb_frame, text="Checking ADB status...",
                                         font=('Arial', 10))
        self.adb_status_label.pack(pady=2)

        # Device connection status frame
        device_frame = ttk.LabelFrame(settings_frame, text="Device Status", padding="10")
        device_frame.pack(fill=tk.X, pady=(0, 5))

        # Device status label
        self.device_status_label = ttk.Label(device_frame, text="Checking device status...",
                                           font=('Arial', 10))
        self.device_status_label.pack(pady=2)

        # ADB Shell test frame
        shell_frame = ttk.LabelFrame(settings_frame, text="ADB Shell Test", padding="10")
        shell_frame.pack(fill=tk.X, pady=(0, 10))

        # Shell test status label
        self.shell_status_label = ttk.Label(shell_frame, text="Testing shell connection...",
                                          font=('Arial', 10))
        self.shell_status_label.pack(pady=2)

        # Re-check all status button
        ttk.Button(settings_frame, text="Re-check All Status",
                  command=lambda: self.update_all_adb_status()).pack(pady=5)

        # Close button (increased height)
        ttk.Button(settings_frame, text="Close",
                  command=on_close).pack(pady=(10, 0), ipady=8)

        # Initial overall ADB status check
        self.update_all_adb_status()

    def start_periodic_connection_check(self):
        """Periodically check overall connection status (every 3 seconds)."""
        self.last_shell_status = False  # Track previous state
        
        def periodic_check():
            # Quietly check overall connection status
            def check_all_thread():
                # 1) Check ADB installation
                adb_installed = self.check_adb_installation_silent()
                
                if adb_installed:
                    # 2) Check specific device connection (ID: ABC-0123456789)
                    device_connected = self.check_adb_devices_silent()
                    
                    if device_connected:
                        # 3) ADB Shell test
                        shell_working, _ = self.check_adb_shell_silent()
                        
                        if shell_working is not None:
                            # Update overall status
                            all_ok = shell_working
                            self.root.after(0, lambda: self.update_connection_status(adb_installed, device_connected, shell_working, all_ok))
                        else:
                            # If shell check fails, keep previous state
                            pass
                    else:
                        self.root.after(0, lambda: self.update_connection_status(adb_installed, device_connected, False, False))
                else:
                    self.root.after(0, lambda: self.update_connection_status(adb_installed, False, False, False))
            
            thread = threading.Thread(target=check_all_thread)
            thread.daemon = True
            thread.start()
            
            # Repeat every 3 seconds regardless of connection status
            self.root.after(3000, periodic_check)
        
        # First run
        periodic_check()

    def check_adb_installation_silent(self):
        """Check ADB installation status (silent, no logs)."""
        try:
            adb_cmd = self.get_adb_command("version")
            process = subprocess.Popen(
                adb_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=5)
            return process.returncode == 0 and ("Android Debug Bridge" in stdout or "version" in stdout.lower())
        except:
            return False

    def check_adb_devices_silent(self):
        """Check device connection status (silent, no logs) - only checks the configured device id."""
        try:
            devices_cmd = self.get_adb_command("devices")
            # List all devices without the -s option
            devices_cmd = devices_cmd.replace(f"-s {self.device_id} ", "")
            
            process = subprocess.Popen(
                devices_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=5)
            
            if process.returncode == 0:
                lines = stdout.strip().split('\n')
                for line in lines[1:]:  # First line is "List of devices attached"
                    if line.strip() and '\t' in line:
                        device_info = line.strip().split('\t')
                        if len(device_info) >= 2:
                            device_id = device_info[0]
                            device_status = device_info[1]
                            # Check the configured device id and its status
                            if device_id == self.device_id:
                                return device_status == 'device'
            return False
        except:
            return False

    def check_adb_shell_silent(self):
        """Test ADB shell connectivity (silent, no logs)."""
        try:
            shell_cmd = self.get_adb_command('shell echo "ADB Shell Test"')
            process = subprocess.Popen(
                shell_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=5)

            if process.returncode == 0 and "ADB Shell Test" in stdout:
                return True, "Connected"
            else:
                return False, "Not connected"

        except subprocess.TimeoutExpired:
            # Treat timeout as a connection failure
            return False, "Timeout"
        except Exception as e:
            # For other exceptions, keep the previous state (return None)
            return None, str(e)

    def update_status_light(self, is_working):
        """Update only the traffic-light color (silent)."""
        if hasattr(self, 'status_canvas'):
            color = "#00FF00" if is_working else "#FF0000"
            self.status_canvas.itemconfig(self.status_light, fill=color, outline=color)

    def update_connection_status(self, adb_installed, device_connected, shell_working, all_ok):
        """Update overall connection status (traffic light + message)."""
        # Update traffic-light color
        self.update_status_light(shell_working)
        
        # Update connection status message
        if hasattr(self, 'connection_status_label'):
            if not adb_installed:
                self.connection_status_label.config(text="❌ ADB not installed", foreground="red")
            elif not device_connected:
                self.connection_status_label.config(text=f"❌ Device not connected (ID: {self.device_id})", foreground="red")
            elif not shell_working:
                self.connection_status_label.config(text="❌ Shell connection failed", foreground="red")
            else:
                self.connection_status_label.config(text="✅ Ready", foreground="green")
        
        # Save previous connection state
        previous_status = self.all_connected if hasattr(self, 'all_connected') else False
        
        # Save overall connection state
        self.all_connected = all_ok
        
        # Upload script only when state changes from disconnected -> connected
        if hasattr(self, 'last_shell_status'):
            if not self.last_shell_status and shell_working:
                # Previously disconnected, now connected
                self.upload_mfl_script_silent()
            self.last_shell_status = shell_working
        
        # Log when connection is lost
        if previous_status and not all_ok:
            self.output_text.insert(tk.END, f"[Disconnected] Device connection was lost.\n")
            self.output_text.see(tk.END)

    def upload_mfl_script_silent(self):
        """Create and upload mfl_total.sh silently."""
        def upload_thread():
            try:
                script_path = os.path.join(self.current_directory, "mfl_total.sh")
                
                # Create the script if missing
                if not os.path.exists(script_path):
                    self.create_mfl_script_file_only(script_path)
                
                # 1) Upload
                push_cmd = self.get_adb_command(f'push "{script_path}" /tmp/')
                push_process = subprocess.Popen(
                    push_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='cp949',
                    cwd=self.current_directory
                )
                push_stdout, push_stderr = push_process.communicate(timeout=30)
                
                if push_process.returncode != 0:
                    # Stop on upload failure
                    return
                
                # 2) Grant execute permission (only if upload succeeded)
                chmod_cmd = self.get_adb_command('shell chmod +x /tmp/mfl_total.sh')
                chmod_process = subprocess.Popen(
                    chmod_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='cp949',
                    cwd=self.current_directory
                )
                chmod_stdout, chmod_stderr = chmod_process.communicate(timeout=15)
                
                # Ignore chmod result (some systems may restrict permission changes)
                    
            except subprocess.TimeoutExpired:
                # Exit silently even on timeout
                pass
            except Exception as e:
                # Exit silently on other exceptions
                pass
        
        thread = threading.Thread(target=upload_thread)
        thread.daemon = True
        thread.start()

    def create_mfl_script_file_only(self, script_path):
        """Create only the mfl_total.sh file (no logs)."""
        script_content = '''#!/bin/bash

if [ "$1" = "up" ]; then
    echo "up."
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "down" ]; then
    echo "down"
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menuup" ]; then
    echo "menuup"
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menudown" ]; then
    echo "menudown"
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "ok" ]; then
    echo "ok"
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "view" ]; then
    echo "view"
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "fas" ]; then
    echo "fas"
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "signal" ]; then
    dpid="$2"
    value="$3"
    if [ -z "$dpid" ] || [ -z "$value" ]; then
        echo "Usage: $0 signal <DPID_NAME> <VALUE>"
        exit 1
    fi
    echo "signal: $dpid = $value"
    IpcSender --dpid "$dpid" 0 "$value" > /dev/null 2>&1
else
    echo "Unknown Command."
fi
'''
        with open(script_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(script_content)
        
        try:
            import stat
            os.chmod(script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
        except:
            pass

    def update_all_adb_status(self):
        """Update overall ADB status."""
        # Show start message in main output
        self.output_text.insert(tk.END, "[Settings] Starting full ADB status check...\n")
        self.output_text.see(tk.END)

        # Check all ADB status in a background thread
        def check_all_adb_thread():
            # 1) Check ADB installation status
            adb_installed, adb_message = self.check_adb_installation()
            self.root.after(0, lambda: self.show_adb_install_result(adb_installed, adb_message))

            if adb_installed:
                # 2) Check device connection status
                device_connected, device_message = self.check_adb_devices()
                self.root.after(0, lambda: self.show_device_result(device_connected, device_message))

                # 3) ADB Shell test
                shell_working, shell_message = self.check_adb_shell()
                self.root.after(0, lambda: self.show_shell_result(shell_working, shell_message))
            else:
                # If ADB is not installed, skip the remaining tests
                self.root.after(0, lambda: self.show_device_result(False, "ADB is not installed, so device status cannot be checked."))
                self.root.after(0, lambda: self.show_shell_result(False, "ADB is not installed, so the shell test cannot be run."))

        thread = threading.Thread(target=check_all_adb_thread)
        thread.daemon = True
        thread.start()

    def show_adb_install_result(self, is_installed, message):
        """Show ADB installation check result."""
        # Update settings window status label
        if hasattr(self, 'adb_status_label'):
            if is_installed:
                self.adb_status_label.config(text=f"✅ {message}", foreground="green")
            else:
                self.adb_status_label.config(text=f"❌ {message}", foreground="red")

        # Also show result in the main output
        if is_installed:
            self.output_text.insert(tk.END, f"[Settings] ✅ ADB: {message}\n")
        else:
            self.output_text.insert(tk.END, f"[Settings] ❌ ADB: {message}\n")
            self.output_text.insert(tk.END, "[Settings] How to install ADB: Download Android SDK Platform Tools and add it to PATH.\n")

        self.output_text.see(tk.END)

    def show_device_result(self, is_connected, message):
        """Show device connection check result."""
        # Update settings window status label
        if hasattr(self, 'device_status_label'):
            if is_connected:
                self.device_status_label.config(text=f"✅ {message}", foreground="green")
            else:
                self.device_status_label.config(text=f"❌ {message}", foreground="red")

        # Also show result in the main output
        if is_connected:
            self.output_text.insert(tk.END, f"[Settings] ✅ Device: {message}\n")
        else:
            self.output_text.insert(tk.END, f"[Settings] ❌ Device: {message}\n")
            if "No devices" in message or "no devices" in message:
                self.output_text.insert(tk.END, "[Settings] Fix: Enable USB debugging and connect the device.\n")

        self.output_text.see(tk.END)

    def show_shell_result(self, is_working, message):
        """Show ADB Shell test result."""
        # Update settings window status label
        if hasattr(self, 'shell_status_label'):
            if is_working:
                self.shell_status_label.config(text=f"✅ {message}", foreground="green")
            else:
                self.shell_status_label.config(text=f"❌ {message}", foreground="red")

        # Update main window traffic light
        if hasattr(self, 'status_canvas'):
            color = "#00FF00" if is_working else "#FF0000"  # Bright green or red
            self.status_canvas.itemconfig(self.status_light, fill=color, outline=color)

        # Also show result in the main output
        if is_working:
            self.output_text.insert(tk.END, f"[Settings] ✅ ADB Shell: {message}\n")
        else:
            self.output_text.insert(tk.END, f"[Settings] ❌ ADB Shell: {message}\n")
            message_lc = (message or "").lower()
            if "unauthorized" in message_lc or "not authorized" in message_lc:
                self.output_text.insert(
                    tk.END,
                    "[Settings] Fix: Approve the USB debugging authorization prompt on the device.\n",
                )

        self.output_text.insert(tk.END, "="*60 + "\n")
        self.output_text.see(tk.END)

        # Upload the script only after all checks pass and shell connection succeeds
        if is_working:
            self.create_mfl_script()
        else:
            # If connection fails, only create the script locally
            self.create_mfl_script_local_only()

    def browse_adb_folder(self):
        """Select an ADB folder and apply it automatically."""
        from tkinter import filedialog

        # Folder selection dialog
        folder_path = filedialog.askdirectory(
            title="Select the folder containing ADB",
            initialdir=self.adb_folder if self.adb_folder else os.getcwd()
        )

        if folder_path:
            # Validate folder
            if not os.path.exists(folder_path):
                messagebox.showerror("Error", f"The selected folder does not exist:\n{folder_path}")
                return

            if not os.path.isdir(folder_path):
                messagebox.showerror("Error", f"The selected path is not a folder:\n{folder_path}")
                return

            # Check for adb.exe
            adb_exe_path = os.path.join(folder_path, "adb.exe")
            if not os.path.exists(adb_exe_path):
                result = messagebox.askyesno(
                    "Confirm",
                    f"adb.exe was not found in the selected folder:\n{folder_path}\n\nUse this folder anyway?",
                )
                if not result:
                    return

            # Apply folder
            old_folder = self.adb_folder
            self.adb_folder = folder_path

            # Save settings
            self.save_adb_settings()

            # Update UI
            if hasattr(self, 'current_adb_folder_label'):
                self.current_adb_folder_label.config(text=self.adb_folder)

            # Log to the main output
            self.log_to_output(f"[Settings] ADB folder changed: {old_folder or 'Default'} -> {self.adb_folder}")

            # Re-check ADB status with the new folder (no alert)
            self.update_all_adb_status()

    def reset_adb_folder(self):
        """Reset the ADB folder to default."""
        old_folder = self.adb_folder
        self.adb_folder = ""

        # Save settings
        self.save_adb_settings()

        # Update UI
        if hasattr(self, 'current_adb_folder_label'):
            self.current_adb_folder_label.config(text="Default (search on PATH)")

        self.log_to_output(
            f"[Settings] ADB folder reset: {old_folder or 'Default'} -> Default (search on PATH)"
        )
        self.update_all_adb_status()

    def create_mfl_script(self):
        """Create the mfl_total.sh shell script file."""
        try:
            script_path = os.path.join(self.current_directory, "mfl_total.sh")

            # Generate shell script content (user-provided content)
            script_content = '''#!/bin/bash

if [ "$1" = "up" ]; then
    echo "up."
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "down" ]; then
    echo "down"
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menuup" ]; then
    echo "menuup"
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menudown" ]; then
    echo "menudown"
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "ok" ]; then
    echo "ok"
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "view" ]; then
    echo "view"
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "fas" ]; then
    echo "fas"
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "signal" ]; then
    dpid="$2"
    value="$3"
    if [ -z "$dpid" ] || [ -z "$value" ]; then
        echo "Usage: $0 signal <DPID_NAME> <VALUE>"
        exit 1
    fi
    echo "signal: $dpid = $value"
    IpcSender --dpid "$dpid" 0 "$value" > /dev/null 2>&1
else
    echo "Unknown Command."
fi
'''

            # Save file
            with open(script_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(script_content)

            # Grant execute permission (primarily on Unix-like systems)
            try:
                import stat
                os.chmod(script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
            except:
                pass  # chmod behavior may be limited on Windows

            self.log_to_output(f"[Script Created] mfl_total.sh was created: {script_path}")

            # Upload to the device only if ADB Shell connectivity is confirmed
            self.upload_script_to_device(script_path)

        except Exception as e:
            self.log_to_output(f"[Script Create Error] {str(e)}")

    def create_mfl_script_local_only(self):
        """Create the mfl_total.sh shell script (local only, no upload)."""
        try:
            script_path = os.path.join(self.current_directory, "mfl_total.sh")

            # Do not recreate if it already exists
            if os.path.exists(script_path):
                self.log_to_output(f"[Script] mfl_total.sh already exists: {script_path}")
                return

            # Generate script content
            script_content = '''#!/bin/bash

if [ "$1" = "up" ]; then
    echo "up."
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "down" ]; then
    echo "down"
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menuup" ]; then
    echo "menuup"
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menudown" ]; then
    echo "menudown"
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "ok" ]; then
    echo "ok"
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "view" ]; then
    echo "view"
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "fas" ]; then
    echo "fas"
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "signal" ]; then
    dpid="$2"
    value="$3"
    if [ -z "$dpid" ] || [ -z "$value" ]; then
        echo "Usage: $0 signal <DPID_NAME> <VALUE>"
        exit 1
    fi
    echo "signal: $dpid = $value"
    IpcSender --dpid "$dpid" 0 "$value" > /dev/null 2>&1
else
    echo "Unknown Command."
fi
'''

            # Save file
            with open(script_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(script_content)

            # Grant execute permission
            try:
                import stat
                os.chmod(script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
            except:
                pass

            self.log_to_output(f"[Script] mfl_total.sh was created: {script_path}")
            self.log_to_output("[Script] It will be uploaded automatically after the device connects.")

        except Exception as e:
            self.log_to_output(f"[Script Create Error] {str(e)}")

    def upload_script_to_device(self, script_path):
        """Upload script to the device and grant execute permission."""
        try:
            # 1. Upload the script via adb push
            self.log_to_output("[Script Upload] Uploading mfl_total.sh to the device...")
            push_cmd = self.get_adb_command(f'push "{script_path}" /tmp/')

            push_process = subprocess.Popen(
                push_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            push_stdout, push_stderr = push_process.communicate(timeout=30)

            self.log_to_output(f"[Script Upload] Return code: {push_process.returncode}")
            if push_stdout.strip():
                self.log_to_output(f"[Script Upload] STDOUT:\n{push_stdout}")
            if push_stderr.strip():
                self.log_to_output(f"[Script Upload] STDERR:\n{push_stderr}")

            if push_process.returncode == 0:
                self.log_to_output("[Script Upload] ✅ Upload succeeded")
            else:
                self.log_to_output("[Script Upload] ❌ Upload failed")
                if "no devices/emulators found" in push_stderr:
                    self.log_to_output("[Script Upload] No device is connected.")
                elif "device unauthorized" in push_stderr:
                    self.log_to_output("[Script Upload] Device authorization is required.")
                # Even if upload fails, still try chmod (file may already exist)

            # 2. Grant execute permission via chmod +x (attempt regardless of upload result)
            self.log_to_output("[Chmod] Granting execute permission to /tmp/mfl_total.sh...")
            chmod_cmd = self.get_adb_command('shell chmod +x /tmp/mfl_total.sh')

            chmod_process = subprocess.Popen(
                chmod_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            chmod_stdout, chmod_stderr = chmod_process.communicate(timeout=15)

            self.log_to_output(f"[Chmod] Return code: {chmod_process.returncode}")
            if chmod_stdout.strip():
                self.log_to_output(f"[Chmod] STDOUT:\n{chmod_stdout}")
            if chmod_stderr.strip():
                self.log_to_output(f"[Chmod] STDERR:\n{chmod_stderr}")

            if chmod_process.returncode == 0:
                self.log_to_output("[Chmod] ✅ Execute permission granted")
                self.log_to_output("[Deploy] ✅ mfl_total.sh deployed to device")
                self.log_to_output("[Usage] On the device: /tmp/mfl_total.sh [up|down|menuup|menudown|ok|view|fas]")
            else:
                self.log_to_output("[Chmod] ❌ Failed to grant execute permission")

        except subprocess.TimeoutExpired:
            self.log_to_output("[Script Upload] ❌ Upload timed out")
        except Exception as e:
            self.log_to_output(f"[Script Upload Error] {str(e)}")

    # Keypad functions
    def go_home(self):
        """Run the FAS button (keypad 1)."""
        self.output_text.insert(tk.END, "[1] Run FAS\n")
        self.execute_mfl_command("fas")

    def move_up(self):
        """Run the UP button (keypad 2)."""
        self.output_text.insert(tk.END, "[2] Run UP\n")
        self.execute_mfl_command("up")

    def refresh_dir(self):
        """Refresh current directory (keypad 9)."""
        self.output_text.insert(tk.END, f"[9] Refresh current directory: {self.current_directory}\n")
        self.set_command("dir")
        self.run_command()

    def move_left(self):
        """Run the MENU UP button (keypad 4)."""
        self.output_text.insert(tk.END, "[4] Run MENU UP\n")
        self.execute_mfl_command("menuup")

    def move_right(self):
        """Run the MENU DOWN button (keypad 6)."""
        self.output_text.insert(tk.END, "[6] Run MENU DOWN\n")
        self.execute_mfl_command("menudown")

    def move_down(self):
        """Run the DOWN button (keypad 8)."""
        self.output_text.insert(tk.END, "[8] Run DOWN\n")
        self.execute_mfl_command("down")

    def focus_signal_input(self):
        """Move focus to the SIGNAL input field (keypad 7)."""
        try:
            if hasattr(self, 'signal_name_entry') and self.signal_name_entry.winfo_exists():
                self.signal_name_entry.focus_set()
                self.signal_name_entry.selection_range(0, tk.END)
        except Exception:
            pass

    def send_custom_signal(self):
        """Send user-provided signal name/value via IpcSender."""
        signal_name = (self.signal_name_var.get() if hasattr(self, 'signal_name_var') else "").strip()
        signal_value = (self.signal_value_var.get() if hasattr(self, 'signal_value_var') else "").strip()

        if not signal_name:
            messagebox.showwarning("Input Required", "Please enter a signal name.")
            self.focus_signal_input()
            return

        # Basic safety validation (prevent shell injection + enforce IpcSender argument format)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", signal_name):
            messagebox.showwarning(
                "Format Error",
                "Signal name may only contain letters, numbers, and underscores. (e.g., DP_ID_SOMETHING)",
            )
            self.focus_signal_input()
            return

        if not signal_value:
            messagebox.showwarning("Input Required", "Please enter a signal value. (e.g., 0 or 1)")
            try:
                self.signal_value_entry.focus_set()
                self.signal_value_entry.selection_range(0, tk.END)
            except Exception:
                pass
            return

        if not re.fullmatch(r"-?\d+", signal_value):
            messagebox.showwarning("Format Error", "Signal value must be an integer. (e.g., 0, 1, -1)")
            try:
                self.signal_value_entry.focus_set()
                self.signal_value_entry.selection_range(0, tk.END)
            except Exception:
                pass
            return

        # adb shell IpcSender --dpid <name> 0 <value>
        # NOTE: Do not use host-side redirection like `> /dev/null` on Windows.
        shell_cmd = f'shell IpcSender --dpid {signal_name} 0 {signal_value}'
        adb_cmd = self.get_adb_command(shell_cmd)

        self.output_text.insert(tk.END, f"[SIGNAL] {signal_name} = {signal_value}\n")
        self.output_text.insert(tk.END, f"Command: {adb_cmd}\n")
        self.output_text.see(tk.END)

        def execute_thread():
            try:
                process = subprocess.Popen(
                    adb_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='cp949',
                    cwd=self.current_directory
                )
                stdout, stderr = process.communicate(timeout=10)
                self.root.after(0, lambda: self.show_signal_result(signal_name, signal_value, stdout, stderr, process.returncode))
            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: self.show_signal_error(signal_name, signal_value, "Command execution timed out"))
            except Exception as e:
                self.root.after(0, lambda: self.show_signal_error(signal_name, signal_value, str(e)))

        thread = threading.Thread(target=execute_thread)
        thread.daemon = True
        thread.start()

    def send_adas_preset(self):
        """Preset: send a batch of ADAS-related DPIDs/values."""
        pairs = [
            ("DP_ID_S_FOD_STATE_ACC", "1"),
            ("DP_ID_B_TA_FOD_STATUS", "1"),
            ("DP_ID_DP_LDW_VERBAUT", "1"),
            ("DP_ID_B_LDW_LERNMODUS_SEITENABHAENGIG", "15"),
            ("DP_ID_B_ACC_STATUSICON", "5"),
            ("DP_ID_B_TA_AKTIV_HMI", "1"),
            ("DP_ID_B_TA_HMI_EGO_LI_TYP", "3"),
            ("DP_ID_B_TA_HMI_EGO_RE_TYP", "3"),
            ("DP_ID_B_TA_HMI_NACHB_LI_TYP", "2"),
            ("DP_ID_B_TA_HMI_NACHB_RE_TYP", "2"),
            ("DP_ID_B_TA_HMI_TAZOOMSTUFEAKTIV", "1"),
            ("DP_ID_B_TA_HMI_SEG1_KRUEMMUNG", "2048"),
            ("DP_ID_B_TA_HMI_SEG2_KRUEMMUNG", "2048"),
            ("DP_ID_B_TA_HMI_SEG1_GIERWINKEL", "2048"),
            ("DP_ID_B_TA_HMI_SEG2_BEGINN", "0"),
            ("DP_ID_B_TA_HMI_EGOOBJ_DY", "64"),
        ]

        self.output_text.insert(tk.END, "[PRESET] ADAS batch send\n")
        self.output_text.see(tk.END)

        def execute_thread():
            for signal_name, signal_value in pairs:
                try:
                    shell_cmd = f'shell IpcSender --dpid {signal_name} 0 {signal_value}'
                    adb_cmd = self.get_adb_command(shell_cmd)
                    process = subprocess.Popen(
                        adb_cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='cp949',
                        cwd=self.current_directory,
                    )
                    stdout, stderr = process.communicate(timeout=10)
                    self.root.after(
                        0,
                        lambda n=signal_name, v=signal_value, out=stdout, err=stderr, rc=process.returncode: self.show_signal_result(
                            n, v, out, err, rc
                        ),
                    )
                except subprocess.TimeoutExpired:
                    self.root.after(0, lambda n=signal_name, v=signal_value: self.show_signal_error(n, v, "Command execution timed out"))
                except Exception as e:
                    self.root.after(0, lambda n=signal_name, v=signal_value, msg=str(e): self.show_signal_error(n, v, msg))

        thread = threading.Thread(target=execute_thread)
        thread.daemon = True
        thread.start()

    def send_navigation_preset(self):
        """Preset: send a batch of Navigation-related DPIDs/values."""
        pairs = [
            ("DP_ID_BAP_NAVI_VIDEOSTREAMS_AVAILABLE", "1"),
            ("DP_ID_BAP_NAVI_ACTIVERGTYPE_RGTYPE", "3"),
            ("DP_ID_HMI_NAVI_VIDEOSTREAM_VIDEODATA_READY", "1"),
            ("DP_ID_BAP_NAVIGATION_AVAILABLE", "1"),
            ("DP_ID_BAP_NAVI_FSG_OPERATIONSTATE_OP_STATE", "0"),
        ]

        self.output_text.insert(tk.END, "[PRESET] Navigation batch send\n")
        self.output_text.see(tk.END)

        def execute_thread():
            for signal_name, signal_value in pairs:
                try:
                    shell_cmd = f'shell IpcSender --dpid {signal_name} 0 {signal_value}'
                    adb_cmd = self.get_adb_command(shell_cmd)
                    process = subprocess.Popen(
                        adb_cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='cp949',
                        cwd=self.current_directory,
                    )
                    stdout, stderr = process.communicate(timeout=10)
                    self.root.after(
                        0,
                        lambda n=signal_name, v=signal_value, out=stdout, err=stderr, rc=process.returncode: self.show_signal_result(
                            n, v, out, err, rc
                        ),
                    )
                except subprocess.TimeoutExpired:
                    self.root.after(
                        0,
                        lambda n=signal_name, v=signal_value: self.show_signal_error(
                            n, v, "Command execution timed out"
                        ),
                    )
                except Exception as e:
                    self.root.after(
                        0,
                        lambda n=signal_name, v=signal_value, msg=str(e): self.show_signal_error(
                            n, v, msg
                        ),
                    )

        thread = threading.Thread(target=execute_thread)
        thread.daemon = True
        thread.start()

    def send_long_view_preset(self):
        """Key 11: send the LONG VIEW press/release sequence (twice)."""
        pairs = [
            ("DP_ID_HMI_VIEW_LONG_PRESS", "1"),
            ("DP_ID_HMI_VIEW_LONG_PRESS", "0"),
            ("DP_ID_HMI_VIEW_LONG_PRESS_RELEASE", "1"),
            ("DP_ID_HMI_VIEW_LONG_PRESS_RELEASE", "0"),
        ]

        self.output_text.insert(tk.END, "[KEY] LONG VIEW (11) sequence send\n")
        self.output_text.see(tk.END)

        def execute_thread():
            for signal_name, signal_value in pairs:
                try:
                    shell_cmd = f'shell IpcSender --dpid {signal_name} 0 {signal_value}'
                    adb_cmd = self.get_adb_command(shell_cmd)
                    process = subprocess.Popen(
                        adb_cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='cp949',
                        cwd=self.current_directory,
                    )
                    stdout, stderr = process.communicate(timeout=10)
                    self.root.after(
                        0,
                        lambda n=signal_name, v=signal_value, out=stdout, err=stderr, rc=process.returncode: self.show_signal_result(
                            n, v, out, err, rc
                        ),
                    )
                except subprocess.TimeoutExpired:
                    self.root.after(
                        0,
                        lambda n=signal_name, v=signal_value: self.show_signal_error(
                            n, v, "Command execution timed out"
                        ),
                    )
                except Exception as e:
                    self.root.after(
                        0,
                        lambda n=signal_name, v=signal_value, msg=str(e): self.show_signal_error(
                            n, v, msg
                        ),
                    )

        thread = threading.Thread(target=execute_thread)
        thread.daemon = True
        thread.start()

    def show_signal_result(self, signal_name, signal_value, stdout, stderr, returncode):
        """Show the result of sending a user signal."""
        combined_output = f"{stdout or ''}\n{stderr or ''}".strip()
        device_parse_error = (
            "[CMessage][ParsingDPID]" in combined_output
            and "can_dpid_msg_lut" in combined_output
        )

        if returncode == 0 and not device_parse_error:
            self.output_text.insert(tk.END, f"✅ SIGNAL sent: {signal_name} = {signal_value}\n")
            if stdout.strip():
                self.output_text.insert(tk.END, f"Output: {stdout.strip()}\n")
        else:
            self.output_text.insert(tk.END, f"❌ SIGNAL failed (code: {returncode}): {signal_name} = {signal_value}\n")
            if device_parse_error:
                self.output_text.insert(
                    tk.END,
                    "Error: The device could not parse the DPID. (Not registered in can_dpid_msg_lut)\n"
                )
                self.output_text.insert(
                    tk.END,
                    "Hint: Add a mapping for this DPID to can_dpid_msg_lut in HMISource/Inc/ODI/ODILut.h.\n"
                )

            if stderr.strip():
                self.output_text.insert(tk.END, f"Error: {stderr.strip()}\n")
            if stdout.strip() and device_parse_error:
                self.output_text.insert(tk.END, f"Output: {stdout.strip()}\n")
            if "no devices" in stderr.lower() or "unauthorized" in stderr.lower() or "offline" in stderr.lower():
                self.output_text.insert(tk.END, "Check connection status. (Click Settings)\n")

        self.output_text.insert(tk.END, "-" * 40 + "\n")
        self.output_text.see(tk.END)

    def show_signal_error(self, signal_name, signal_value, error_msg):
        """Show an error for sending a user signal."""
        self.output_text.insert(tk.END, f"❌ SIGNAL error: {signal_name} = {signal_value} / {error_msg}\n")
        if "timeout" in error_msg.lower() or "no devices" in error_msg.lower():
            self.output_text.insert(tk.END, "Check connection status. (Click Settings)\n")
        self.output_text.insert(tk.END, "-" * 40 + "\n")
        self.output_text.see(tk.END)
    
    def run_command(self):
        """Run the OK button (keypad 5)."""
        self.output_text.insert(tk.END, "[5] Run OK\n")
        self.execute_mfl_command("ok")
    
    def handle_cd_command(self, command):
        """Handle the cd command."""
        try:
            path = command[3:].strip()
            if not path:
                path = os.path.expanduser("~")
            
            if path == "..":
                path = os.path.dirname(self.current_directory)
            elif not os.path.isabs(path):
                path = os.path.join(self.current_directory, path)
            
            if os.path.exists(path) and os.path.isdir(path):
                self.current_directory = os.path.abspath(path)
                os.chdir(self.current_directory)
                self.update_directory_label()
                self.output_text.insert(tk.END, f"Directory changed: {self.current_directory}\n")
            else:
                self.output_text.insert(tk.END, f"Error: Directory not found: {path}\n")
            
            self.output_text.see(tk.END)
            
        except Exception as e:
            self.output_text.insert(tk.END, f"cd command error: {str(e)}\n")
            self.output_text.see(tk.END)
    
    def execute_command(self, command):
        """Run a command and display the result."""
        try:
            # Execute command in Windows environment
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',  # Windows code page (commonly used for Korean output)
                cwd=self.current_directory,
                universal_newlines=True
            )
            
            # Capture output
            stdout, stderr = process.communicate()
            
            # Update UI on the main thread
            self.root.after(0, self.show_result, stdout, stderr, process.returncode)
            
        except Exception as e:
            self.root.after(0, self.show_error, str(e))
    
    def show_result(self, stdout, stderr, returncode):
        """Show command execution result."""
        if stdout:
            self.output_text.insert(tk.END, stdout)
        
        if stderr:
            self.output_text.insert(tk.END, f"\nError output:\n{stderr}")
        
        if returncode != 0:
            self.output_text.insert(tk.END, f"\nExit code: {returncode}\n")
        
        self.output_text.insert(tk.END, "\n" + "="*60 + "\n")
        self.output_text.see(tk.END)
        
        # Re-enable run button (keypad 5)
        if hasattr(self, 'keypad_btns') and (1, 1) in self.keypad_btns:
            self.keypad_btns[(1, 1)].config(state=tk.NORMAL)
        self.cmd_entry.focus()
    
    def show_error(self, error):
        """Show an error message."""
        self.output_text.insert(tk.END, f"\nExecution error: {error}\n")
        self.output_text.insert(tk.END, "="*60 + "\n")
        self.output_text.see(tk.END)
        
        if hasattr(self, 'keypad_btns') and (1, 1) in self.keypad_btns:
            self.keypad_btns[(1, 1)].config(state=tk.NORMAL)
        self.cmd_entry.focus()
    
    def clear_output(self):
        """Clear the output window."""
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, "CMD GUI Tool - output window cleared.\n")
        self.output_text.insert(tk.END, "="*60 + "\n")
    
    def save_output(self):
        """Run the VIEW button (keypad 9)."""
        self.output_text.insert(tk.END, "[9] Run VIEW\n")
        self.execute_mfl_command("view")

    def execute_mfl_command(self, button_name):
        """Execute an MFL script command."""
        try:
            # Build adb shell /tmp/mfl_total.sh [button_name] command
            mfl_cmd = self.get_adb_command(f'shell /tmp/mfl_total.sh {button_name}')
            self.output_text.insert(tk.END, f"Command: {mfl_cmd}\n")
            self.output_text.see(tk.END)

            # Execute in a separate thread
            def execute_thread():
                try:
                    process = subprocess.Popen(
                        mfl_cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='cp949',
                        cwd=self.current_directory
                    )
                    stdout, stderr = process.communicate(timeout=10)

                    # Show results on the main thread
                    self.root.after(0, lambda: self.show_mfl_result(button_name, stdout, stderr, process.returncode))

                except subprocess.TimeoutExpired:
                    self.root.after(0, lambda: self.show_mfl_error(button_name, "Command execution timed out", True))
                except Exception as e:
                    self.root.after(0, lambda: self.show_mfl_error(button_name, str(e), True))

            thread = threading.Thread(target=execute_thread)
            thread.daemon = True
            thread.start()

        except Exception as e:
            self.output_text.insert(tk.END, f"MFL command error: {str(e)}\n")
            self.output_text.see(tk.END)

    def show_mfl_result(self, button_name, stdout, stderr, returncode):
        """Show the result of executing an MFL command."""
        if returncode == 0:
            self.output_text.insert(tk.END, f"✅ {button_name.upper()} executed successfully\n")
            if stdout.strip():
                self.output_text.insert(tk.END, f"Output: {stdout.strip()}\n")
        else:
            self.output_text.insert(tk.END, f"❌ {button_name.upper()} failed (code: {returncode})\n")
            if stderr.strip():
                self.output_text.insert(tk.END, f"Error: {stderr.strip()}\n")
            
            # Show guidance only for connectivity-related issues
            if "no devices" in stderr or "unauthorized" in stderr or "offline" in stderr:
                self.output_text.insert(tk.END, "Check connection status. (Click Settings)\n")

        self.output_text.insert(tk.END, "-" * 40 + "\n")
        self.output_text.see(tk.END)

    def show_mfl_error(self, button_name, error_msg, open_settings=False):
        """Show an error for executing an MFL command."""
        self.output_text.insert(tk.END, f"❌ {button_name.upper()} error: {error_msg}\n")

        # Show guidance only for timeout/connectivity issues
        if "timeout" in error_msg.lower() or "no devices" in error_msg.lower():
            self.output_text.insert(tk.END, "Check connection status. (Click Settings)\n")

        self.output_text.insert(tk.END, "-" * 40 + "\n")
        self.output_text.see(tk.END)

def main():
    """Main entry point."""
    # Create Tkinter root window
    root = tk.Tk()
    
    # Icon setup (optional)
    try:
        # Set a default icon on Windows
        root.iconbitmap(default='')
    except:
        pass
    
    # Start application
    app = CMDGui(root)
    
    # Startup message
    app.output_text.insert(tk.END, "FPK ADB CMD Sender started - HMI button control\n")
    app.output_text.insert(tk.END, f"Current directory: {os.getcwd()}\n")
    app.output_text.insert(tk.END, "HMI keypad usage:\n")
    app.output_text.insert(tk.END, "1(Home):FAS  2(▲):UP  3:ADAS\n")
    app.output_text.insert(tk.END, "4(◀):MENU UP  5(Enter):OK  6(▶):MENU DOWN\n")
    app.output_text.insert(tk.END, "7:SIGNAL input  8(▼):DOWN  9(PgDn):VIEW\n")
    app.output_text.insert(tk.END, "10:Navigation  11:LONG VIEW\n")
    app.output_text.insert(tk.END, "0:Clear Log\n")
    app.output_text.insert(tk.END, "="*60 + "\n")
    
    # Set initial focus
    app.cmd_entry.focus()
    
    # Run GUI
    root.mainloop()

if __name__ == "__main__":
    main()
