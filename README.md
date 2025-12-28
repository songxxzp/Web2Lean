# Web2Lean

A comprehensive platform for crawling mathematical Q&A websites and automatically formalizing problems into Lean 4.

## Features

- **Multi-Site Crawling**: Support for Math StackExchange, MathOverflow, AMM, and custom sites
- **LLM Preprocessing**: GLM-4V for image OCR, GLM-4 for content validation and correction
- **Dual Lean Converter System**: Two independent Lean converters with different strengths
  - **Kimina Legacy**: Fast local conversion using Kimina-Autoformalizer-7B via VLLM
  - **GLM LLM Agent**: High-quality conversion using GLM-4.7 with iterative correction
- **Lean Verification**: Verify Lean code against kimina-lean-server for correctness
- **Independent Converter Tracking**: Each converter maintains its own conversion results
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

Configure GLM models (optional, defaults provided):
```bash
# For LLM-based Lean converter
export GLM_LEAN_MODEL="glm-4.7"  # or "glm-4" for faster conversion
export LEAN_MAX_ITERATIONS=1     # Max correction iterations (default: 1)
```

Or configure in the Web UI at **Configuration > Models**.

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
   - Trigger LLM preprocessing (GLM-4V + GLM-4)
   - Start Lean conversion with selected converter:
     - **Kimina (Legacy)**: Fast conversion using local model
     - **GLM LLM Agent**: High-quality conversion with iterative correction
   - Verify converted Lean code
4. Navigate to **Database** to:
   - Browse and view processed content
   - View Lean code split by converter (Question/Answer Lean code)
   - Compare results from different converters
   - Check verification status for each converter
   - Clear data by converter or stage
5. Navigate to **Configuration** to:
   - Manage sites, prompts, and scheduled tasks
   - Configure GLM models and Lean conversion settings

### Via API

Example: Start a crawler
```bash
curl -X POST http://localhost:5000/api/crawlers/start \
  -H "Content-Type: application/json" \
  -d '{"site_name": "math_stackexchange", "mode": "incremental"}'
```

Example: Trigger Lean conversion with specific converter
```bash
# Using Kimina Legacy converter
curl -X POST http://localhost:5000/api/processing/start-lean \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "converter": "kimina"}'

# Using GLM LLM Agent converter
curl -X POST http://localhost:5000/api/processing/start-lean \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "converter": "llm"}'
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
5. **Lean Conversion**: Two independent converter options
   - **Kimina Legacy Converter**:
     - Uses local Kimina-Autoformalizer-7B via VLLM
     - Fast conversion speed
     - Requires VLLM server running
   - **GLM LLM Agent Converter**:
     - Uses GLM-4.7 API for high-quality conversion
     - Generates Question Lean Code (theorem declaration with `:= by sorry`)
     - Generates Answer Lean Code (complete theorem with rigorous proof)
     - Iterative correction with Lean verifier feedback (configurable iterations)
     - Automatically fixes errors based on verifier output
   - **Independent Operation**: Each converter processes only questions it hasn't converted
   - **Comparison**: View results from both converters side-by-side
6. **Lean Verification**: kimina-lean-server validates generated code
   - Independent verification status per converter
   - Track verification history (passed/warning/failed)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/crawlers/start` | POST | Start a crawler |
| `/api/crawlers/stop/:site` | POST | Stop a crawler |
| `/api/crawlers/status` | GET | Get all crawler statuses |
| `/api/processing/start-lean` | POST | Start Lean conversion (supports `converter` param: `kimina` or `llm`) |
| `/api/processing/preprocess` | POST | Start LLM preprocessing |
| `/api/processing/task/:type/progress` | GET | Get progress for a task type |
| `/api/verification/verify/:id` | POST | Verify a single question's Lean code |
| `/api/verification/verify-all` | POST | Batch verify all Lean-converted questions |
| `/api/verification/status/:id` | GET | Get verification status for a question |
| `/api/database/questions` | GET | List/search questions |
| `/api/database/questions/:id/lean-conversions` | GET | Get all Lean conversions for a question |
| `/api/database/clear` | POST | Clear data by stage (lean/preprocess/verification) |
| `/api/statistics/overview` | GET | Get overall statistics |
| `/api/config/sites` | GET/POST | Manage site configurations |
| `/api/config/models` | GET/PUT | Manage model configurations |

## Development

### Converter Selection

Choose the right converter for your use case:

**Kimina Legacy Converter**:
- ✅ Fast conversion speed (local model)
- ✅ No API costs
- ✅ Good for batch processing
- ❌ Requires VLLM server setup
- ❌ Less accurate on complex problems

**GLM LLM Agent Converter**:
- ✅ Higher quality output
- ✅ Better at understanding context
- ✅ Iterative error correction
- ✅ No local model setup needed
- ❌ API costs apply
- ❌ Slower than local model

### Testing Lean Conversion

Use the interactive test tool to test Lean conversion without going through the full pipeline:

```bash
python test_lean_converter.py
```

This allows you to:
- Test question conversion (theorem declaration only)
- Test answer conversion (complete theorem with proof)
- Quickly iterate on prompts and see results
- Compare converter outputs side-by-side

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

### Dual Converter Workflow

The dual converter system allows you to leverage both converters:

1. **Initial Processing with Kimina**:
   - Process large batches quickly with Kimina Legacy
   - Get baseline Lean code for all questions

2. **Selective Enhancement with GLM**:
   - Use GLM LLM Agent for questions that failed verification
   - Apply GLM converter to complex problems needing higher accuracy
   - Compare outputs from both converters

3. **Verification and Selection**:
   - Run verification on both converter outputs
   - Select the best result based on verification status
   - Track which converter produced verified code

4. **Parallel Processing**:
   - Both converters can run simultaneously
   - Each maintains independent progress tracking
   - No interference between converters

## Troubleshooting

### Lean Conversion Issues

**Problem**: Kimina converter fails to start
- **Solution**: Ensure VLLM server is running on port 8000
- **Check**: `curl http://localhost:8000/v1/models`

**Problem**: GLM converter returns errors
- **Solution**: Verify ZHIPU_API_KEY is set correctly
- **Check**: API key has sufficient quota

**Problem**: Conversion produces invalid Lean code
- **Solution**:
  - For Kimina: Check VLLM model is loaded correctly
  - For GLM: Increase `LEAN_MAX_ITERATIONS` for more correction attempts
  - Check kimina-lean-server is running for verification

### Verification Errors

**Problem**: Verification timeout
- **Solution**: Ensure kimina-lean-server is running on port 9000
- **Check**: `curl http://127.0.0.1:9000/health`

**Problem**: All conversions fail verification
- **Solution**:
  - Try different converter (Kimina vs GLM)
  - Increase max iterations for GLM converter
  - Check preprocessing quality (theorem names, content)

## License

MIT License - See LICENSE file for details
