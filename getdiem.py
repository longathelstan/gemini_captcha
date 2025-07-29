import requests
from io import BytesIO
import time
import random
from bs4 import BeautifulSoup
import os
import re
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv

# --- Environment Setup ---
load_dotenv()

# ================== CONFIGURATION ==================
# --- URLs and Headers ---
CAPTCHA_URL = "https://hatinh.edu.vn/api/Common/Captcha/getCaptcha"
FETCH_URL = "https://hatinh.edu.vn/?module=Content.Listing&moduleId=1017&cmd=redraw&site=32982&url_mode=rewrite"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://hatinh.edu.vn/tracuudiemthi_ts10",
    "Origin": "https://hatinh.edu.vn",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

# --- Scraping Parameters ---
STUDENT_ID_START = 260001
STUDENT_ID_END = 260420
OUTPUT_CSV_FILE = "exam_scores_hatinh.csv"
CAPTCHA_SAVE_FOLDER = "solved_captchas"
MAX_FETCH_RETRIES = 5  # Retries per student ID

# --- Anti-Detection and Rate Limiting ---
QUERY_BATCH_SIZE = 10       # Number of students to fetch before a long delay
MIN_DELAY_S = 3             # Minimum delay in seconds for the long delay
MAX_DELAY_S = 7             # Maximum delay
GEMINI_COOLDOWN_S = 90      # Cooldown time in seconds when rate limited
GEMINI_RATE_LIMIT_FLAG = "RATE_LIMITED" # Internal flag for rate limit events

# ================== GEMINI MULTI-KEY SETUP ==================
API_KEYS = [key for i in range(1, 100) if (key := os.getenv(f'GOOGLE_API_KEY_{i}'))]

if not API_KEYS:
    raise ValueError("No GOOGLE_API_KEY_n found in .env file. Please set them as GOOGLE_API_KEY_1, GOOGLE_API_KEY_2, etc.")

print(f" [INFO] Found and loaded {len(API_KEYS)} API key(s).")
current_key_index = 0

# ================== SCRIPT LOGIC ==================
if not os.path.exists(CAPTCHA_SAVE_FOLDER):
    os.makedirs(CAPTCHA_SAVE_FOLDER)

session = requests.Session()
session.get("https://hatinh.edu.vn/tracuudiemthi_ts10", headers=HEADERS) 

def load_existing_data(filepath):
    """Loads previously scraped data from the output CSV file if it exists."""
    if not os.path.exists(filepath):
        print(f" [INFO] Output file '{filepath}' not found. Starting a new scrape.")
        return [], set()
    try:
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        processed_ids = set(df['Số báo danh'].astype(int).tolist()) if 'Số báo danh' in df.columns else set()
        print(f"  [INFO] Resuming scrape. Loaded {len(df)} records and {len(processed_ids)} processed student IDs.")
        return df.to_dict('records'), processed_ids
    except Exception as e:
        print(f"  [WARNING] Could not load existing CSV file. Starting fresh. Error: {e}")
        return [], set()

def save_data_to_csv(all_records, filepath):
    """Saves the collected data to a CSV file, removing duplicates."""
    if not all_records:
        return
    
    df = pd.DataFrame(all_records)
    if "Số báo danh" in df.columns:
        df['Số báo danh'] = pd.to_numeric(df['Số báo danh'], errors='coerce')
        df.dropna(subset=['Số báo danh'], inplace=True)
        df['Số báo danh'] = df['Số báo danh'].astype(int)
        df.sort_values(by="Số báo danh", inplace=True)
        df.drop_duplicates(subset=['Số báo danh'], keep='last', inplace=True)
    
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"\n [SAVE] Saved {len(df)} unique records to '{filepath}'.")

def solve_captcha_with_gemini():
    """Fetches a CAPTCHA and uses a rotating Gemini API key and model to solve it."""
    global current_key_index

    models_to_try = ['gemini-1.5-flash-latest', 'gemini-2.0-flash']
    timestamp = int(time.time() * 1000)
    url = f"{CAPTCHA_URL}?returnType=image&site=32982&width=150&height=50&t={timestamp}"

    try:
        response = session.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        image_bytes = response.content
        image_part = {"mime_type": "image/png", "data": image_bytes}
        prompt = "This is a CAPTCHA image. Read the characters in it. Return only the character string, with no explanations or formatting."

        for model_name in models_to_try:
            try:
                selected_key = API_KEYS[current_key_index]
                genai.configure(api_key=selected_key)
                model = genai.GenerativeModel(model_name)
                print(f"    (Using API Key #{current_key_index + 1}, Model: {model_name})")

                gemini_response = model.generate_content([prompt, image_part])
                solved_text = gemini_response.text.strip()
                final_text = (match.group(0) if (match := re.search(r'[a-zA-Z0-9]+', solved_text)) else solved_text)

                if final_text:
                    safe_filename = re.sub(r'[^\w\-_\.]', '_', final_text)[:50]
                    save_path = os.path.join(CAPTCHA_SAVE_FOLDER, f"{safe_filename}_{timestamp}.png")
                    try:
                        with open(save_path, "wb") as f: f.write(image_bytes)
                    except OSError as e:
                        print(f"    [!] Could not save CAPTCHA image: {e}")

                    current_key_index = (current_key_index + 1) % len(API_KEYS)
                    return final_text

            except Exception as model_error:
                error_msg = str(model_error).lower()
                if any(keyword in error_msg for keyword in ['rate', 'quota', 'limit', 'exceeded', '429']):
                    print(f"      [RATE LIMIT] {model_name} rate limit hit. Trying next model or rotating key.")
                    continue
                else:
                    print(f"    [ERROR] {model_name} failed unexpectedly: {model_error}")
                    break

        current_key_index = (current_key_index + 1) % len(API_KEYS)
        return GEMINI_RATE_LIMIT_FLAG

    except Exception as e:
        print(f"    [ERROR] Could not fetch CAPTCHA image: {e}")
        return ""

