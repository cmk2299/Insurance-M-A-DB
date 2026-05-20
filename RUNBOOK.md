# RUNBOOK — insurance-intel

## Wenn ein Cron-Run failet

1. Logs prüfen:
   ```bash
   sudo journalctl -u insurance-intel.service --since "12 hours ago"
   ```
2. Letzten Run-Status in Postgres:
   ```sql
   SELECT id, started_at, finished_at, status, events_added, sources_failed, notes
   FROM loop_runs ORDER BY id DESC LIMIT 5;
   ```
3. Häufige Fehlerklassen:
   - **Nimble-API-Key abgelaufen:** Renew über dashboard.nimbleway.com, neuen
     Key in `/etc/insurance-intel.env` setzen, `sudo systemctl daemon-reload`.
   - **Anthropic-Rate-Limit:** Manuell Lauf später nachholen mit
     `sudo -u insurance-intel insurance-intel run`.
   - **Postgres-Verbindung weg:** `sudo systemctl status postgresql` → wenn
     down: `sudo systemctl restart postgresql`.
   - **Slack-Webhook-Rotation:** Neuer Webhook im cmk-digital-Workspace,
     ENV updaten.

## Manuell triggern

```bash
sudo systemctl start insurance-intel.service   # via systemd, voll mit Slack+Git
# oder ohne Slack/Git:
sudo -u insurance-intel /home/insurance-intel/insurance-intel/.venv/bin/insurance-intel dry-run
```

## Einzelne Source debuggen

```bash
sudo -u insurance-intel /home/insurance-intel/insurance-intel/.venv/bin/insurance-intel test-source vwheute
```

Schreibt nach Postgres, schickt aber kein Slack und committet nichts.

## Schema-Änderung

Sprint 1 hat nur eine Migration. Spätere Migrationen werden
`migrations/002_*.sql` etc. heißen, NICHT die 001 überschreiben. Wenn das
Schema sich ändert, immer ALTER TABLE statt DROP+CREATE — Daten sind
load-bearing für die spätere Trend-Analyse.

## ToS-Reminder

Die Hardlines aus `CLAUDE.md` Sektion "Hardlines" haben Vorrang vor
allem anderen. Wenn der Loop versehentlich auf vermittlerregister.info
zugreift (z.B. weil eine Trade-Press-Quelle einen Backlink rendert und
der Extractor dem folgt): SOFORT stoppen, Logs säubern, Hardline-Verstoß
in `decisions_log` des Cowork-Hauptprojekts dokumentieren. Hardline #3
ist nicht verhandelbar.

## Was tun bei "0 Events drei Wochen in Folge"

Das wäre eine Verletzung der Sprint-1-DoD. Diagnose-Reihenfolge:

1. Nimble-Search-Queries manuell durchspielen — liefern sie überhaupt
   Results? Wenn nein: Query-Templates zu eng formuliert, Nimble-Coverage-
   Problem oder Trade-Press-Quellen indizieren neue Inhalte erst spät.
2. LLM-Strukturierung am Fixture-Set durchspielen
   (`pytest -m live tests/test_structure.py`). Wenn die Fixtures klappen
   aber Live-Artikel nicht: Prompt vermutlich zu strikt, Schwelle für P1
   zu hoch.
3. Wenn Nimble-Search + LLM beide ok: dann liefern die Trade-Press-Quellen
   tatsächlich wenig — bedeutet Anbindung von Sprint 2 (First-Party-
   Newsrooms) vorziehen, weil dort die Pressemitteilungen früher landen.

Drei-Wochen-Null-Befund ist NICHT eine Failure des Codes, sondern eine
Information über die Marktrealität — entsprechend behandeln.

## Erweiterungs-Pfade für Sprint 2+
- Sprint 2: First-Party-Newsroom-Sources hinzu in `sources.py`, eigene
  Klasse `FirstPartySource` mit RSS-Feed-Parser statt Nimble-Search.
- Sprint 3: North-Data-API-Adapter als `northdata.py`, eventbasiertes
  Polling jeden Werktag, in `ma_events` mit `source_publication='northdata'`.
- Sprint 4: DIHK-Quartals-Statistik-Pull, eigene `dihk_stats`-Tabelle mit
  Aggregat-Datenpunkten.
