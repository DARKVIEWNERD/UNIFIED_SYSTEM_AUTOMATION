# helpers/console.py
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def prompt_input(prompt, default=None, allow_blank=False):
    while True:
        if default is not None:
            val = input(f"{prompt} [{default}]: ").strip()
            if val == "" and default is not None:
                return default
        else:
            val = input(f"{prompt}: ").strip()
        if val == "" and not allow_blank:
            print("  ⚠️  Input is required. Please try again.")
            continue
        return val

def progress_bar(current, total, width=28):
    if total <= 0:
        print("Progress: 0/0", end="\r")
        return
    ratio = min(max(current / total, 0.0), 1.0)
    filled = int(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    print(f"[{bar}] {current}/{total}", end="\r")

def iter_mhtml_files(dir_path):
    for name in os.listdir(dir_path):
        if name.lower().endswith((".mhtml", ".mht")):
            yield os.path.join(dir_path, name)

def effective_cap(max_rows_from_cfg):
    try:
        mr = int(max_rows_from_cfg) if max_rows_from_cfg is not None else 10
    except Exception:
        mr = 10
    mr = max(1, mr)
    return min(mr, 10)

def post_trim_rows(rows, cap):
    cleaned = [r for r in rows if any((r[i] if i < len(r) else "") for i in range(3))]
    if len(cleaned) > cap:
        cleaned = cleaned[:cap]
    return cleaned