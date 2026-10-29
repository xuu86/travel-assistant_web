# Open-Meteo Provider Acceptance

Date: 2026-10-29 (Asia/Shanghai)

## Scope and evidence

- Configured the local backend with `APP_WEATHER_PROVIDER=open_meteo`; no API key is required or stored.
- Reviewed the official [terms](https://open-meteo.com/en/terms), [pricing](https://open-meteo.com/en/pricing), [Forecast API docs](https://open-meteo.com/en/docs), and [licence](https://open-meteo.com/en/licence) on 2026-10-29.
- The free endpoint is for non-commercial use. The official terms list 600 calls/minute, 5,000/hour, and fewer than 10,000/day. The free service has no uptime guarantee. Data attribution is required under CC BY 4.0. No commercial or public-launch permission is asserted here.
- Performed five one-day requests, one for each registered pilot city, all for 2026-10-29. Every request succeeded; each returned the requested date with all six requested values present.
- After starting the configured API, made one additional end-to-end Shanghai API request for 2026-10-29 through 2026-10-31. It returned `live` with all three dates and no missing date ranges. This validates the route and normalization path, not a continuing uptime guarantee.

| City | Returned date | Missing values | Resolved grid coordinate | Elevation | Retrieved at (UTC) |
|---|---|---|---|---:|---|
| Shanghai | 2026-10-29 | none | 31.177504, 121.462550 | 7 m | 09:00:45Z |
| Suzhou | 2026-10-29 | none | 31.318100, 120.572110 | 7 m | 09:00:47Z |
| Wuxi | 2026-10-29 | none | 31.599297, 120.287420 | 4 m | 09:00:48Z |
| Jiaxing | 2026-10-29 | none | 30.755710, 120.708380 | 9 m | 09:00:50Z |
| Hangzhou | 2026-10-29 | none | 30.263618, 120.140510 | 11 m | 09:00:52Z |

Coordinates are provider-resolved forecast grid points, not station observations. This is a point-in-time connectivity check only and is not evidence of ongoing uptime, accuracy, or future coverage.

## Automated verification

- Backend: `uv run pytest -q` — 262 passed.
- Backend lint: `uv run ruff check .` — passed.
- Adapter tests use `httpx.MockTransport`; they do not access the network.

## Remaining production gate

Before public/commercial deployment, confirm intended use under the current provider terms or obtain a commercial-use licence. Add deployment-specific quota monitoring, alerting, privacy review, and an operational fallback. The provider does not promise uptime on the free service.
