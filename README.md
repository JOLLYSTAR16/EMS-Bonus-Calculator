# EMS Bonus Calculator

A no-login EMS bonus calculator for reading Discord duty-log screenshots, calculating lobby hours, adding manual bonuses, and generating a Discord-ready weekly report.

## Stack
- Frontend: React + Vite
- OCR: Tesseract.js (runs in the browser)
- Backend: FastAPI
- Storage: Browser localStorage (no account/login required)

## Run

### Backend
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
Open another terminal:
```bash
cd frontend
npm install
npm run dev
```

Then open the Vite URL, normally:
`http://localhost:5173`

The frontend expects the backend at `http://127.0.0.1:8000`.

## OCR
Upload Discord screenshots in the Upload Logs tab. Tesseract.js reads the screenshot in the browser. The parser looks for:
- `Name | ID`
- `On Duty PH1: 18:24`
- `Off Duty PH1: 19:04`
- `On Duty SH: 16:40`
- `Off Duty SH: 19:27`
- `On Duty PH2: 00:09`
- `Off Duty PH2: 01:16`

OCR is never assumed to be perfect. Every parsed entry is shown in a review table before it is added.

## Important
Lobby hourly rates and Day/Night/Late time windows are editable from Settings. The defaults are examples and should be changed to your EMS department's actual rules.
