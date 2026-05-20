# insurance-intel — Loop-Anweisungen für Claude

## Mission
Wöchentliche Trade-Press-Signal-Aggregation für DACH-Versicherungsmakler-M&A.
Erste Säule des Multi-Source-Loops (Sprint 1). Folgesprints: First-Party-
Newsrooms, North-Data-API, DIHK-Quartals-Statistik.

## Hardlines (gelten in jedem Lauf, in jedem Edit, ohne Ausnahme)
1. **KEINE automatisierten Abfragen gegen `vermittlerregister.info`.** ToS § 4 VI b
   verbietet Robots zur Datensammlung/-auswertung. Robots.txt blockiert
   `/recherche?` und `/inhalt`. Diese Quelle wird im Code NIE adressiert.
2. **KEINE erfundenen Zahlen.** Bei Unsicherheit Feld leer oder
   `data_quality='hypothesis-pending-review'`. `event_date` und
   `transaction_value_eur` bleiben TEXT — text-flexibel für "undisclosed",
   "Q4 2025" usw.
3. **KEINE PII natürlicher Personen** (Privat-Adressen, Geburtstage). Nur
   juristische Personen + in der Trade-Press öffentlich genannte GF-Namen.
4. **Append-only Reports.** Reports in `reports/YYYY-WW.md`, vom Loop committed
   und gepusht. Manuelle Überschreibung historischer Reports ist verboten.
5. **Pro Quelle ≤1 Request/Sekunde**, User-Agent
   `CMK-Digital-Research <kontakt@cmkdigital.de>`.

## Loop-Run-Anweisung (was bei jedem Cron-Trigger passiert)
1. Lies letzten erfolgreichen Run-Timestamp aus
   `loop_runs.finished_at WHERE status IN ('succeeded','partial')`.
2. Für jede `source` in `src/insurance_intel/sources.py`:
   a. Render `nimble_query_template` mit `{date_range}` = `after:YYYY-MM-DD`
      (letzter Run, oder Coldstart-Lookback aus `.env`).
   b. `nimble search` mit der Query, `--max-results=NIMBLE_MAX_RESULTS`.
   c. Für jeden URL: `nimble --transform "data.markdown" extract --url ...`.
   d. Berechne `content_hash` aus normalisiertem Markdown.
   e. Skip wenn Hash bereits in `trade_press_hits` (Dedupe).
   f. Sonst: Insert in `trade_press_hits`, danach LLM-Strukturierung.
   g. Insert resultierende M&A-Events in `ma_events`.
3. Render Markdown-Digest aus diesem Run nach `reports/YYYY-WW.md`.
4. Slack-Webhook POST mit Block-Kit-Digest.
5. `git add reports/ && git commit -m "weekly run YYYY-WW: N events" && git push`.
6. Update `loop_runs` mit `finished_at` und `status`.

## Decision Rules (im LLM-Prompt + Post-Processing)

### P1 Direktes M&A-Event
Trigger: Artikel nennt konkreten Käufer + Verkäufer mit Datum oder
Datums-Approximation. Ein Artikel kann mehrere P1-Events enthalten
(Beispiel: cash-online-Nov-2025-MRH-Trowe-Story mit 4 Deals).

### P2 Konsolidator-Governance-Event
Trigger: CEO-Wechsel, neuer strategischer Partner, Refinanzierung,
Continuation-Fund bei einem der ~16 bekannten Konsolidatoren.

### P3 PE-Sponsor-Aktivität
Trigger: Permira / HG Capital / Anacap / TA Associates / Nordic Capital /
Bain / IK Partners / Macquarie / Great-West-Life Portfolio-News mit
DACH-Versicherungsbezug.

### P4 Markt-Aggregat
Trigger: FTI Consulting Barometer, KJB-Consulting-Studien, DIHK-Quartals-
statistik, AssCompact-Markt-Zusammenfassungen. `data_quality='aggregate-reference'`.

### P5 Finanz-/Stammdaten-Update
Trigger: Jahresabschluss-Erwähnung eines Konsolidators in der Trade-Press
(Umsatz, EBITDA, Mitarbeiterzahl). Echte Finanzdaten kommen erst in
Sprint 3 via North-Data-API.

## Konstanten
- Cron-Schedule: Sonntag 02:00 Europe/Berlin via systemd-timer.
- Retry-Strategie: implizit über Cron-Persistent=true (versäumte Slots beim
  Boot nachholen). Per-Run-Retries sind NICHT implementiert in Sprint 1 —
  bei Quellen-Ausfall wird der Run als `partial` markiert, der nächste
  Sonntag holt das ungelesene Material via Coldstart-Lookback nach.
- Wenn 1-2 von 8 Quellen scheitern: Status `partial`, Slack-Alert mit Liste.
- Wenn ≥3 Quellen scheitern: Status `failed`, Slack-Alert.
- `MIN_EVENTS_FOR_SUCCESS=1` standardmäßig — ein Sonntag ohne neue Events
  ist `partial`, nicht `failed`, weil das in der Trade-Press realistisch ist.

## Burggraben-Reminder
Trade-Press allein ist nicht der Burggraben — die Trade-Press ist für jeden
zugänglich. Was Sprint 1 produziert, ist die Skelett-Infrastruktur. Der
eigentliche CMK-Wert entsteht erst durch die Verknüpfung mit den
First-Party-Newsroom-Triggern (Sprint 2) und der North-Data-Event-
Subscription (Sprint 3) sowie der konsolidator-spezifischen Watchlist-
Logik in diesem File.

## Codebase-Hinweise
- Stack: Python 3.11+, uv-managed pyproject, psycopg3, pydantic-settings,
  typer, rich, anthropic, httpx.
- Tests: `pytest` mit pytest-mock. Live-Tests sind mit `@pytest.mark.live`
  markiert und kosten Anthropic-API-Calls, deshalb opt-in.
- Style: ruff für format+lint, mypy für type-check. CI fehlt in Sprint 1.

## Bekannte Konsolidatoren
Siehe `consolidators.yaml`. Liste konsistent mit dem Cowork-MVP-Demo v1.1
unter `~/Documents/Claude/Projects/CMK x InsuranceDB/CMK_InsuranceBroker_Platform/`.
Updates erfolgen koordiniert in beide Dateien.
