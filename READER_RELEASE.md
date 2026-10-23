# Reader Questions release

This release adds private editorial reporting, durable query logging, signed anonymous browser sessions, and baseline abuse limits. Public retrieval and answer generation accept only explicitly public records with a public surface policy and an approved public URL. Unknown or private records fail closed. The answer cache version changes, invalidating previous generated answers.

## Included

- SQLite query storage on `DATA_DIR/reader_queries.sqlite3`, with 90-day default retention, a Sheets outbox, retry backoff, event IDs in column N for duplicate detection, and admin delivery status. SQLite is authoritative; Sheets is a mirror.
- Basic email, telephone, street-address and self-introduction redaction. URL query strings and fragments are removed. Redaction is best effort; editors must review examples before sharing. Existing retained JSON logs are imported once as legacy records and excluded from trend counts because old sessions were unreliable.
- Signed sessions last 12 hours and persist in sessionStorage across queries and same-tab page reloads. They are not identities, proof of humanity, or model conversation memory.
- Rate limits on chat and related-card endpoints: 20 requests/minute and 120/hour per resolved IP, 20/minute per signed session, and 120/minute overall. Four active requests per process. Session issuance is separately limited. Client-supplied session IDs cannot bypass the signed session. Browser origin checks and known crawler-agent rejection provide additional screening, not proof of human use.
- An authenticated Reader Questions report in `/admin`: 7/30/90-day views, themes and reporting prompts, distinct sessions, constraints, weak-answer indicators, redacted examples, existing sources and session sequences. Test traffic, legacy logs, exact same-session repeats and rapid bursts are excluded. Topic assignment and suggested angles use transparent rules; they are not new facts inferred by an LLM. Reports cap analysis at 20,000 recent records and label truncation.
- Authentication for magazine uploads and the Drive-file proxy; safe upload filenames; private admin responses use no-store/noindex. Private COGNITION output is disabled in public responses regardless of its old feature flag. Legacy transcript endpoints require a corresponding published HubSpot transcript.
- The erroneous rule treating every mention of 2026/2027 as a future event is corrected. Public correction responses no longer reveal internal editor notes.

## Deployment

1. Deploy backend and `widget/embed.js` together through the existing GitHub/Render workflow. Existing open browser tabs need reloading to acquire a signed session. `/widget.js` now requires cache revalidation.
2. Keep the existing persistent Render disk mounted at `/data` and `DATA_DIR=/data`. Back up the SQLite database along with the index. This release does not modify existing public PDF files or upload/ingest the Q3 issue.
3. Configure a strong `ADMIN_PASSWORD`; the default `change-me` is rejected. Keep `GOOGLE_SERVICE_ACCOUNT_JSON` and `GOOGLE_SHEET_ID` set. The service account needs editor access to the sheet. Set `GOOGLE_SHEET_WORKSHEET` if the log is not its first tab. Delivery errors appear in admin and remain queued; this code cannot repair missing production credentials or sharing permissions.
4. On Render (`RENDER=true`, set by the platform), rate limits use Cloudflare's edge-replaced `CF-Connecting-IP`, not caller-controlled `X-Forwarded-For` or Uvicorn's derived client address. Missing or malformed edge identity fails closed for public chat/session requests. This relies on Render's Cloudflare-only public ingress: do not expose this service through a direct origin or untrusted private-network proxy, and do not manually enable `RENDER=true` elsewhere. Other hosts use the resolved socket client and require a separately verified trusted-proxy configuration. Keep one web worker initially; rate counters and the outbox lease are shared through SQLite, while the concurrency semaphore is per process. Multiple service instances require shared rate-limit storage. `/health` includes the deployed Git commit for release verification.
5. Include every legitimate widget host in `ALLOWED_ORIGINS`. Origins are not a bot security boundary. Verify the direct Render origin has the same application limits; do not rely only on a custom-domain proxy.
6. Optional tuning variables are listed in `.env.example`. `CHAT_SESSION_SECRET` is optional; without it, a random secret is persisted in SQLite. Rotating it invalidates sessions. Old privacy labels must be reviewed: no code can recognize confidential text already incorrectly labeled as public.

## Acceptance checks

- Ask two questions, reload and ask a third. Confirm the same anonymous session in admin and no client errors. The assistant still answers each question independently.
- Confirm the local event is present, then confirm its request ID appears once in column N of the configured sheet. Simulate Sheets unavailability in staging, restore access, and use Retry log delivery.
- Unauthenticated report/log/upload/Drive-proxy requests must be rejected. The admin report must have `Cache-Control: no-store` and `X-Robots-Tag: noindex, nofollow`.
- In staging, test separate visitor IPs, forged tokens, expired sessions, excessive requests and a mixed public/private retrieval set. Private text must not reach generation, cards or citations. The tests exercise this with a sentinel private document.
- Confirm normal published transcripts and magazine links still work and public HubSpot SEO pages remain crawlable.

## Limits and follow-on work

Bots can imitate browsers and obtain sessions; this baseline limits cost and harvesting but cannot promise to stop all scraping. Add edge challenges and coordinated abuse detection if traffic warrants it. Keep sensitive research outside the public index as a second boundary. The report does not yet collect link clicks or compare periods automatically. It is a reporting lead generator, not a representative audience survey. Sheets retention is separate from local retention and must be managed by the sheet owner.

Tests: `python -m pytest tests/test_reader_release.py`; browser smoke test: `node tests/ui_release.cjs` with Playwright available. Browser tests use synthetic data only.
