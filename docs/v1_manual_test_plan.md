# Finance Agent V1 Manual Test Plan

This file is a manual regression checklist for the V1 demo. It is intentionally small and practical so it can be completed before publishing the repository.

## Test Record Format

Use this format when testing:

```text
Case ID / Input / Expected Behavior / Actual Result / Pass / Notes
```

## Startup

| Case ID | Input | Expected Behavior | Actual Result | Pass | Notes |
| --- | --- | --- | --- | --- | --- |
| START-01 | `uv sync` | Dependencies install successfully |  |  |  |
| START-02 | `uv run python -m app.main` | Server starts on `127.0.0.1:8001` |  |  |  |
| START-03 | Open `/` | Finance frontend is displayed |  |  |  |
| START-04 | Open `/docs` | FastAPI docs are displayed |  |  |  |

## Access Code

| Case ID | Input | Expected Behavior | Actual Result | Pass | Notes |
| --- | --- | --- | --- | --- | --- |
| AUTH-01 | Register new access code | Returns `access_code` and `user_id` |  |  |  |
| AUTH-02 | Login with valid access code | Restores the same `user_id` |  |  |  |
| AUTH-03 | Login with invalid access code | Returns a clear error |  |  |  |
| AUTH-04 | Refresh browser | Local access identity is restored |  |  |  |

## Natural Language Accounting

| Case ID | Input | Expected Behavior | Actual Result | Pass | Notes |
| --- | --- | --- | --- | --- | --- |
| CHAT-01 | `今天午餐花了20` | Saves one expense record |  |  |  |
| CHAT-02 | `今天中午吃饭20，晚上奶茶15，打车28` | Saves three expense records |  |  |  |
| CHAT-03 | `工资到账5000` | Saves one income record |  |  |  |
| CHAT-04 | Missing amount | Agent asks for or handles missing information safely |  |  |  |
| CHAT-05 | Sticker disabled | No sticker event is rendered |  |  |  |
| CHAT-06 | Sticker enabled | Sticker event is rendered after successful accounting |  |  |  |

## Import

| Case ID | Input | Expected Behavior | Actual Result | Pass | Notes |
| --- | --- | --- | --- | --- | --- |
| IMPORT-01 | Upload `resources/sample_bill.csv` | CSV is parsed, classified and saved |  |  |  |
| IMPORT-02 | Upload Excel bill | Excel is parsed, classified and saved |  |  |  |
| IMPORT-03 | Upload `resources/test_bill.png` | Vision model extracts transaction fields |  |  |  |
| IMPORT-04 | Upload unsupported file | API returns a clear error |  |  |  |
| IMPORT-05 | Import same file twice | Duplicate records are skipped |  |  |  |

## Query

| Case ID | Input | Expected Behavior | Actual Result | Pass | Notes |
| --- | --- | --- | --- | --- | --- |
| QUERY-01 | `最近5笔交易是什么` | Returns recent records |  |  |  |
| QUERY-02 | `餐饮一共花了多少` | Returns category total |  |  |  |
| QUERY-03 | `瑞幸消费了多少` | Returns merchant total |  |  |  |
| QUERY-04 | Frontend category filter | List updates by category |  |  |  |
| QUERY-05 | Frontend keyword search | List updates by keyword |  |  |  |

## Edit And Delete

| Case ID | Input | Expected Behavior | Actual Result | Pass | Notes |
| --- | --- | --- | --- | --- | --- |
| EDIT-01 | Edit amount in frontend | Record amount updates |  |  |  |
| EDIT-02 | Edit category in frontend | Record category updates |  |  |  |
| EDIT-03 | Delete a record | Record disappears from list |  |  |  |
| EDIT-04 | Delete invalid ID | API returns a clear error |  |  |  |

## Long-Term Memory

| Case ID | Input | Expected Behavior | Actual Result | Pass | Notes |
| --- | --- | --- | --- | --- | --- |
| MEM-01 | `以后奶茶都算娱乐` | Preference is saved to mem0 when configured |  |  |  |
| MEM-02 | `今天买奶茶18` | Retrieved memory influences classification |  |  |  |
| MEM-03 | No `MEM0_API_KEY` | App still runs without long-term memory |  |  |  |
| MEM-04 | Transaction-only message | Ordinary bill data is not written as durable memory |  |  |  |

## Privacy And Release

| Case ID | Input | Expected Behavior | Actual Result | Pass | Notes |
| --- | --- | --- | --- | --- | --- |
| REL-01 | `git status --short` | No `.env`, uploads, logs or cache files are staged |  |  |  |
| REL-02 | Search for API keys | No real secrets appear in tracked files |  |  |  |
| REL-03 | `python -m compileall app` | Python source compiles successfully |  |  |  |
| REL-04 | README review | Setup, APIs and limitations are accurate |  |  |  |

