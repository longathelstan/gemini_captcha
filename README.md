
# 📄 HaTinh Exam Results Scraper (CAPTCHA Solver with Gemini)

This Python script automates the extraction of 10th-grade entrance exam results from the official Hà Tĩnh education department website: [https://hatinh.edu.vn](https://hatinh.edu.vn).

It bypasses CAPTCHA protection by using Google's **Gemini API** to recognize CAPTCHA images using image-to-text AI models (`gemini-1.5-flash`, `gemini-2.0-flash`).

---

## 🚀 Features

- 🔐 **CAPTCHA Bypass**: Uses Google Gemini AI to solve CAPTCHA
- 📄 **Scrapes Exam Scores** by student ID (SBD)
- 🧠 **Auto Rate Limit Handling**: rotates through multiple Gemini API keys
- 💾 **CSV Export**: Saves clean result data to `exam_scores_hatinh.csv`
- 🧠 **Resume Progress**: Supports resuming if interrupted
- 💡 **BeautifulSoup Parsing**: Parses score tables from HTML
- 📁 Saves all solved CAPTCHAs for debugging and verification

---

## 🛠 Requirements

Install dependencies:

```bash
pip install -r requirements.txt
````

> Or manually:

```bash
pip install requests beautifulsoup4 pandas python-dotenv google-generativeai
```

---

## 🔐 Environment Setup

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY_1=your_first_key
GOOGLE_API_KEY_2=your_second_key
GOOGLE_API_KEY_3=your_third_key
...
```

You can generate Gemini API keys at: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

> Add as many keys as needed to avoid rate limiting.

---

## 🧠 How It Works

1. Sends request to get CAPTCHA image from Hà Tĩnh's website.
2. Sends the image to Gemini model (Google Generative AI) to solve.
3. Submits the student ID (SBD) + solved CAPTCHA.
4. Parses and stores the score table if found.
5. Repeats the process for the next ID.

---

## 📦 Configuration

You can adjust these in the script:

```python
STUDENT_ID_START = 260001
STUDENT_ID_END = 260420
QUERY_BATCH_SIZE = 10
GEMINI_COOLDOWN_S = 90
OUTPUT_CSV_FILE = "exam_scores_hatinh.csv"
```

---

## ▶️ Running the Script

```bash
python main.py
```

The script will:

* Start from `STUDENT_ID_START`
* Fetch score (if exists) for each ID
* Save results to CSV
* Save CAPTCHA images to `/solved_captchas/`

---

## 🧪 Quick Test

To run on a small ID range (e.g. 5 IDs):

```python
STUDENT_ID_START = 260100
STUDENT_ID_END = 260104
```

---

## 🧠 Example Output

CSV file will look like:

| Số báo danh | Họ tên       | Ngày sinh  | Toán | Văn | Tiếng Anh | Tổng điểm |
| ----------- | ------------ | ---------- | ---- | --- | --------- | --------- |
| 260123      | Nguyễn Văn A | 01/01/2010 | 8.25 | 7.5 | 9.0       | 24.75     |

---

## 📁 Project Structure

```
📂 your-project/
├── main.py
├── .env
├── exam_scores_hatinh.csv
├── solved_captchas/
└── requirements.txt
```

---

## 📌 Notes

* Make sure your API keys are valid and have quota.
* CAPTCHA may be hard to read sometimes → model might fail.
* If all keys are rate-limited, script waits and resumes.

---

## ❤️ Credits

* Website: [hatinh.edu.vn](https://hatinh.edu.vn)
* CAPTCHA solving: [Google Generative AI (Gemini)](https://ai.google.dev/)
* Made with ❤️ by [lowng](https://github.com/longathelstan)

---

## 📄 License

MIT License

```