def fetch_exam_scores(student_id, captcha):
    """Submits the student ID and solved CAPTCHA to fetch the score data."""
    payload = {
        'layout': 'Decl.DataSet.Detail.default', 'itemsPerPage': '1000', 'pageNo': '1',
        'service': 'Content.Decl.DataSet.Grouping.select', 'itemId': '6844479ae672fba4ce0b1dc5',
        'gridModuleParentId': '17', 'type': 'Decl.DataSet', 'modulePosition': '0', 'moduleParentId': '-1',
        'orderBy': '', 'unRegex': '', 'keyword': str(student_id), 'BDC_UserSpecifiedCaptchaId': captcha,
        'captcha_check': captcha, 'captcha_code': captcha, '_t': int(time.time() * 1000)
    }
    try:
        response = session.post(FETCH_URL, headers=HEADERS, data=payload, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"     [ERROR] Network error while fetching scores: {e}")
        return ""

def parse_score_data(html_text):
    """Parses the HTML response to extract score data into a dictionary."""
    if not html_text or "không tìm thấy" in html_text.lower(): return None
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table")
    if not table: return None
    
    headers = [th.get_text(strip=True) for th in table.select("thead th")]
    values = [td.get_text(strip=True) for td in table.select("tbody tr td")]

    if len(headers) == len(values):
        return dict(zip(headers, values))
    return None

def main():
    """Main function to orchestrate the scraping process."""
    print(f" [START] Begin scraping from student ID {STUDENT_ID_START} to {STUDENT_ID_END}")
    
    all_records, processed_ids = load_existing_data(OUTPUT_CSV_FILE)
    query_count = 0

    for student_id in range(STUDENT_ID_START, STUDENT_ID_END + 1):
        if student_id in processed_ids:
            print(f" [SKIP] Student ID {student_id} has already been processed.")
            continue
            
        print(f"\n [FETCHING] Student ID: {student_id}")
        
        success = False
        for attempt in range(1, MAX_FETCH_RETRIES + 1):
            captcha = solve_captcha_with_gemini()
            
            if captcha == GEMINI_RATE_LIMIT_FLAG:
                print(f" [COOLDOWN] All Gemini API keys are rate-limited. Pausing for {GEMINI_COOLDOWN_S} seconds...")
                save_data_to_csv(all_records, OUTPUT_CSV_FILE)
                time.sleep(GEMINI_COOLDOWN_S)
                print(" [RESUME] Resuming scrape...")
                continue 
                
            print(f"    (Attempt {attempt}/{MAX_FETCH_RETRIES}) Solved CAPTCHA: '{captcha}'")
            
            if captcha and captcha.isalnum() and len(captcha) >= 4:
                html_response = fetch_exam_scores(student_id, captcha)
                if not html_response:
                    print("    [!] Server did not return a valid response. Retrying...")
                    time.sleep(1); continue
                
                if "không tìm thấy" in html_response.lower():
                    print(f"     [SUCCESS] CAPTCHA was correct, but no data exists for student ID {student_id}.")
                    success = True; break
                    
                record = parse_score_data(html_response)
                if record:
                    all_records.append(record)
                    processed_ids.add(student_id)
                    print(f"     [SUCCESS] Found and stored scores for student ID {student_id}.")
                    success = True; break
            else:
                print("    [!] Invalid CAPTCHA solved. Retrying...")
            
            time.sleep(1)
        
        if not success:
            print(f"     [FAILURE] Failed to fetch data for student ID {student_id} after {MAX_FETCH_RETRIES} attempts.")
        
        query_count += 1
        
        if query_count % QUERY_BATCH_SIZE == 0:
            save_data_to_csv(all_records, OUTPUT_CSV_FILE)
            delay = random.uniform(MIN_DELAY_S, MAX_DELAY_S)
            print(f"💤 [DELAY] Batch of {QUERY_BATCH_SIZE} processed. Pausing for {delay:.1f} seconds...")
            time.sleep(delay)
        else:
            time.sleep(random.uniform(1, 2.5)) 

    print("\n [COMPLETE] Scraping process finished.")
    save_data_to_csv(all_records, OUTPUT_CSV_FILE)

if __name__ == "__main__":
    main()