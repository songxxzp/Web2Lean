# Web2Lean Tests

## Test Files

### Unit Tests
`test_math_se_crawler.py` - Unit tests for MathSECrawler with mocked API responses

### Integration Tests
`test_real_api.py` - Tests against real StackExchange API

## Running Tests

### Run Unit Tests
```bash
python tests/test_math_se_crawler.py
```

### Run Integration Tests (requires network)
```bash
python tests/test_real_api.py
```

## Test Results

### Unit Tests (Latest)
```
test_api_error_handling .... ok
test_api_url_construction .... ok
test_crawler_initialization .... ok
test_fetch_questions_page .... ok
test_get_status .... ok
test_parse_question .... ok
test_strip_html .... ok

----------------------------------------------------------------------
Ran 7 tests in 0.068s

OK
```

### Integration Tests (Latest)
```
============================================================
Testing MathSECrawler with Real API
============================================================

✓ Crawler initialized
  API Base: https://api.stackexchange.com/2.3
  Pages to crawl: 1

------------------------------------------------------------
Test 1: Fetching questions from API...
------------------------------------------------------------
✓ Successfully fetched 1 questions
  First question ID: 5116355
  Title: Can this integral be computed or is it not possible?...
  Has answers: No

------------------------------------------------------------
Test 2: Parsing question...
------------------------------------------------------------
✓ Successfully parsed question
  Title: Can this integral be computed or is it not possible?...
  Score: -3
  Body (stripped): $$
\int_{-\infty}^{\infty}\int_{-\infty}^{\infty} \cos{x} \e...

------------------------------------------------------------
Test 3: Running full crawl (1 page)...
------------------------------------------------------------
Page 1 completed: 1 questions
✓ Crawl completed
  Run ID: run_math_stackexchange_20251224_134512
  Questions crawled: 1
  Answers crawled: 0
  Questions in database: 1
  First DB question: Can this integral be computed or is it not possible?...

============================================================
✓ ALL TESTS PASSED
============================================================
```

## MathSECrawler Status

- ✅ Unit tests passing
- ✅ Integration tests passing
- ✅ API connection working
- ✅ Data parsing working
- ✅ Database storage working
- ✅ Connected to backend API

The MathSECrawler is now fully functional and can be used via the web UI or API.
