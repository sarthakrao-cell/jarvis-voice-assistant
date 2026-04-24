"""
JARVIS-style Voice Assistant for PC
Requirements: pip install speechrecognition pyttsx3 pyaudio anthropic psutil pyautogui pillow requests
Optional: pip install pyperclip playsound
"""

import speech_recognition as sr
import pyttsx3
import anthropic
import subprocess
import os
import sys
import json
import time
import threading
import webbrowser
import platform
import psutil
import pyautogui
import datetime
import shutil
import glob
import re
from pathlib import Path


# ─── CONFIG ───────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = "YOUR_ANTHROPIC_API_KEY_HERE"   # ← paste your key here
WAKE_WORD = "jarvis"                                  # change to whatever you like
VOICE_RATE = 165                                      # speech speed (words/min)
VOICE_VOLUME = 1.0                                    # 0.0 – 1.0
CONVERSATION_HISTORY = []                             # multi-turn memory
MAX_HISTORY = 20                                      # keep last N turns
SYSTEM_PROMPT = """You are JARVIS, an intelligent voice assistant running on the user's PC.
You have access to the user's computer through Python tools. 
Keep responses concise and conversational (1–3 sentences max unless detail is needed).
When you perform an action, confirm it briefly. Never say "As an AI..." or add disclaimers."""


# ─── SPEECH ENGINE ────────────────────────────────────────────────────────────
engine = pyttsx3.init()
engine.setProperty("rate", VOICE_RATE)
engine.setProperty("volume", VOICE_VOLUME)

# Try to pick a natural-sounding voice
voices = engine.getProperty("voices")
for v in voices:
    if "zira" in v.name.lower() or "david" in v.name.lower() or "daniel" in v.name.lower():
        engine.setProperty("voice", v.id)
        break


def speak(text: str):
    """Convert text to speech."""
    print(f"\n[JARVIS] {text}")
    engine.say(text)
    engine.runAndWait()


# ─── MICROPHONE / LISTENING ───────────────────────────────────────────────────
recognizer = sr.Recognizer()
recognizer.pause_threshold = 1.0
recognizer.energy_threshold = 300


def listen(timeout: int = 8, phrase_limit: int = 15) -> str | None:
    """Listen for a voice command and return transcribed text."""
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        print("\n[Listening...]", flush=True)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            text = recognizer.recognize_google(audio).lower().strip()
            print(f"[You] {text}")
            return text
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            print(f"[Speech API error] {e}")
            return None


# ─── PC TOOLS ─────────────────────────────────────────────────────────────────

def open_application(app_name: str) -> str:
    system = platform.system()
    app_name_lower = app_name.lower()
    app_map = {
        "notepad":   {"Windows": "notepad.exe",     "Darwin": "TextEdit", "Linux": "gedit"},
        "calculator":{"Windows": "calc.exe",        "Darwin": "Calculator","Linux": "gnome-calculator"},
        "chrome":    {"Windows": "chrome",          "Darwin": "Google Chrome","Linux": "google-chrome"},
        "firefox":   {"Windows": "firefox",         "Darwin": "Firefox",  "Linux": "firefox"},
        "explorer":  {"Windows": "explorer.exe",    "Darwin": "Finder",   "Linux": "nautilus"},
        "terminal":  {"Windows": "cmd.exe",         "Darwin": "Terminal", "Linux": "gnome-terminal"},
        "settings":  {"Windows": "ms-settings:",    "Darwin": "System Preferences","Linux": "gnome-control-center"},
        "spotify":   {"Windows": "spotify",         "Darwin": "Spotify",  "Linux": "spotify"},
        "vscode":    {"Windows": "code",            "Darwin": "Visual Studio Code","Linux": "code"},
        "word":      {"Windows": "winword",         "Darwin": "Microsoft Word","Linux": "libreoffice --writer"},
        "excel":     {"Windows": "excel",           "Darwin": "Microsoft Excel","Linux": "libreoffice --calc"},
    }
    for key, paths in app_map.items():
        if key in app_name_lower:
            cmd = paths.get(system, app_name)
            try:
                if system == "Windows":
                    os.startfile(cmd) if not cmd.startswith("ms-") else subprocess.Popen(f"start {cmd}", shell=True)
                elif system == "Darwin":
                    subprocess.Popen(["open", "-a", cmd])
                else:
                    subprocess.Popen([cmd.split()[0]] + cmd.split()[1:])
                return f"Opened {app_name}."
            except Exception as e:
                return f"Could not open {app_name}: {e}"
    try:
        if system == "Windows":
            subprocess.Popen(app_name, shell=True)
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
        else:
            subprocess.Popen([app_name])
        return f"Attempted to open {app_name}."
    except Exception as e:
        return f"Failed: {e}"


