# Local demo environment

Runs the real API and Worker against a throw-away data directory filled with fake
accounts, and replaces NodeSeek / Telegram with canned responses so every button
works offline. **Never point it at real data**: both scripts refuse `/data` and
any directory that already holds a different instance.

```bash
cd backend
export NS_DATA_DIR=/tmp/ns-demo NS_ADMIN_PASSWORD=demo-only-password NS_WEB_DIR=../frontend/dist
python -m dev.seed_demo                       # fill the demo data
uvicorn nsapp.api.app:app --port 8090         # API (+ built frontend)
python -m dev.demo_worker                     # Worker with fake NodeSeek/Telegram
cd ../frontend && npm run dev                 # UI with hot reload on :5173
```
