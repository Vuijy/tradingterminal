# SEC EDGAR Full-Text Search (EFTS): verified research notes

Produced by a research agent on 2026-10-18 against the live endpoint. Input for the supply-chain milestone (docs/ROADMAP.md, item 5).

## Endpoint spec

# SEC EDGAR Full-Text Search (EFTS) — verified spec (all requests run 2026-10-18)

Scripts, raw logs and saved JSON for every claim below are in
`C:\Users\REMIST~1\AppData\Local\Temp\claude\c--Users-Remi-Stefanescu-Downloads-tradingterminal\0993c870-972b-4b73-9216-71bed0b619bd\scratchpad\research\efts\` (probe01…probe10 + `efts_search.py`; outputs in `out\`).

## 1. Endpoint

- `GET https://efts.sec.gov/LATEST/search-index?<params>` — JSON. This is the API behind https://www.sec.gov/edgar/search/ (same parameter names in the UI's URL fragment).
- **GET only.** `POST` → HTTP 403 `{"message":"Missing Authentication Token"}` (API Gateway).
- Required headers: `User-Agent: "<App> <contact email>"` and `Accept-Encoding: gzip, deflate`. With httpx's default UA (`python-httpx/0.28.1`) the response is **HTTP 403 text/html** titled *"SEC.gov | Your Request Originates from an Undeclared Automated Tool"* (tested once).
- Responses are gzip (`content-encoding: gzip`, `vary: Accept-Encoding`), CORS `access-control-allow-origin: *`, served via CloudFront/API Gateway (`x-amzn-requestid`, `x-amz-cf-id`). No rate-limit headers of any kind.
- Index coverage: 2001 onward (oldest hit seen: 10-K405 filed 2001-03-19). Text indexed per *document* (primary doc **and each exhibit / XBRL R file** are separate hits). The indexed text (`doc_text`) is never returned; there are no highlights/snippets.
- The response echoes the OpenSearch query it actually ran under the top-level `query` key — read that to debug any parameter.

## 2. Parameters (each confirmed from the echoed query + results)

