# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added - AI-Report-Specific Filtering (Backward Compatible)

New optional config keys for filtering and ordering AI report pages:

- **`ai_report_path_prefix`** (str, default: `""`)
  - When non-empty, only pages whose `file.src_path` starts with this prefix are eligible for AI-report special handling.

- **`ai_report_recent_limit`** (int, default: `0`)
  - When `ai_report_path_prefix` is set and this is `> 0`: caps the number of homepage-highlighted AI report pages to this limit.

- **`ai_report_pin_to_top`** (bool, default: `False`)
  - When `ai_report_path_prefix` is set and this is `True`: sorts matching AI report pages ahead of non-matching pages in the nav `page_list` (homepage remains first).

### Compatibility

- **Backward compatible**: Existing users with only old config keys see no functional change.
- Compatible with MkDocs 1.6.x.
- No exception when pages have no `time` field or when `time` is malformed.

### Example Configuration

```yaml
plugins:
  - modified-awesome-pages:
      filename: pages.yml
      maximum_file_homepage: 20
      maximum_days_ahead: 365
      ai_report_path_prefix: "other_categories/daily/"
      ai_report_recent_limit: 60
      ai_report_pin_to_top: true
```

### Internal Changes

- Replaced numpy with Python built-in `sorted()` for page ordering (removes optional dependency).
- Added `_safe_parse_time()` helper for robust YYYYMMDD parsing (returns `None` on invalid/missing).
- Added `_is_ai_report_page()` helper for prefix-based page classification.
- Removed debug print statement.