def search_web(query: str) -> str:
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"Opened browser and searched for: {query}"


def get_system_info() -> str:
    cpu   = psutil.cpu_percent(interval=1)
    ram   = psutil.virtual_memory()
    disk  = psutil.disk_usage("/")
    boot  = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot
    return (
        f"CPU: {cpu}%  |  "
        f"RAM: {ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB ({ram.percent}%)  |  "
        f"Disk: {disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB ({disk.percent}%)  |  "
        f"Uptime: {str(uptime).split('.')[0]}"
    )


def get_running_processes(top: int = 10) -> str:
    procs = [(p.info["pid"], p.info["name"], p.info["cpu_percent"])
             for p in psutil.process_iter(["pid", "name", "cpu_percent"])
             if p.info["cpu_percent"] is not None]
    procs.sort(key=lambda x: x[2], reverse=True)
    lines = [f"PID {pid}: {name} ({cpu}%)" for pid, name, cpu in procs[:top]]
    return "\n".join(lines)


def kill_process(name_or_pid: str) -> str:
    try:
        pid = int(name_or_pid)
        p = psutil.Process(pid)
        p.terminate()
        return f"Terminated process PID {pid}."
    except ValueError:
        killed = []
        for p in psutil.process_iter(["name", "pid"]):
            if name_or_pid.lower() in p.info["name"].lower():
                p.terminate()
                killed.append(str(p.info["pid"]))
        return f"Terminated: {', '.join(killed)}" if killed else f"No process found matching '{name_or_pid}'."


def create_file(path: str, content: str = "") -> str:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(content, encoding="utf-8")
        return f"Created file: {path}"
    except Exception as e:
        return f"Error: {e}"


def read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")[:2000]
    except Exception as e:
        return f"Error reading file: {e}"


def list_directory(path: str = ".") -> str:
    try:
        items = os.listdir(path)
        dirs  = [d for d in items if os.path.isdir(os.path.join(path, d))]
        files = [f for f in items if os.path.isfile(os.path.join(path, f))]
        return f"Folders: {', '.join(dirs[:15])}\nFiles: {', '.join(files[:20])}"
    except Exception as e:
        return f"Error: {e}"


