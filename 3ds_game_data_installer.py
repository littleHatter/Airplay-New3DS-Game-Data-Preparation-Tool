"""New Nintendo 3DS game-data preparer: Windows-friendly GUI, no Python install after packaging."""
from __future__ import annotations

import queue
import threading
import traceback
import tkinter as tk
import sys
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from installer_backend import GAMES, prepare_game


GAME_IDS = list(GAMES)
GAME_LABELS = [GAMES[key]['title'] for key in GAME_IDS]


class GameDataInstaller(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Airplay New 3DS Game Data Preparation Tool')
        self.geometry('800x780')
        self.minsize(700, 660)
        self.events = queue.Queue()
        self.busy = False
        self.fields: dict[str, tk.StringVar] = {}
        self.game = tk.StringVar(value=GAME_LABELS[0])
        self.destination = tk.StringVar()
        self.ffmpeg = tk.StringVar()
        self.status = tk.StringVar(value='Ready')
        self._apply_icon()
        self._configure_theme()
        self._create_widgets()
        self._show_game_fields()
        self.after(120, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _apply_icon(self):
        try:
            if hasattr(sys, '_MEIPASS'):
                base = Path(sys._MEIPASS)
            else:
                base = Path(__file__).resolve().parent
            icon_png = base / 'app_icon.png'
            if icon_png.is_file():
                self._icon_image = tk.PhotoImage(file=str(icon_png))
                self.iconphoto(True, self._icon_image)
            icon_ico = base / 'app_icon.ico'
            if sys.platform.startswith('win') and icon_ico.is_file():
                try:
                    self.iconbitmap(default=str(icon_ico))
                except tk.TclError:
                    pass
        except Exception:
            pass

    def _close(self):
        if self.busy:
            messagebox.showwarning("Preparation in progress",
                "Please let the file preparation finish before closing this window.", parent=self)
            return
        self.destroy()

    def _configure_theme(self):
        style = ttk.Style(self)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        elif 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('TButton', padding=(10, 6))
        style.configure('Heading.TLabel', font=('Segoe UI', 16, 'bold'))
        style.configure('Hint.TLabel', foreground='#5d6878', wraplength=720)
        style.configure('Section.TLabel', font=('Segoe UI', 10, 'bold'))

    def _create_widgets(self):
        main = ttk.Frame(self, padding=(22, 18))
        main.pack(fill=tk.BOTH, expand=True)

        # Pack the action footer FIRST, anchored to the bottom. The flexible
        # activity log in the body yields height before this button is hidden.
        footer = ttk.Frame(main)
        footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        self.start = ttk.Button(footer, text='Prepare game files', command=self._start)
        self.start.pack(side=tk.RIGHT)
        ttk.Label(footer, text='Existing saves and unrelated SD files are preserved.',
                  style='Hint.TLabel').pack(side=tk.LEFT, fill=tk.X, expand=True)

        body = ttk.Frame(main)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        ttk.Label(body, text='Airplay New 3DS Game Data Preparation Tool', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(body, text='Build the required game-data folders from your own original releases. No commercial game files are included.',
                  style='Hint.TLabel').pack(anchor='w', pady=(4, 14))
        ttk.Label(body, text='Choose game', style='Section.TLabel').pack(anchor='w', pady=(0, 5))
        self.selector = ttk.Combobox(body, state='readonly', textvariable=self.game, values=GAME_LABELS)
        self.selector.pack(fill=tk.X)
        self.selector.bind('<<ComboboxSelected>>', lambda event: self._show_game_fields())
        self.hint = ttk.Label(body, text='', style='Hint.TLabel')
        self.hint.pack(fill=tk.X, anchor='w', pady=(7, 10))
        self.inputs_frame = ttk.LabelFrame(body, text='Original game files', padding=(12, 9))
        self.inputs_frame.pack(fill=tk.X, pady=(0, 12))
        output = ttk.LabelFrame(body, text='Output folder', padding=(12, 9))
        output.pack(fill=tk.X)
        ttk.Label(output, text='Choose an SD-card root or empty staging folder; the required 3ds/ subfolders are created automatically.',
                  style='Hint.TLabel').pack(anchor='w', pady=(0, 7))
        row = ttk.Frame(output)
        row.pack(fill=tk.X)
        self.destination_entry = ttk.Entry(row, textvariable=self.destination)
        self.destination_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.output_browse = ttk.Button(row, text='Browse...', command=self._browse_output)
        self.output_browse.pack(side=tk.LEFT, padx=(8, 0))
        self.ffmpeg_frame = ttk.LabelFrame(body, text='Pandemonium! video conversion', padding=(12, 9))
        ttk.Label(self.ffmpeg_frame, text='Optional override: leave empty to use bundled/adjacent FFmpeg or the PATH.',
                  style='Hint.TLabel').pack(anchor='w')
        ffrow = ttk.Frame(self.ffmpeg_frame)
        ffrow.pack(fill=tk.X, pady=(6, 0))
        self.ffmpeg_entry = ttk.Entry(ffrow, textvariable=self.ffmpeg)
        self.ffmpeg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ffmpeg_browse = ttk.Button(ffrow, text='Browse...', command=self._browse_ffmpeg)
        self.ffmpeg_browse.pack(side=tk.LEFT, padx=(8, 0))
        progress_row = ttk.Frame(body)
        progress_row.pack(fill=tk.X, pady=(14, 5))
        ttk.Label(progress_row, text='Activity', style='Section.TLabel').pack(side=tk.LEFT)
        ttk.Label(progress_row, textvariable=self.status).pack(side=tk.RIGHT)
        self.progress = ttk.Progressbar(body, mode='indeterminate')
        self.progress.pack(fill=tk.X)
        self.logs = scrolledtext.ScrolledText(body, wrap='word', height=8, state='disabled', font=('Consolas', 9))
        self.logs.pack(fill=tk.BOTH, expand=True, pady=(8, 10))

    def _game_id(self) -> str:
        return GAME_IDS[GAME_LABELS.index(self.game.get())]

    def _show_game_fields(self):
        for child in self.inputs_frame.winfo_children():
            child.destroy()
        self.fields = {}
        selected = self._game_id()
        self.hint.configure(text=GAMES[selected]['hint'])
        for key, label, kind in GAMES[selected]['inputs']:
            self.fields[key] = tk.StringVar()
            ttk.Label(self.inputs_frame, text=label).pack(anchor='w', pady=(3, 3))
            row = ttk.Frame(self.inputs_frame)
            row.pack(fill=tk.X, pady=(0, 5))
            ttk.Entry(row, textvariable=self.fields[key]).pack(side=tk.LEFT, fill=tk.X, expand=True)
            if kind == 'either':
                ttk.Button(row, text='File...', command=lambda k=key: self._browse_file(k)).pack(side=tk.LEFT, padx=(7, 0))
                ttk.Button(row, text='Folder...', command=lambda k=key: self._browse_folder(k)).pack(side=tk.LEFT, padx=(5, 0))
            else:
                ttk.Button(row, text='Browse...', command=lambda k=key: self._browse_file(k)).pack(side=tk.LEFT, padx=(7, 0))
        if selected == 'pandemonium':
            self.ffmpeg_frame.pack(fill=tk.X, pady=(12, 0), after=self.inputs_frame)
        else:
            self.ffmpeg_frame.pack_forget()

    def _browse_file(self, key):
        filetypes = [('Game packages and archives', '*.n-gage *.ngage *.sis *.sisx *.ipa *.zip *.dz *.ngdat'), ('All files', '*.*')]
        chosen = filedialog.askopenfilename(parent=self, title='Choose original game file', filetypes=filetypes)
        if chosen:
            self.fields[key].set(chosen)

    def _browse_folder(self, key):
        chosen = filedialog.askdirectory(parent=self, title='Choose extracted game data directory')
        if chosen:
            self.fields[key].set(chosen)

    def _browse_output(self):
        chosen = filedialog.askdirectory(parent=self, title='Choose SD root or staging folder')
        if chosen:
            self.destination.set(chosen)

    def _browse_ffmpeg(self):
        chosen = filedialog.askopenfilename(parent=self, title='Choose ffmpeg.exe', filetypes=[('Executable', '*.exe'), ('All files', '*.*')])
        if chosen:
            self.ffmpeg.set(chosen)

    def _log(self, line):
        self.logs.configure(state='normal')
        self.logs.insert(tk.END, str(line) + '\n')
        self.logs.see(tk.END)
        self.logs.configure(state='disabled')

    def _start(self):
        if self.busy:
            return
        selected = self._game_id()
        sources = {key: val.get() for key, val in self.fields.items()}
        output = self.destination.get()
        ffmpeg_path = self.ffmpeg.get()
        if not output.strip():
            messagebox.showerror('Output folder required', 'Choose an SD card root or staging directory.', parent=self)
            return
        for key, label, _kind in GAMES[selected]['inputs']:
            if not sources[key].strip():
                messagebox.showerror('Game file required', f'Choose {label}.', parent=self)
                return
        self.busy = True
        self.selector.configure(state='disabled')
        self.start.configure(state='disabled')
        self.progress.start(12)
        self.status.set('Working...')
        self._log('─' * 42)
        worker = threading.Thread(target=self._worker, args=(selected, sources, output, ffmpeg_path), daemon=True)
        worker.start()

    def _worker(self, game, sources, output, ffmpeg_path):
        def log(message):
            self.events.put(('log', message))
        try:
            destination = prepare_game(game, sources, output, log=log, ffmpeg_override=ffmpeg_path)
            self.events.put(('done', str(destination)))
        except Exception as exc:
            self.events.put(('error', (str(exc), traceback.format_exc())))

    def _poll_events(self):
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == 'log':
                    self._log(payload)
                elif event == 'done':
                    self._set_ready('Complete')
                    self._log(f'Success. Game files are in: {payload}')
                    messagebox.showinfo('Preparation complete',
                        'The game-data folder is ready:\n\n' + payload +
                        '\n\nCopy it to your SD card. You must install the port .3dsx separately.', parent=self)
                elif event == 'error':
                    message, stack = payload
                    self._set_ready('Failed')
                    self._log('ERROR: ' + message)
                    self._log(stack)
                    messagebox.showerror('Preparation failed', message + '\n\nSee Activity for details.', parent=self)
        except queue.Empty:
            pass
        self.after(120, self._poll_events)

    def _set_ready(self, status):
        self.busy = False
        self.selector.configure(state='readonly')
        self.start.configure(state='normal')
        self.progress.stop()
        self.status.set(status)


if __name__ == '__main__':
    GameDataInstaller().mainloop()
