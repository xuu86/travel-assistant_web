# Weather Provider Gate

> Updated: 2026-10-29 (Asia/Shanghai)
> Provider: Open-Meteo Forecast API
> Scope: local non-commercial trial configuration and five one-day connectivity checks.

## Official terms checked

The following official pages were reachable and reviewed on 2026-10-29:

- [Terms](https://open-meteo.com/en/terms)
- [Pricing](https://open-meteo.com/en/pricing)
- [Forecast API docs](https://open-meteo.com/en/docs)
- [Data licence](https://open-meteo.com/en/licence)

The Free API is restricted to non-commercial use. Current terms list limits of 600 calls/minute, 5,000/hour, and less than 10,000/day. The pricing page says the free service has no uptime guarantee. Open-Meteo data is licensed under CC BY 4.0; attribution and an indication of modifications are required. The pricing page identifies subscriptions, advertisements, commercial products, and promotional activities as commercial use examples. No commercial-use permission is inferred for this project, competition presentation, public hosting, or launch. Obtain the appropriate licence before those uses.

The adapter calls only `https://api.open-meteo.com/v1/forecast`, has no API key, sends at most the registered city coordinate and requested date range, and asks for six daily variables in `Asia/Shanghai` with Celsius, mm, and km/h units. The request has an 8-second timeout, one bounded retry for transient errors, and the existing 15-minute in-memory cache. The `.env` setting is ignored by Git and is local-only.

## Controlled connectivity check

The project owner requested a non-commercial provider configuration. On 2026-10-29, one request per registered pilot city was made for the same single date, 2026-10-29. No API key was used. After starting the configured backend, one additional end-to-end Shanghai API check queried 2026-10-29 through 2026-10-31 and returned all three dates. Only summarized metadata is retained; raw payloads and request URLs are not recorded.

| City | Result | Returned date | Missing metrics | Resolved grid coordinate | Elevation | Retrieved at (UTC) |
|---|---|---|---|---|---:|---|
| Shanghai | HTTP success | 2026-10-29 | none | 31.177504, 121.462550 | 7 m | 09:00:45Z |
| Suzhou | HTTP success | 2026-10-29 | none | 31.318100, 120.572110 | 7 m | 09:00:47Z |
| Wuxi | HTTP success | 2026-10-29 | none | 31.599297, 120.287420 | 4 m | 09:00:48Z |
| Jiaxing | HTTP success | 2026-10-29 | none | 30.755710, 120.708380 | 9 m | 09:00:50Z |
| Hangzhou | HTTP success | 2026-10-29 | none | 30.263618, 120.140510 | 11 m | 09:00:52Z |

The provider resolves city anchors to forecast grid coordinates; these are not weather-station observations. This check demonstrates only one-time connectivity and field mapping for the specified date. It does not establish ongoing availability, forecast accuracy, future coverage, quota headroom, or permission for commercial/public operation.

## Gate outcome

- Adapter implementation and offline tests are complete (WTH-10).
- The explicitly scoped five-city smoke check is complete (WTH-11, non-commercial trial scope only).
- Local backend configuration is `APP_WEATHER_PROVIDER=open_meteo`; unset/blank remains unconfigured and makes no upstream request.
- Production or public deployment remains gated on confirming the use is non-commercial or acquiring the required commercial licence, plus deployment-specific quota, monitoring, privacy, and availability controls.
