# Web2Lean

A comprehensive platform for crawling mathematical Q&A websites and automatically formalizing problems into Lean 4.

## Features

- **Multi-Site Crawling**: Support for Math StackExchange, MathOverflow, AMM, and custom sites
- **LLM Preprocessing**: GLM-4V for image OCR, GLM-4 for content validation and correction
- **Lean Formalization**: Automatic conversion to Lean 4 using Kimina-Autoformalizer-7B
- **Lean Verification**: Verify Lean code against kimina-lean-server for correctness
- **Web Control Platform**: Full-featured Vue 3 frontend for monitoring and control
- **Scheduled Tasks**: APScheduler-based automation for crawling and processing

## Architecture

```
/datadisk/Web2Lean/
├── backend/          # Python backend (Flask + SQLAlchemy)
│   ├── api/         # REST API endpoints
│   ├── core/        # Crawler implementations
│   ├── database/    # Database models and management
│   ├── processing/  # LLM processing & Lean conversion
│   └── utils/       # Utilities (image handling, LLM clients)
├── frontend/         # Vue 3 frontend (Element Plus + ECharts)
├── data/            # SQLite databases & images
└── legacy/          # Original codebase (preserved)
```

## Quick Start

### 1. Install Dependencies

**Backend:**
```bash
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

### 2. Configure API Keys

Set the Zhipu API key:
```bash
export ZHIPU_API_KEY="your-api-key-here"
```

Or in the code, update the API key in `backend/config/settings.py`.

### 3. Start VLLM Server (for Lean conversion)

```bash
vllm serve /root/Kimina-Autoformalizer-7B --tensor-parallel-size 1 --port 8000 --host 0.0.0.0
```

Or use the built-in command:
```bash
python main.py --vllm-start
```

### 4. Start kimina-lean-server (for Lean verification)

The verification feature requires kimina-lean-server running:

```bash
# Default: http://127.0.0.1:9000
# Configure in backend/config/settings.py if different
```

### 5. Initialize Database

```bash
python main.py --init-db
```

### 6. Start the Backend API

```bash
python main.py
```

API will be available at `http://localhost:5000`

### 7. Start the Frontend

```bash
cd frontend
npm run dev
```

Frontend will be available at `http://localhost:3000`

## Usage

### Via Web Interface

1. Open `http://localhost:3000`
2. Navigate to **Crawlers** to start/stop site crawlers
3. Navigate to **Processing** to:
   - Trigger LLM preprocessing
   - Start Lean conversion
   - Verify converted Lean code
4. Navigate to **Database** to:
   - Browse and view processed content
   - View Lean code split into question (theorem declaration) and answer (complete theorem)
   - Check verification status
   - Clear data by stage (lean code, verification status, etc.)
5. Navigate to **Configuration** to manage sites, prompts, and scheduled tasks

### Via API

Example: Start a crawler
```bash
curl -X POST http://localhost:5000/api/crawlers/start \
  -H "Content-Type: application/json" \
  -d '{"site_name": "math_stackexchange", "mode": "incremental"}'
```

Example: Trigger Lean conversion
```bash
curl -X POST http://localhost:5000/api/processing/start-lean \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

Example: Verify all Lean-converted questions
```bash
curl -X POST http://localhost:5000/api/verification/verify-all \
  -H "Content-Type: application/json" \
  -d '{"limit": 100, "async": true}'
```

## Configuration

### Site Configuration

Edit `backend/config/sites.json` to configure crawl targets:
```json
{
  "sites": {
    "math_stackexchange": {
      "site_type": "math_se",
      "base_url": "https://math.stackexchange.com",
      "enabled": true,
      "pages_per_run": 10,
      "request_delay": 8.0
    }
  }
}
```

### LLM Prompts

Edit `backend/config/prompts.json` to customize LLM behavior:
- `image_ocr_decision`: Prompt for GLM-4V image analysis
- `content_correction`: Prompt for GLM-4 content validation
- `lean_conversion`: Prompt for Kimina-Autoformalizer-7B

## Processing Pipeline

1. **Raw Data**: Questions/answers crawled from web
2. **OCR (GLM-4V)**: Images analyzed, text extracted when possible
3. **Preprocessing (GLM-4)**: Content validated and corrected
4. **Deduplication** (interface only, not implemented)
5. **Lean Conversion**: Kimina-Autoformalizer-7B generates Lean 4 code
   - Question Lean Code: Theorem declaration
   - Answer Lean Code: Complete theorem with proof
6. **Lean Verification**: kimina-lean-server validates generated code

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/crawlers/start` | POST | Start a crawler |
| `/api/crawlers/stop/:site` | POST | Stop a crawler |
| `/api/crawlers/status` | GET | Get all crawler statuses |
| `/api/processing/start-lean` | POST | Start Lean conversion |
| `/api/processing/preprocess` | POST | Start LLM preprocessing |
| `/api/verification/verify/:id` | POST | Verify a single question's Lean code |
| `/api/verification/verify-all` | POST | Batch verify all Lean-converted questions |
| `/api/verification/status/:id` | GET | Get verification status for a question |
| `/api/database/questions` | GET | List/search questions |
| `/api/database/clear` | POST | Clear data by stage (lean/preprocess/verification) |
| `/api/statistics/overview` | GET | Get overall statistics |
| `/api/config/sites` | GET/POST | Manage site configurations |

## Development

### Testing Lean Conversion

Use the interactive test tool to test Lean conversion without going through the full pipeline:

```bash
python test_lean_converter.py
```

This allows you to:
- Test question conversion (theorem declaration only)
- Test answer conversion (complete theorem with proof)
- Quickly iterate on prompts and see results

### Adding a New Crawler

1. Create a new crawler class in `backend/core/` extending `BaseCrawler`
2. Implement abstract methods:
   - `fetch_questions_page(page)`
   - `parse_question(raw_data)`
   - `fetch_answers(question_id)`
3. Import and register in `backend/api/routes/crawlers.py`

### Modifying LLM Prompts

1. Edit prompts via Web UI at Configuration > Prompts
2. Or edit `backend/config/prompts.json` directly

## License

MIT License - See LICENSE file for details