def run_shell_command(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        out = result.stdout.strip()[:1000] or result.stderr.strip()[:500]
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error: {e}"


def take_screenshot(filename: str = None) -> str:
    if not filename:
        filename = f"screenshot_{int(time.time())}.png"
    try:
        img = pyautogui.screenshot()
        img.save(filename)
        return f"Screenshot saved as {filename}"
    except Exception as e:
        return f"Error: {e}"


def type_text(text: str) -> str:
    time.sleep(0.5)
    pyautogui.write(text, interval=0.03)
    return f"Typed: {text}"


def press_keys(*keys) -> str:
    pyautogui.hotkey(*keys)
    return f"Pressed: {'+'.join(keys)}"


def get_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError:
        return "pyperclip not installed."


def set_clipboard(text: str) -> str:
    try:
        import pyperclip
        pyperclip.copy(text)
        return "Copied to clipboard."
    except ImportError:
        return "pyperclip not installed."


def get_datetime() -> str:
    now = datetime.datetime.now()
    return now.strftime("It's %A, %B %d %Y, %I:%M %p")


def set_volume(level: int) -> str:
    """Set system volume 0–100 (Windows/Linux)."""
    system = platform.system()
    try:
        if system == "Windows":
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            scalar = max(0.0, min(1.0, level / 100.0))
            volume.SetMasterVolumeLevelScalar(scalar, None)
            return f"Volume set to {level}%."
        elif system == "Darwin":
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"])
            return f"Volume set to {level}%."
        else:
            subprocess.run(["amixer", "-q", "sset", "Master", f"{level}%"])
            return f"Volume set to {level}%."
    except Exception as e:
        return f"Could not set volume: {e}"


def find_files(pattern: str, search_dir: str = str(Path.home())) -> str:
    matches = glob.glob(os.path.join(search_dir, "**", pattern), recursive=True)
    return "\n".join(matches[:15]) if matches else f"No files found matching '{pattern}'."


# ─── TOOL REGISTRY ────────────────────────────────────────────────────────────
TOOLS = [
    {"name": "open_application",   "description": "Open a program or application on the PC.", "input_schema": {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]}},
    {"name": "search_web",         "description": "Open the browser and perform a Google search.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "get_system_info",    "description": "Get CPU, RAM, disk usage and uptime.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_running_processes","description":"List top CPU-consuming processes.", "input_schema": {"type": "object", "properties": {"top": {"type": "integer"}}}},
    {"name": "kill_process",       "description": "Kill a process by name or PID.", "input_schema": {"type": "object", "properties": {"name_or_pid": {"type": "string"}}, "required": ["name_or_pid"]}},
    {"name": "create_file",        "description": "Create a file with optional content.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path"]}},
    {"name": "read_file",          "description": "Read contents of a file.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "list_directory",     "description": "List files and folders in a directory.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "run_shell_command",  "description": "Execute a shell/terminal command.", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}},
    {"name": "take_screenshot",    "description": "Take a screenshot and save it.", "input_schema": {"type": "object", "properties": {"filename": {"type": "string"}}}},
    {"name": "type_text",          "description": "Type text at the current cursor position.", "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "press_keys",         "description": "Press keyboard shortcut (e.g. ctrl+c).", "input_schema": {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}}}, "required": ["keys"]}},
    {"name": "get_clipboard",      "description": "Get current clipboard content.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "set_clipboard",      "description": "Copy text to clipboard.", "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "get_datetime",       "description": "Get current date and time.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "set_volume",         "description": "Set system volume (0-100).", "input_schema": {"type": "object", "properties": {"level": {"type": "integer"}}, "required": ["level"]}},
    {"name": "find_files",         "description": "Search for files matching a pattern.", "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "search_dir": {"type": "string"}}, "required": ["pattern"]}},
]

TOOL_FUNCTIONS = {
    "open_application":    lambda i: open_application(i["app_name"]),
    "search_web":          lambda i: search_web(i["query"]),
    "get_system_info":     lambda i: get_system_info(),
    "get_running_processes":lambda i: get_running_processes(i.get("top", 10)),
    "kill_process":        lambda i: kill_process(i["name_or_pid"]),
    "create_file":         lambda i: create_file(i["path"], i.get("content", "")),
    "read_file":           lambda i: read_file(i["path"]),
    "list_directory":      lambda i: list_directory(i.get("path", ".")),
    "run_shell_command":   lambda i: run_shell_command(i["cmd"]),
    "take_screenshot":     lambda i: take_screenshot(i.get("filename")),
    "type_text":           lambda i: type_text(i["text"]),
    "press_keys":          lambda i: press_keys(*i["keys"]),
    "get_clipboard":       lambda i: get_clipboard(),
    "set_clipboard":       lambda i: set_clipboard(i["text"]),
    "get_datetime":        lambda i: get_datetime(),
    "set_volume":          lambda i: set_volume(i["level"]),
    "find_files":          lambda i: find_files(i["pattern"], i.get("search_dir", str(Path.home()))),
}


# ─── CLAUDE BRAIN ─────────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def ask_claude(user_input: str) -> str:
    global CONVERSATION_HISTORY

    CONVERSATION_HISTORY.append({"role": "user", "content": user_input})
    if len(CONVERSATION_HISTORY) > MAX_HISTORY:
        CONVERSATION_HISTORY = CONVERSATION_HISTORY[-MAX_HISTORY:]

    messages = list(CONVERSATION_HISTORY)

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Collect tool calls and text
        tool_calls = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tc in tool_calls:
                func = TOOL_FUNCTIONS.get(tc.name)
                result = func(tc.input) if func else f"Unknown tool: {tc.name}"
                print(f"  [Tool] {tc.name}({tc.input}) → {result[:120]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": str(result),
                })
            messages.append({"role": "user", "content": tool_results})
        else:
            final_text = " ".join(b.text for b in text_blocks).strip()
            CONVERSATION_HISTORY.append({"role": "assistant", "content": final_text})
            return final_text


# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

def run():
    speak(f"JARVIS online. Say '{WAKE_WORD}' to activate.")
    print(f"\n{'='*50}")
    print(f"  JARVIS Voice Assistant  |  Wake word: '{WAKE_WORD}'")
    print(f"  Say 'exit jarvis' or 'goodbye jarvis' to quit.")
    print(f"{'='*50}\n")

    while True:
        # Wait for wake word
        phrase = listen(timeout=None, phrase_limit=6)
        if not phrase:
            continue
        if WAKE_WORD not in phrase:
            continue

        speak("Yes?")

        # Now listen for the actual command
        command = listen(timeout=8, phrase_limit=20)
        if not command:
            speak("I didn't catch that.")
            continue

        if any(w in command for w in ["exit", "goodbye", "shut down", "quit"]):
            speak("Goodbye. Shutting down.")
            sys.exit(0)

        # Send to Claude
        try:
            reply = ask_claude(command)
            speak(reply)
        except Exception as e:
            print(f"[Error] {e}")
            speak("Sorry, something went wrong. Please try again.")


if __name__ == "__main__":
    run()