| param | effect (verified) |
|---|---|
| `q` | Free text. **Each `"quoted phrase"` → one `match_phrase` on `doc_text` in `bool.must`** (AND of phrases, words adjacent in order). **Bare words → one `match_phrase` per word** (so `Apple accounted for` ≡ `"Apple" "accounted" "for"`; it gave the same 1500 hits as `"Apple" "accounted for"` only because the stop word `for` matches everywhere — bare words do **not** enforce adjacency). Analyzer is case-insensitive and drops punctuation: `"apple"`=`"Apple"`=`"APPLE"` (1500 each); `"Apple Inc"`=`"Apple Inc."`=`"Apple, Inc."` (216 each); `"AT&T"` and `"T-Mobile"` work (805 / 266). |
| `q` operators | `OR` between terms → both go to `bool.should` and act as a real OR: `Apple OR Nvidia` = 2249 = 1864 + 436 − 51; with a required phrase, `(Apple OR Nvidia) "accounted for"` = 1671 = 1500 + 220 − 49 (so at least one should-term is required; parentheses are passed through literally as `"(Apple"`, `"Nvidia)"` and happen to work only because punctuation is stripped — don't rely on grouping). `NOT X` and `-X` → `bool.must_not` (identical: 1813 each); `-"multi word"` also works. `AND` is **not** an operator: it becomes the literal phrase `"AND"` (which matches everything), so `Apple AND Nvidia` = `Apple Nvidia` = 51. |
| `q` wildcards | A bare `word*` → OpenSearch `wildcard` on `doc_text` (lower-cased): `Appl*` ≥10 000 (matches "applicable", "application"…) — useless for names. Inside quotes `*` is kept literally: `"accounted for*"` ≡ `"accounted for"`, and `"compet* with Apple"` = 0 hits. No proximity: `"Apple customer"~10` becomes two phrases, the second being `"~10"`. Smart quotes `“Apple”` are tolerated (treated as plain `Apple`). |
| `forms` | Comma-separated: `forms=10-K,10-Q` → `{"terms":{"root_forms":["10-K","10-Q"]}}`. A value containing `/A` (e.g. `10-K/A`, `10-KT/A`) is matched on the exact `form` field instead. `root_forms` "10-K" **includes 10-K/A** (counts on one page: 93 × 10-K, 3 × 10-K/A, 3 × EX-13, 1 × XML) but **not 10-KT or 10-K405** (separate roots: 1109 and 3663 hits for "transition period"); `10-KSB` → 0 hits. **Case-sensitive**: `forms=10-k` → 0 hits. `filter_forms=10-K` (what the UI facet sends) → single `{"term":{"root_forms":"10-K"}}`. |
| `dateRange` | **Cosmetic.** `all`, `1y`, `30d`, `5y`, `custom` add **no** filter by themselves (echo shows none). |
| `startdt`, `enddt` | `YYYY-MM-DD` filing-date window → `{"range":{"file_date":{"gte":startdt,"lte":enddt}}}`. Applied **only when BOTH are present** (either one alone → no filter at all, silently). Works with or without `dateRange=custom`. Future `enddt` (2099-12-31) is fine. `start > end` → 200 with 0 hits. Wrong format (`01/01/2024`) → HTTP **200** with error JSON: `{"errorType":"ResponseError","errorMessage":"search_phase_execution_exception: [parse_exception] Reason: failed to parse date field [01/01/2024] with format [yyyy-MM-dd]...","trace":[...]}`. |
| `from` | Offset, echoed as `"from": N`; any integer works (150 tested). **Page size is fixed at 100** (`size=10` is ignored). Max `from` = **9900**: `from=10000` → HTTP 200 error JSON `"Result window is too large, from + size must be less than or equal to: [10000] but was [10100]"`. |
| `page` | **Ignored by the server** (`page=2`, `100`, `250` all echo `from: 0`). The UI sends both `page=N&from=(N-1)*100`; send `from` yourself. |
| `entityName` | Whitespace-split; every token must `match` the analyzed `display_names` field (case-insensitive, partial names OK): `Best Buy` → BEST BUY CO INC (20 hits for the Apple query). The UI's full string `Best Buy Co Inc  (BBY)  (CIK 0000764478)` also works. Combined with `q` as AND. |
| `ciks` | Comma-separated, **must be 10-digit zero-padded** (`0000764478` works; `764478` → 0 hits) → `{"terms":{"ciks":[...]}}`. Matches any filer listed on the filing (issuer CIK on a Form 4 too). |
| `locationType` + `locationCodes` | `located` → `{"terms":{"biz_states":["CA"]}}`; `incorporated` → `{"terms":{"inc_states":["DE"]}}`. |
| `category`, `sics`, `sort`, `size`, `page`, unknown params | **No effect** (echo unchanged). `category=form-cat1` does not restrict to annual/quarterly reports — use `forms`. |
| no `q` | Allowed if `entityName`, `forms`, `ciks` or location is given: server adds `{"term":{"sequence":{"value":1}}}` (primary documents only) and sorts `file_date desc, _id desc` → a free "latest filings" listing. With no params at all: HTTP 200 `{"error":"Blank search not valid.  Either entity, keywords, location, or filing types must be submitted.","hits":{"hits":[]}}` (note: different error shape, no `errorType`, no `hits.total`). |

Ordering: with `q`, hits are sorted by `_score` desc (no date sort available); without `q`, by `file_date` desc.

## 3. Response JSON

Top level: `took` (ms, 23–238 observed), `timed_out`, `_shards`, `hits`, `aggregations`, `query` (echo).

- `hits.total` = `{"value": N, "relation": "eq"}`; **capped at 10 000** → `{"value":10000,"relation":"gte"}` for broad queries. Exact counts come from `aggregations.form_filter`: with a single `forms` value its one bucket is the exact total (e.g. `q=the&forms=10-K` → total 10000/gte but `form_filter` = `[{"key":"10-K","doc_count":1734372}]`; `"accounted for"` in 10-K since 2024-01-01 = 17 364).
- `hits.max_score`, `hits.hits[]` (≤100).
- `aggregations`: `form_filter` (field `root_forms`), `entity_filter` (`display_names.raw`), `sic_filter` (`sics`), `biz_states_filter` (`biz_states`) — each `{"buckets":[{"key","doc_count"}…≤30], "sum_other_doc_count", "doc_count_error_upper_bound"}`. `entity_filter` is a cheap "which filers mention X most" list, but keys are display strings, and the same CIK appears under different strings when its ticker list changed (e.g. `Super Micro Computer, Inc.  (SMCI)` and `…(SMCI, SMCIP)`), so aggregate by CIK client-side.

One full hit, verbatim (first hit of `q="Apple" "accounted for"&forms=10-K&dateRange=custom&startdt=2024-01-01&enddt=2026-10-18`):

```json
{
  "_index": "edgar_file",
  "_id": "0000320193-25-000079:aapl-20250927.htm",
  "_score": 12.191149,
  "_source": {
    "ciks": ["0000320193"],
    "period_ending": "2025-09-27",
    "file_num": ["001-36743"],
    "display_names": ["Apple Inc.  (AAPL)  (CIK 0000320193)"],
    "xsl": null,
    "sequence": 1,
    "root_forms": ["10-K"],
    "file_date": "2025-10-31",
    "biz_states": ["CA"],
    "sics": ["3571"],
    "form": "10-K",
    "adsh": "0000320193-25-000079",
    "film_num": ["251437791"],
    "biz_locations": ["Cupertino, CA"],
    "file_type": "10-K",
    "file_description": "10-K",
    "inc_states": ["CA"],
    "items": []
  }
}
```

Field semantics (union of `_source` keys over all pages seen is exactly the 18 above):
- `_id` = `"<accession-with-dashes>:<document filename>"`; `_source.adsh` repeats the accession.
- `ciks` / `display_names`: parallel lists, one entry per filer on the filing (10-K: one; Form 4: `["0001780525","0000320193"]` ↔ `["Newstead Jennifer  (CIK 0001780525)","Apple Inc.  (CIK 0000320193)"]`, reporting owner first).
- `display_names` format: `"{Name}  ({TICKER}[, {TICKER2}…])  (CIK {10 digits})"` with **two spaces** between groups, or `"{Name}  (CIK {10 digits})"` when the registrant has no listed security. **Ticker present on 100/100 hits** of each 10-K page for queries (a)(b)(c), 58/61 for (d), 73/74 for a NVIDIA supplier query; multiple tickers list share classes/preferreds (`GS, GSCE, GS-PA, GS-PC, GS-PD`; `BHR, BHR-PB, BHR-PD`). The ticker string reflects the filing-time status (same CIK appears as `(GTI)` and `(GTIJF)`, `(BSAI)` and `(IMII, IMIID)`, with and without a ticker for MULIANG). On Form 4 hits Apple showed **without** ticker.
- `form` = exact form (`10-K`, `10-K/A`); `root_forms` = base form list; `file_type` = type of *this document* within the filing (`10-K`, `10-K/A`, `EX-21`, `EX-10.21`, `EX-13`, `EX-4.11`, `EX-99.1`, `XML` for XBRL R-files); `file_description` = index description (usually equals `file_type`); `sequence` = document number in the filing, **1 = primary document** (an EX-10.21 hit had `sequence: 6`).
- `file_date` (filing date, the field all date filters use), `period_ending` (may be null), `file_num`, `film_num`, `biz_states`, `biz_locations`, `inc_states`, `sics`, `items` (8-K item codes, e.g. `["2.02","9.01"]`, else `[]`), `xsl` (null for HTML docs; e.g. `"xslF345X06"` for XML forms 3/4/5).

## 4. Building the document URL from a hit (confirmed by download)

```
cik      = int(_source.ciks[0])            # any CIK on the filing works (issuer or owner, both returned 200)
adsh     = _source.adsh.replace("-", "")    # or _id.split(":")[0]
filename = _id.split(":", 1)[1]
url      = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh}/{quote(filename)}"
```
- Verified: `https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm` → 200 text/html 1 520 315 bytes (chunked, no content-length); 60+ other 10-K/exhibit URLs built this way all returned 200 (sizes 0.26–9.6 MB).
- Zero-padded CIK in the path works via 301 → unpadded (`/data/0000320193/...` → final `/data/320193/...`). **Accession with dashes in the path → 403.**
- `HEAD` works (`content-length: 111125` = compressed size, `last-modified` present).
- If `xsl` is non-null, `/{adsh}/{xsl}/{filename}` gives the browser-rendered HTML (`.../000114036126039785/xslF345X06/form4.xml` → text/html 15 729 B; without xsl → text/xml 3 294 B).
- Same User-Agent rule applies to www.sec.gov. Filing index page: `https://www.sec.gov/Archives/edgar/data/{cik}/{adsh}/` (not needed for the hit itself).

## 5. Error behaviour summary

| condition | HTTP | body |
|---|---|---|
| missing/generic User-Agent | 403 | HTML "Undeclared Automated Tool" |
| OpenSearch error (bad date format, `from`+100 > 10000) | **200** | `{"errorType":"ResponseError","errorMessage":"…","trace":[…]}` |
| no search criteria at all | **200** | `{"error":"Blank search not valid. …","hits":{"hits":[]}}` (no `hits.total`) |
| POST | 403 | `{"message":"Missing Authentication Token"}` |
| start>end, unknown params, `forms=10-k` | 200 | normal shape, 0 hits / ignored |

A client must check both `errorType` and `error` keys before touching `hits.total`.

## 6. Performance and limits (measured)

- Latency: 0.17–2.4 s per page, median ≈0.5 s over 12 varied sequential requests (server `took` 23–130 ms; repeated identical queries ≈0.18 s, i.e. cached). A 100-hit page is ≈58 KB gzipped.
- Rate limiting: no `x-ratelimit-*`/`retry-after` headers; 8 back-to-back unthrottled requests (2.4 req/s achieved) and 12 at ~3.3 req/s all returned 200. SEC's published fair-access ceiling is 10 req/s across sec.gov; stay well under it (this research used ≤3.3 req/s, sequential).
- Hits cap: `total.value` ≤ 10 000 (`relation: gte` beyond); retrievable window is `from` ≤ 9 900 (≤10 000 hits). To enumerate more, split the query by `startdt/enddt` windows or add `forms`/`ciks` filters; use `aggregations.form_filter` for exact counts.
- Each filing yields several hits (primary doc + exhibits); dedupe by `adsh` (or by CIK for a relationship map) and prefer `sequence == 1` / `file_type == form`.

## Query strategy for supplier / customer / competitor discovery

## General principles (all numbers: forms=10-K, startdt=2024-01-01, enddt=2026-10-18)

1. EFTS is a **document-level AND of phrases with no proximity operator**, so a loose query like `"X" "accounted for"` degenerates to "any 10-K that mentions X" (`"accounted for"` alone matches 17 364 of the 10-K documents in the window). Precision of the loose task queries, judged from the downloaded documents: (a) `"Apple" "accounted for"` 1/10 true major customer (Take-Two), 2 self, 2 partner, 5 noise; (b) `"Nvidia" "accounted for"` 0/10 as customer, 5/10 as *supplier*, 3 self; (c) `"compete with" "Apple"` ~3/10 loosely competitive, 0 strict; (d) `"purchase" "from Apple"` 1/10 supplier-like (Match Group platform fees) + 1 reverse direction; (e) `"from NVIDIA" "GPUs"` 3/10 supplier, 3 competitor, 2 self, 2 partner.
2. **Tight phrases are precise but sparse** because they must match the filer's exact wording. Use a *union of several templates*, dedupe by CIK (keep newest `file_date`), drop the searched company's own CIK, and keep `sequence == 1` docs (or at least `file_type` in {form, EX-13}), then confirm by downloading the primary document and extracting a ±200-char window around the name (the 10-K is 1–10 MB; this research did that for ~70 documents at 0.3–0.6 s each). Treat EFTS as a candidate generator, never as the final answer.
3. Always exclude the target's own filings: `ciks` cannot be negated, so either filter client-side on `cik != target_cik` or add a negative phrase that only the target's own filing contains (e.g. `-"NVIDIA Corporation and Subsidiaries"` removed exactly the 3 NVIDIA 10-Ks from a 17-hit result).

## (a) Filers naming X as a MAJOR CUSTOMER
Templates, in order of precision (Apple results): `"{X Inc. / X} accounted for"` (`"Apple Inc. accounted for"` 2 hits: Knowles 16 %, Amkor 27.7 % — 2/2), `"sales to {X}"` (3/3, Amkor), `"{X} represented"` (2, Warner Music), `"customers include {X}"` (6 hits/3 entities, ~all customers), `"customers such as {X}"` (7, mostly customers), `"customers including {X}"` (2, Pixelworks). Because `match_phrase` requires adjacency, run both the short name and the legal name (`"Apple accounted for"` and `"Apple Inc. accounted for"` returned disjoint sets: WMG vs Knowles/Amkor; punctuation is ignored so `Inc.`/`Inc`/`, Inc.` are one variant). Expect sparse results: for NVIDIA every customer template returned 0 (`"NVIDIA accounted for"`, `"NVIDIA Corporation accounted for"`, `"sales to NVIDIA"`, `"revenue from NVIDIA"`, `"customers include NVIDIA"`); suppliers to NVIDIA write "Customer A". Looser fallbacks with usable top-10 precision: `"{X}" "our largest customers"` (29 hits for NVIDIA: Marvell, Arista, Mercury, Netgear, Qualcomm, SMCI... mixed directions) and `"{X}" "largest customer"` (9). The loose `"{X}" "accounted for"` is only useful with the client-side verification step, and `"{X}" "accounted for" "10% of"` barely narrows it (1201 vs 1500).

## (b) Filers naming X as a SUPPLIER
Filers rarely say "we purchase from X"; direct phrases returned 0 (`"purchases from Apple"`, `"products from Apple"`, `"supplied by Apple"`, `"devices from Apple"`, `"depend on NVIDIA"`), and `"purchase" "from Apple"` (61) is noise. What works is **domain vocabulary + the name**:
- Hardware/GPU buyers (CoreWeave-like): `"NVIDIA GPUs" "our suppliers"` (17 hits; 10/14 true after removing NVIDIA itself: SharonAI, IREN, CoreWeave, One Stop Systems, Bit Digital, HIVE, WhiteFiber, Rumble, HP, Jet.AI), `"{X}" "suppliers accounted for"` (7; CoreWeave, Super Micro ×3, Corvex true; Graphjet noise), `"{X}" "supply of GPUs"` (7; ~5 true, AMD is a competitor), `"{X}" "GPUs" "sole source"` (18; IREN, Bit Digital, ChronoScale, SMCI, Axe Compute true; Arista/Intel competitor), `"purchase" "GPUs" "{X}" "supplier"` (74; ~6/10 true excluding self). Avoid `"{X}" "sole supplier"` (11 hits, all AMD/Intel/Mobileye/Lumentum talking about themselves or TSMC) and `"rely on {X}"` (1).
- Retail/distribution (Apple as vendor to a retailer): `"Apple" "Samsung" "largest suppliers"` (6: Best Buy ×3 true), `"Apple" "merchandise vendors"` (25: Best Buy true, apparel retailers noise), `"Apple products" "resell"` (5: Ingram Micro true), `"Apple" "our vendors"` (621, but top-10 by score had Ingram Micro, Target, QVC ×2, PC Connection — true resellers), `"Apple" "largest suppliers"` (26, ~1-2/10). `"Apple" "authorized reseller"`/`"authorized distributor"` found nothing useful (4/13, unrelated). `"Apple" "key suppliers"` (168) and `"Apple" "significant suppliers"` (33) are noise.
- Beware of direction flips: Qualcomm, Qorvo, Skyworks, InterDigital, Coherent, Globalstar surface in "supplier" queries about Apple/NVIDIA but are suppliers *to* them (verify the snippet).

## (c) Filers naming X as a COMPETITOR
Exact templates: `"competitors include {X}"` (Apple 2: Movano; NVIDIA 3: GSI Technology — all true), `"compete with {X}"` (Apple 2: Jamf), `"competitors like {X}"` (Apple 2: Triller), `"competitors such as {X}"` (Apple 1: DiamondRock — matched "Apple Hospitality"; a name-collision), `"competes with {X}"`/`"competition from {X}"`/`"compete against {X}"`/`"competitors including {X}"` → 0 for both names. Because competitors are usually listed ("Cisco, Juniper, Nvidia and ..."), exact templates miss most of them; the loose `"compete with" "{X}"` (1356 for Apple) needs the snippet verification step, where the rule "name appears within ~200 chars of compet*" works (Arista, AMD, Intel for NVIDIA). `"competitors" "such as Apple"` (312) is a middle ground dominated by app companies mentioning Apple/Google platforms.

## Name variants and collisions
- Search the **short name** as the primary term and the legal name as a second template: in the window `"Apple"` matches 1 864 10-K documents, `"Apple Inc"` 216, `"AAPL"` 14; `"Nvidia"` 436, `"NVIDIA Corporation"` 100, `"NVDA"` 22. **Tickers almost never appear in filing text — do not search by ticker**; use `display_names` to read the ticker of the *filer* instead.
- Case-insensitive (`"apple"`=`"Apple"`=`"APPLE"`), punctuation-insensitive (`"Apple Inc."`=`"Apple, Inc."`), so one variant per distinct token sequence is enough. Wildcards do not help (`Appl*` matches "applicable").
- Short names collide: `"Apple"` also hits Apple Hospitality REIT and Apple iSports (both in the top 10 of some queries) — add `-"Apple Hospitality" -"Apple iSports"` or filter by the filer CIK; `"Alphabet"` (304) vs `"Google"` (2 486) — query the brand the filers actually use; `"Meta"` matches the word "meta". For multi-brand parents, run one query per brand.

## Date windows
- Filters apply to **filing date** (`file_date`), not fiscal period, and need both `startdt` and `enddt` (a future `enddt` such as 2099-12-31 is fine). FY2025 10-Ks were filed Jan–Sep 2026, so "latest annual report of every filer" = a window of roughly the last 15–18 months; a 2-year window catches a filer twice (dedupe by CIK, keep newest).
- Stay under the 10 000-hit window: the loose Apple queries (1 500 docs) fit on 15 pages; `"the"`-class queries do not — split by date or by `forms`.
- 10-K only (`forms=10-K`) excludes 10-KT/10-K405 roots and 20-F/40-F foreign filers; add `20-F` if non-US suppliers/customers matter (`forms=10-K,20-F`).

## Caveats

- Unofficial API: efts.sec.gov is the backend of the EDGAR full-text search UI and is not listed among the documented data.sec.gov APIs; parameter behaviour above is what the server did on 2026-10-18 and may change without notice.
- `dateRange` is purely cosmetic and `startdt`/`enddt` only apply when BOTH are present; a request with only `startdt` silently searches all years since 2001.
- `page` and `size` are ignored by the server; paginate with `from` in steps of 100, maximum `from=9900`. `hits.total.value` is capped at 10 000 (relation 'gte'); exact counts come from `aggregations.form_filter`.
- Application errors (bad date format, result window too large, blank search) arrive with HTTP 200 in two different JSON shapes (`errorType`/`errorMessage` vs `error`); a client must check for those keys before reading `hits.total`.
- One filing produces many hits (primary document plus every exhibit and XBRL R-file); dedupe by accession (`adsh`) or by CIK and prefer `sequence == 1`. A phrase match may live in an exhibit (e.g. Globalstar's EX-10.21), and the hit does not say where in the text it matched - there are no snippets or highlights.
- No proximity search: a multi-phrase query only guarantees that all phrases occur somewhere in the same document. Any relationship label derived from EFTS alone is a hypothesis; this research confirmed labels by downloading the documents, which an implementation should also do (1-10 MB per 10-K, 0.3-0.6 s each).
- Few filers name NVIDIA as a >10% customer in phrase form (0 hits for five customer templates); expect sparse customer results for suppliers that anonymize customers as 'Customer A'.
- display_names ticker strings reflect the filing-time registrant status and vary for the same CIK across filings (SMCI vs 'SMCI, SMCIP', GTI vs GTIJF, present vs absent for MULIANG); aggregate by CIK, not by display name. Form 4 hits showed Apple without a ticker.
- `forms` values are case-sensitive and root-based: `10-K` includes `10-K/A` but not `10-KT`, `10-K405`, `20-F`; a value containing `/A` switches to an exact `form` match. `category`, `sics`, `sort` and unknown parameters are silently ignored.
- `ciks` must be 10-digit zero-padded (unpadded returns 0 hits, no error). Archive document URLs need the accession WITHOUT dashes (with dashes -> 403); padded CIK in the path redirects (301) to the unpadded form.
- Rate limits: no limit headers were observed and bursts of 8 unthrottled requests passed, but the test never exceeded ~3.3 req/s sustained; SEC's stated fair-access ceiling is 10 req/s across all sec.gov hosts and a missing/generic User-Agent is rejected with 403 immediately. Keep EFTS calls behind the project's cache (results for a given query/window are stable for a day).
- The 10,000-hit retrieval window plus relevance-only ordering (no date sort when q is present) means broad queries cannot be enumerated completely; narrow by date windows or filters.
- All experiments used forms=10-K and the filing window 2024-01-01..2026-10-18; precision numbers quoted are from top-10 inspection of single pages and are indicative, not statistically tight.

## Working Python snippet

```python
"""SEC EDGAR Full-Text Search (EFTS) client: one function, httpx, no other deps.

Verified against https://efts.sec.gov/LATEST/search-index on 2026-10-18.
Executed output (python -I efts_search.py):
  total=2 (eq) from=0 n=2 secs=0.54
  {"cik": "0001319161", "entity_name": "Warner Music Group Corp.", "ticker_if_shown": "WMG", "form": "10-K", "file_type": "10-K", "file_date": "2025-11-20", "period_ending": "2025-09-30", "accession": "0001319161-25-000034", "primary_doc_url": "https://www.sec.gov/Archives/edgar/data/1319161/000131916125000034/wmg-20250930.htm"}
  {"cik": "0001319161", "entity_name": "Warner Music Group Corp.", "ticker_if_shown": "WMG", "form": "10-K", "file_type": "10-K", "file_date": "2024-11-21", "period_ending": "2024-09-30", "accession": "0001319161-24-000039", "primary_doc_url": "https://www.sec.gov/Archives/edgar/data/1319161/000131916124000039/wmg-20240930.htm"}
  expected error: ResponseError: search_phase_execution_exception: [parse_exception] Reason: failed to parse date field [01/01/2024] with format [yyyy-MM-dd]:
  expected error: Blank search not valid.  Either entity, keywords, location, or filing types must be submitted.
  page2 total=1500 from=100 n=100 first=LiveOne, Inc. (LVO) primary=True
  download: https://www.sec.gov/Archives/edgar/data/1319161/000131916125000034/wmg-20250930.htm 200 text/html 2666577 bytes
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{adsh_nodash}/{path}"
PAGE_SIZE = 100            # fixed by the server; `size` is ignored
MAX_FROM = 9_900           # from + 100 must be <= 10_000 (index.max_result_window)

# "Apple Inc.  (AAPL)  (CIK 0000320193)"  |  "Lottery.com Inc.  (LTRY, LTRYW)  (CIK 0001673481)"
# "ALL FOR ONE MEDIA CORP.  (CIK 0001286459)"  (no ticker)
_DISPLAY_RE = re.compile(
    r"^(?P<name>.*?)\s+(?:\((?P<tickers>[A-Z0-9][A-Z0-9.\-]*(?:,\s*[A-Z0-9][A-Z0-9.\-]*)*)\)\s+)?\(CIK\s+(?P<cik>\d{10})\)\s*$"
)


class EftsError(RuntimeError):
    """HTTP error, 403 (bad User-Agent), or an application error returned with HTTP 200."""


def parse_display_name(display: str) -> dict[str, Any]:
    m = _DISPLAY_RE.match(display)
    if not m:
        return {"entity_name": display, "ticker_if_shown": None, "cik": None}
    tickers = [t.strip() for t in m.group("tickers").split(",")] if m.group("tickers") else []
    return {"entity_name": m.group("name"), "ticker_if_shown": tickers[0] if tickers else None,
            "all_tickers": tickers, "cik": m.group("cik")}


def primary_doc_url(cik: str | int, adsh: str, filename: str, xsl: str | None = None) -> str:
    """Archive URL of the document that matched. `filename` is the part of `_id` after the colon.
    `xsl` (non-null only for XML forms such as 3/4/5) gives the browser-rendered variant."""
    path = f"{xsl}/{filename}" if xsl else filename
    return ARCHIVE_URL.format(cik=int(cik), adsh_nodash=adsh.replace("-", ""), path=quote(path))


def search_efts(
    q: str,
    *,
    user_agent: str,
    forms: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    from_: int = 0,
    ciks: list[str] | None = None,
    entity_name: str | None = None,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """One page (<=100 hits) of EDGAR full-text search.

    q      : EFTS syntax. "quoted phrase" -> match_phrase; bare words -> one match_phrase each
             (AND); OR between terms -> optional (boost-only when any required term exists);
             -word / NOT word -> must_not; word* -> wildcard (bare words only). No proximity.
    forms  : root form types, e.g. ["10-K"] (includes 10-K/A, 10-KT...). Case-sensitive.
    start/end : filing-date window, both 'YYYY-MM-DD'; BOTH must be given or neither applies.
    from_  : offset, any integer 0..9900 (page size is always 100).
    Returns {"total": int, "total_relation": str, "from": int, "hits": [normalized...],
             "entity_agg": [(display_name, doc_count), ...]}.
    """
    if from_ < 0 or from_ > MAX_FROM:
        raise ValueError(f"from_ must be within 0..{MAX_FROM}")
    params: dict[str, str] = {"q": q, "from": str(from_)}
    if forms:
        params["forms"] = ",".join(forms)
    if start and end:
        params.update(dateRange="custom", startdt=start, enddt=end)
    if ciks:
        params["ciks"] = ",".join(f"{int(c):010d}" for c in ciks)
    if entity_name:
        params["entityName"] = entity_name
    headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}

    own = client is None
    client = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        resp = client.get(EFTS_URL, params=params, headers=headers)
    finally:
        if own:
            client.close()
    if resp.status_code == 403:
        raise EftsError("403: SEC rejected the request; declare a User-Agent like 'AppName contact@example.com'")
    if resp.status_code >= 400:
        raise EftsError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    # Application errors come back with HTTP 200 in two shapes:
    #   {"errorType": "ResponseError", "errorMessage": "...", "trace": [...]}   (OpenSearch errors)
    #   {"error": "Blank search not valid. ...", "hits": {"hits": []}}            (validation)
    if "errorType" in data:
        raise EftsError(f"{data.get('errorType')}: {data.get('errorMessage')}")
    if "error" in data:
        raise EftsError(str(data["error"]))

    hits = []
    for h in data["hits"]["hits"]:
        s = h["_source"]
        adsh, _, filename = h["_id"].partition(":")
        adsh = s.get("adsh") or adsh
        filer_cik = (s.get("ciks") or [None])[0]
        parsed = [parse_display_name(d) for d in s.get("display_names") or []]
        who = next((p for p in parsed if p["cik"] == filer_cik), parsed[0] if parsed else {})
        hits.append({
            "cik": filer_cik,
            "entity_name": who.get("entity_name"),
            "ticker_if_shown": who.get("ticker_if_shown"),
            "form": s.get("form"),                 # exact form, e.g. 10-K/A
            "root_form": (s.get("root_forms") or [None])[0],
            "file_type": s.get("file_type"),       # document type within the filing: 10-K, EX-21, ...
            "is_primary_doc": s.get("sequence") == 1,
            "file_date": s.get("file_date"),
            "period_ending": s.get("period_ending"),
            "accession": adsh,
            "filename": filename,
            "primary_doc_url": primary_doc_url(filer_cik, adsh, filename, s.get("xsl")),
            "all_ciks": s.get("ciks"),
            "display_names": s.get("display_names"),
            "score": h.get("_score"),
        })
    agg = data.get("aggregations", {}).get("entity_filter", {}).get("buckets", [])
    return {
        "total": data["hits"]["total"]["value"],
        "total_relation": data["hits"]["total"]["relation"],
        "from": data.get("query", {}).get("from", from_),
        "hits": hits,
        "entity_agg": [(b["key"], b["doc_count"]) for b in agg],
    }


if __name__ == "__main__":
    import json, sys, time

    sys.stdout.reconfigure(encoding="utf-8")
    UA = "TradingTerminal research your.email@example.com"
    t0 = time.perf_counter()
    page = search_efts('"Apple accounted for"', user_agent=UA, forms=["10-K"], start="2024-01-01", end="2026-10-18")
    print(f"total={page['total']} ({page['total_relation']}) from={page['from']} n={len(page['hits'])} secs={time.perf_counter()-t0:.2f}")
    for h in page["hits"][:5]:
        print(json.dumps({k: h[k] for k in ("cik", "entity_name", "ticker_if_shown", "form", "file_type", "file_date", "period_ending", "accession", "primary_doc_url")}))
    time.sleep(0.3)
    # error path: bad date format -> EftsError raised from an HTTP 200 body
    try:
        search_efts('"Apple"', user_agent=UA, forms=["10-K"], start="01/01/2024", end="2026-10-18")
    except EftsError as e:
        print("expected error:", str(e)[:140])
    time.sleep(0.3)
    # error path 2: blank search -> {"error": ...} with HTTP 200
    try:
        search_efts("", user_agent=UA)
    except EftsError as e:
        print("expected error:", str(e)[:140])
    time.sleep(0.3)
    # pagination: second page of a broad query
    page2 = search_efts('"Apple" "accounted for"', user_agent=UA, forms=["10-K"], start="2024-01-01", end="2026-10-18", from_=100)
    print(f"page2 total={page2['total']} from={page2['from']} n={len(page2['hits'])} first={page2['hits'][0]['entity_name']} ({page2['hits'][0]['ticker_if_shown']}) primary={page2['hits'][0]['is_primary_doc']}")
    time.sleep(0.3)
    # download the first primary document to prove the URL
    h = page["hits"][0]
    r = httpx.get(h["primary_doc_url"], headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}, timeout=60, follow_redirects=True)
    print("download:", h["primary_doc_url"], r.status_code, r.headers.get("content-type"), len(r.content), "bytes")
```

## Sample queries


### `q="Apple" "accounted for" | forms=10-K | startdt=2024-01-01 enddt=2026-10-18  (task query a; relationship judged from downloaded documents)` (1500 hits)

- Apple Inc. (AAPL) (CIK 0000320193, 10-K 2025-10-31): noise (the searched company's own filing)
- Apple Inc. (AAPL) (CIK 0000320193, 10-K 2024-11-01): noise (self)
- Jamf Holding Corp. (JAMF) (CIK 0001721947, 10-K 2025-02-27): customer/partner, minor: 'Apple as a customer represented less than 1% of our total revenue'; Apple also a channel partner
- Jamf Holding Corp. (JAMF) (CIK 0001721947, 10-K 2024-02-27): customer/partner, minor (same text, prior year)
- Apple iSports Group, Inc. (AAPI) (CIK 0001134982, 10-K 2025-04-01): noise (name collision: unrelated company called Apple iSports)
- SOCKET MOBILE, INC. (SCKT) (CIK 0000944075, 10-K 2026-03-30): noise (iOS compatibility mention)
- TAKE TWO INTERACTIVE SOFTWARE INC (TTWO) (CIK 0000946581, 10-K 2026-05-22): CUSTOMER: 'Apple, Sony, Google, and Microsoft each accounting for more than 10.0% of our net revenue'
- SOCKET MOBILE, INC. (SCKT) (CIK 0000944075, 10-K 2025-03-25): noise
- SOCKET MOBILE, INC. (SCKT) (CIK 0000944075, 10-K 2024-03-25): noise
- GOLDMAN SACHS GROUP INC (GS, GSCE, GS-PA, GS-PC, GS-PD) (CIK 0000886982, 10-K 2026-02-25): partner (Apple Card issuer; Platform Solutions revenue from Apple Card customers), not a >10% customer

### `q="Nvidia" "accounted for" | forms=10-K | startdt=2024-01-01 enddt=2026-10-18  (task query b)` (220 hits)

- NVIDIA CORP (NVDA) (CIK 0001045810, 10-K 2024-02-21): noise (self)
- NVIDIA CORP (NVDA) (CIK 0001045810, 10-K 2026-02-25): noise (self)
- NVIDIA CORP (NVDA) (CIK 0001045810, 10-K 2025-02-26): noise (self)
- SharonAI Holdings Inc. (SHAZ) (CIK 0002068385, 10-K 2026-03-31): SUPPLIER (GPU allocations; 'We do not have long-term supply agreements with NVIDIA') + partner (NVIDIA Cloud Partner referrals)
- IREN Ltd (IREN) (CIK 0001878848, 10-K 2026-08-27): SUPPLIER (GPUs) and also customer ('cloud services agreement with NVIDIA, under which NVIDIA is a customer of the Group')
- IREN Ltd (IREN) (CIK 0001878848, 10-K 2025-08-28): SUPPLIER (NVIDIA H100/H200/GB300 GPU fleet)
- Serve Robotics Inc. /DE/ (SERV) (CIK 0001832483, 10-K 2024-02-29): SUPPLIER ('Key suppliers of single and limited source components include NVIDIA') + strategic investor
- AEye, Inc. (LIDR, LIDRW) (CIK 0001818644, 10-K 2026-03-18): technology partner (lidar integrated into NVIDIA DRIVE AGX); noise for customer/supplier
- CoreWeave, Inc. (CRWV) (CIK 0001769628, 10-K 2026-03-02): SUPPLIER ('all of the GPUs used in our infrastructure today are NVIDIA GPUs'; 'three suppliers accounted for 23%, 20%, and 17% of total purchases')
- COHERENT CORP. (COHR) (CIK 0000820318, 10-K 2026-08-14): customer/partner (multi-year strategic agreement with NVIDIA; Coherent sells optical transceivers), no % disclosed

### `q="compete with" "Apple" | forms=10-K | startdt=2024-01-01 enddt=2026-10-18  (task query c)` (1356 hits)

- Jamf Holding Corp. (JAMF) (CIK 0001721947, 10-K 2024-02-27): potential competitor + partner ('Apple could choose to develop competing technology')
- Jamf Holding Corp. (JAMF) (CIK 0001721947, 10-K 2025-02-27): potential competitor + partner
- PALTALK, INC. (PALT) (CIK 0001355839, 10-K 2024-03-15): weak competitor/platform dependency ('Apple App Store ... provides consumers with products that compete with ours')
- Appsoft Technologies, Inc. (ASFT) (CIK 0001651992, 10-K 2024-04-11): potential competitor ('increased competition if large companies ... such as Apple ... enter ... the games space')
- LIQUIDMETAL TECHNOLOGIES INC (LQMT) (CIK 0001141240, 10-K/A 2024-11-21): noise (Apple is a licensee of its IP)
- LIQUIDMETAL TECHNOLOGIES INC (LQMT) (CIK 0001141240, 10-K 2024-03-12): noise (licensee)
- LIQUIDMETAL TECHNOLOGIES INC (LQMT) (CIK 0001141240, 10-K 2026-03-12): noise (licensee)
- LIQUIDMETAL TECHNOLOGIES INC (LQMT) (CIK 0001141240, 10-K 2025-03-13): noise (licensee)
- Nextdoor Holdings, Inc. (KIND) (CIK 0001846069, 10-K 2024-02-27): noise/platform (OS privacy changes by Apple and Google)
- Appsoft Technologies, Inc. (ASFT) (CIK 0001651992, 10-K 2026-04-27): potential competitor

### `q="purchase" "from Apple" | forms=10-K | startdt=2024-01-01 enddt=2026-10-18  (task query d: Apple as supplier)` (61 hits)

- Globalstar, Inc. (GSAT) (CIK 0001366868, 10-K (document EX-10.21, sequence 6) 2025-02-28): reverse direction: Apple is Globalstar's CUSTOMER/financier (prepayment agreement; Globalstar is the 'Supplier')
- SOCKET MOBILE, INC. (SCKT) (CIK 0000944075, 10-K 2026-03-30): noise
- SOCKET MOBILE, INC. (SCKT) (CIK 0000944075, 10-K 2025-03-25): noise
- Owlet, Inc. (OWLT, OWLTW) (CIK 0001816708, 10-K/A 2024-04-29): noise (executive biography: 'joined Anaplan from Apple Inc.')
- Owlet, Inc. (OWLT, OWLTW) (CIK 0001816708, 10-K/A 2025-04-30): noise (biography)
- Mawson Infrastructure Group Inc. (MIGI) (CIK 0001218683, 10-K/A 2025-04-30): noise (management 'expertise from Apple')
- Owlet, Inc. (OWLT, OWLTW) (CIK 0001816708, 10-K/A 2026-04-30): noise (biography)
- Match Group, Inc. (MTCH) (CIK 0000891103, 10-K 2026-02-26): platform vendor (in-app purchase fees paid to Apple; relies on App Store) - the only supplier-like hit
- AMJ Global Technology (AMJT, KGNR) (CIK 0001593773, 10-K 2024-03-12): noise (develops apps for Apple devices)
- BIOREGENX, INC. (BRGX) (CIK 0001593184, 10-K 2024-04-12): noise (app available on Apple App Store)

### `q="from NVIDIA" "GPUs" | forms=10-K | startdt=2024-01-01 enddt=2026-10-18  (task query e: NVIDIA as supplier, CoreWeave-like)` (12 hits)

- NVIDIA CORP (NVDA) (CIK 0001045810, 10-K 2025-02-26): noise (self: 'customers who purchase products directly from NVIDIA')
- NVIDIA CORP (NVDA) (CIK 0001045810, 10-K 2026-02-25): noise (self)
- ADVANCED MICRO DEVICES INC (AMD) (CIK 0000002488, 10-K 2024-01-31): competitor ('intense competition from companies such as Nvidia in the supply of GPUs')
- SharonAI Holdings Inc. (SHAZ) (CIK 0002068385, 10-K 2026-03-31): SUPPLIER (sole/limited-source supplier risk on NVIDIA)
- IREN Ltd (IREN) (CIK 0001878848, 10-K 2026-08-27): SUPPLIER (NVIDIA GPU clusters)
- Axe Compute Inc. (AGPU) (CIK 0001446159, 10-K 2026-03-31): SUPPLIER ('We source GPU hardware primarily from NVIDIA Corporation')
- ANSYS INC (ANSS) (CIK 0001013462, 10-K 2024-02-21): technology partner (solvers tuned for NVIDIA GPUs); noise for supplier
- TERADATA CORP /DE/ (TDC) (CIK 0000816761, 10-K 2026-02-27): partner (integration/partnership list); noise
- Arista Networks, Inc. (ANET) (CIK 0001596532, 10-K 2025-02-19): competitor (InfiniBand/NVLink 'sold ... along with the GPUs from Nvidia')
- Arista Networks, Inc. (ANET) (CIK 0001596532, 10-K 2024-02-13): competitor

### `q="Apple Inc. accounted for" | forms=10-K | 2024-01-01..2026-10-18  (tight customer template)` (2 hits)

- Knowles Corp (KN) (CIK 0001587523, 10-K 2024-02-21): CUSTOMER: 'Apple Inc. accounted for approximately 16%, 15%, and 16% of our total revenues'
- AMKOR TECHNOLOGY, INC. (AMKR) (CIK 0001047127, 10-K 2024-02-16): CUSTOMER: 'Direct sales to Apple Inc. accounted for 27.7% of our net sales'

### `q="sales to Apple" | forms=10-K | 2024-01-01..2026-10-18` (3 hits)

- AMKOR TECHNOLOGY, INC. (AMKR) (CIK 0001047127, 10-K 2024-02-16): CUSTOMER (27.7% of net sales)
- AMKOR TECHNOLOGY, INC. (AMKR) (CIK 0001047127, 10-K 2026-02-20): CUSTOMER ('Direct sales to Apple and Qualcomm accounted for 29.8% and 11.1%')
- AMKOR TECHNOLOGY, INC. (AMKR) (CIK 0001047127, 10-K 2025-02-21): CUSTOMER (30.8%)

### `q="customers include Apple" | forms=10-K | 2024-01-01..2026-10-18` (6 hits)

- MICROSOFT CORP (MSFT) (CIK 0000789019, 10-K 2024-07-30): customer (generic list)
- GREEN DOT CORP (GDOT) (CIK 0001386278, 10-K 2026-03-16): customer (banking-as-a-service partner programs)
- GREEN DOT CORP (GDOT) (CIK 0001386278, 10-K 2025-03-04): customer
- GREEN DOT CORP (GDOT) (CIK 0001386278, 10-K 2024-02-29): customer
- Rubicon Technologies, Inc. (RBTC, RBTCW) (CIK 0001862068, 10-K 2024-03-28): customer
- Rubicon Technologies, Inc. (RBTC, RBTCW) (CIK 0001862068, 10-K/A 2024-05-20): customer

### `q="NVIDIA GPUs" "our suppliers" | forms=10-K | 2024-01-01..2026-10-18  (best NVIDIA-as-supplier template; add -"NVIDIA Corporation and Subsidiaries" to drop the 3 self hits -> 14)` (17 hits)

- SharonAI Holdings Inc. (SHAZ) (CIK 0002068385, 10-K 2026-03-31): SUPPLIER
- NVIDIA CORP (NVDA) (CIK 0001045810, 10-K 2026-02-25): noise (self)
- NVIDIA CORP (NVDA) (CIK 0001045810, 10-K 2025-02-26): noise (self)
- NVIDIA CORP (NVDA) (CIK 0001045810, 10-K 2024-02-21): noise (self)
- IREN Ltd (IREN) (CIK 0001878848, 10-K 2025-08-28): SUPPLIER
- CoreWeave, Inc. (CRWV) (CIK 0001769628, 10-K 2026-03-02): SUPPLIER
- ONE STOP SYSTEMS, INC. (OSS) (CIK 0001394056, 10-K 2026-03-18): SUPPLIER (builds systems on NVIDIA GPUs)
- ONE STOP SYSTEMS, INC. (OSS) (CIK 0001394056, 10-K 2024-03-21): SUPPLIER
- ONE STOP SYSTEMS, INC. (OSS) (CIK 0001394056, 10-K 2025-03-19): SUPPLIER
- Bit Digital, Inc (BTBT) (CIK 0001710350, 10-K 2025-03-14): SUPPLIER (GPU cloud)

### `q="NVIDIA" "suppliers accounted for" | forms=10-K | 2024-01-01..2026-10-18  (supplier-concentration note + name mention)` (7 hits)

- CoreWeave, Inc. (CRWV) (CIK 0001769628, 10-K 2026-03-02): SUPPLIER (verified snippet: all GPUs are NVIDIA; three suppliers 23%/20%/17% of purchases)
- Super Micro Computer, Inc. (SMCI) (CIK 0001375365, 10-K 2025-02-25): SUPPLIER ('Two of our suppliers accounted for 65.4% and 6.3% of total purchases'; NVIDIA named elsewhere in the filing)
- Corvex, Inc. (MOVE) (CIK 0001734750, 10-K 2026-03-31): SUPPLIER (three suppliers 63%/23%/9% of purchases; GPU infrastructure)
- Super Micro Computer, Inc. (SMCI) (CIK 0001375365, 10-K 2025-08-28): SUPPLIER (Supplier A 64.4%)
- Super Micro Computer, Inc. (SMCI, SMCIP) (CIK 0001375365, 10-K 2026-08-31): SUPPLIER (one supplier 63.1%)
- GRAPHJET TECHNOLOGY (GTIJF) (CIK 0001879373, 10-K 2025-12-23): noise (graphite raw-material suppliers)
- GRAPHJET TECHNOLOGY (GTI) (CIK 0001879373, 10-K 2025-07-15): noise

### `q="competitors include NVIDIA" | forms=10-K | 2024-01-01..2026-10-18` (3 hits)

- GSI TECHNOLOGY INC (GSIT) (CIK 0001126741, 10-K 2025-06-18): COMPETITOR
- GSI TECHNOLOGY INC (GSIT) (CIK 0001126741, 10-K 2024-06-13): COMPETITOR
- GSI TECHNOLOGY INC (GSIT) (CIK 0001126741, 10-K 2026-06-05): COMPETITOR

### `q="competitors include Apple" | forms=10-K | 2024-01-01..2026-10-18` (2 hits)

- Movano Inc. (MOVE) (CIK 0001734750, 10-K 2024-04-16): COMPETITOR (health wearables vs Apple Watch)
- Movano Inc. (MOVE) (CIK 0001734750, 10-K 2025-04-09): COMPETITOR

### `q="Apple" "Samsung" "largest suppliers" | forms=10-K | 2024-01-01..2026-10-18  (Apple-as-supplier, retailer vocabulary)` (6 hits)

- BEST BUY CO INC (BBY) (CIK 0000764478, 10-K 2024-03-15): SUPPLIER (Apple among Best Buy's largest merchandise vendors)
- IMMERSION CORP (IMMR) (CIK 0001058811, 10-K 2026-07-24): noise (haptics licensing)
- BEST BUY CO INC (BBY) (CIK 0000764478, 10-K 2025-03-19): SUPPLIER
- BEST BUY CO INC (BBY) (CIK 0000764478, 10-K 2026-03-18): SUPPLIER
- IMMERSION CORP (IMMR) (CIK 0001058811, 10-K 2026-03-12): noise
- Aaron's Company, Inc. (AAN) (CIK 0001821393, 10-K 2024-02-29): SUPPLIER (lease-to-own retailer sourcing electronics), plausible

### `q="Apple products" "resell" | forms=10-K | 2024-01-01..2026-10-18` (5 hits)

- Jamf Holding Corp. (JAMF) (CIK 0001721947, 10-K 2025-02-27): channel partner (resells alongside Apple)
- Jamf Holding Corp. (JAMF) (CIK 0001721947, 10-K 2024-02-27): channel partner
- Ingram Micro Holding Corp (INGM) (CIK 0001897762, 10-K 2026-03-03): SUPPLIER (IT distributor reselling Apple products)
- MNTN, Inc. (MNTN) (CIK 0001891027, 10-K 2026-02-19): noise
- Ingram Micro Holding Corp (INGM) (CIK 0001897762, 10-K 2025-03-05): SUPPLIER (distributor)