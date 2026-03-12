# file_handlers.py - File saving and handling
import time
from datetime import datetime
from pathlib import Path

def get_timestamped_folder(base_dir: Path) -> Path:
    """
    Create a timestamped folder for this execution
    Format: YYYY-MM-DD_HH-MM-SS
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    timestamped_dir = base_dir / timestamp
    timestamped_dir.mkdir(parents=True, exist_ok=True)
    return timestamped_dir

def initialize_counters_from_files(folder: Path, countries: list) -> dict:
    """
    Scan existing files and find the HIGHEST sequence number for each country.
    Returns dict with last used sequence: {country_number: last_sequence}
    """
    counters = {}
    
    for file in folder.glob("*.mhtml"):
        filename = file.stem
     #   print(f"  File: {filename}")
        
        try:
            # Extract first 4 digits: country_number(2) + sequence(2)
            if len(filename) >= 4 and filename[:4].isdigit():
                country_num = filename[:2]  # "01"
                seq_num = int(filename[2:4])  # "01" -> 1
                
               # print(f"    Country: {country_num}, Sequence: {seq_num}")
                
                # Update if this sequence is higher than what we have
                if country_num in counters:
                    if seq_num > counters[country_num]:
                        counters[country_num] = seq_num
                      
                else:
                    counters[country_num] = seq_num
                 #   print(f"    ✅ New country, sequence = {seq_num}")
        except Exception as e:
            print(f"    ❌ Error parsing: {e}")
            continue
    
    # Initialize missing countries to 0
    for country in countries:
        country_num = country['number']
        if country_num not in counters:
            counters[country_num] = 0
            print(f"  Country {country_num}: No files yet, starting at 0")
       
    
    return counters

def save_mhtml_snapshot(driver, base_filename: str, folder_path: Path):
    """
    Save webpage as MHTML safely with temp file + validation to avoid corrupt / duplicate saves
    """
    """
    Save webpage as MHTML using driver.execute_cdp_cmd('Page.captureSnapshot', {})
    EXACTLY like your original code
    """
    try:
        snapshot_data = driver.execute_cdp_cmd('Page.captureSnapshot', {})
        
        if 'data' in snapshot_data:
            temp_path = folder_path / f"{base_filename}.tmp"
            final_path = folder_path / f"{base_filename}.mhtml"

            # Write temp file first
            with open(temp_path, 'w', encoding='utf-8', newline='') as f:
                f.write(snapshot_data['data'])

            # Validate size (avoid corrupted files)
            if temp_path.stat().st_size < 5_000:
                temp_path.unlink(missing_ok=True)
                return False, "Snapshot too small or corrupted"

            # Prevent overwrite
            counter = 1
            while final_path.exists():
                final_path = folder_path / f"{base_filename}_{counter}.mhtml"
                counter += 1

            # Atomic rename
            temp_path.rename(final_path)
            return True, final_path.name
        else:
            return False, "Could not capture web snapshot"
            
    except Exception as e:
        return False, f"Web snapshot failed: {str(e)[:80]}"

def load_existing_snapshots(folder: Path) -> set:
    """
    Scan existing MHTML files so execution can resume instead of duplicating files.
    Returns a set of:
    (country_code, web_platform, app_platform, category)
    """
    existing = set()

    for file in folder.glob("*.mhtml"):
        name = file.stem  # e.g., "0101_US_AppFollow_android_music_and_audio_20260128"
        
        try:
            # Handle the merged country_number + sequence format
            # First 4 digits = country_number(2) + sequence(2)
            first_part = name[:4]  # "0101"
            country_number = first_part[:2]  # "01"
            sequence_number = first_part[2:]  # "01"
            
            # Extract the rest of the filename after the first part
            rest = name[4:]  # "_US_AppFollow_android_music_and_audio_20260128"
            
            # Split by underscore
            parts = rest.split("_")
            
            # Remove empty strings from split
            parts = [p for p in parts if p]
            
            # Parse components (adjust indices based on your actual naming)
            # Format: _US_AppFollow_android_music_and_audio_20260128
            # parts[0] = "US" (country_code)
            # parts[1] = "AppFollow" (web_platform)
            # parts[2] = "android" (app_platform)
            # parts[3:-1] = category parts ("music", "and", "audio")
            # parts[-1] = date
            
            if len(parts) >= 4:
                country_code = parts[0]
                web_platform = parts[1].lower()
                app_platform = parts[2].lower()
                
                # Join category parts (everything between app_platform and date)
                category_parts = parts[3:-1]  # Skip the date
                category = "_".join(category_parts).lower()
                
                key = (country_code, web_platform, app_platform, category)
                existing.add(key)
                
        except Exception as e:
            print(f"Warning: Could not parse filename '{name}': {e}")
            continue

    print(f"📂 Resume mode: detected {len(existing)} existing snapshots")
    return existing


def create_base_filename(country: dict, sequence: int, web_platform: dict, 
                         app_platform: str, category: str, date_stamp: str) -> str:
    """
    Create the exact same filename format as your original code
    {country_number}{sequence}_{Country}_{Webplatform}_{Platform}_{Category}_{Date}
    """
    # Get components
    country_number = country['number']
    sequence_str = str(sequence).zfill(2)
    country_name_clean = country['code'].replace(' ', '')
    webplatform_clean = web_platform['name'].replace(' ', '')
    safe_category = category.replace(' ', '_').replace('&', 'and')
    
    # Construct filename
    filename = f"{country_number}{sequence_str}_{country_name_clean}_{webplatform_clean}_{app_platform}_{safe_category}_{date_stamp}"
    
    return filename

def ensure_directory_exists(directory: Path):
    """Ensure directory exists"""
    directory.mkdir(parents=True, exist_ok=True)