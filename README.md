# insurance-intel

DACH Versicherungsmakler M&A Signal Loop — Sprint 1.

Weekly cron, Trade-Press sweep über acht Quellen, LLM-Strukturierung via
Claude API, Postgres-Persistenz, Slack-Digest, Git-Audit-Trail.

## Status
Pre-Production-Scaffold. Wird ab erster Cron-Aktivierung produktiv. Definition
of Done für Sprint 1 ist binär: Sonntag 02:00 Cron läuft, Slack-Digest erscheint,
Git-Commit landet — drei Wochen mit durchschnittlich ≥5 unique Events.

## Quickstart (auf einer fresh Hetzner-VPS)

```bash
# 1. System-Voraussetzungen
sudo apt update && sudo apt install -y python3.11 python3.11-venv postgresql nodejs npm git
sudo npm install -g @nimble-way/nimble-cli

# 2. User anlegen
sudo useradd -m insurance-intel
sudo -u insurance-intel git clone <REMOTE> /home/insurance-intel/insurance-intel
cd /home/insurance-intel/insurance-intel

# 3. Virtualenv + Dependencies (uv-managed)
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo -u insurance-intel uv venv
sudo -u insurance-intel uv pip install -e .

# 4. Postgres-User + DB
sudo -u postgres psql <<'EOF'
CREATE USER insurance_intel WITH PASSWORD 'CHANGE_ME';
CREATE DATABASE insurance_intel OWNER insurance_intel;
EOF

# 5. Env-File
sudo cp .env.example /etc/insurance-intel.env
sudo nano /etc/insurance-intel.env    # echte Werte eintragen
sudo chown root:insurance-intel /etc/insurance-intel.env
sudo chmod 640 /etc/insurance-intel.env

# 6. Schema deployen
sudo -u insurance-intel /home/insurance-intel/insurance-intel/.venv/bin/insurance-intel init-db

# 7. Smoke-Test
sudo -u insurance-intel /home/insurance-intel/insurance-intel/.venv/bin/insurance-intel dry-run

# 8. systemd scharfschalten
sudo cp systemd/insurance-intel.service /etc/systemd/system/
sudo cp systemd/insurance-intel.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now insurance-intel.timer
systemctl list-timers insurance-intel.timer
```

## CLI

```bash
insurance-intel init-db                  # apply migration
insurance-intel run                      # full sweep (default for cron)
insurance-intel dry-run                  # sweep but skip Slack/git
insurance-intel test-source vwheute      # only one source, no Slack/git
```

## Datenquellen
Acht Trade-Press-Publikationen, abgesucht via Nimble-CLI `search` + `extract`.
Quellen sind sauber (keine Anti-Bot-Klauseln). Vermittlerregister.info ist
ausdrücklich ausgeschlossen — ToS § 4 VI b verbietet automatisierte
Datensammlung, siehe RUNBOOK.

## Architektur
Siehe `CLAUDE.md` für die Decision Rules P1-P5 und die Loop-Run-Anweisung.

## Sources of Truth
- LLM-Prompt: `prompts/structure_event.txt`
- Konsolidator-Aliases: `consolidators.yaml`
- Postgres-Schema: `migrations/001_initial.sql`
- CLAUDE.md: Decision Rules für die LLM-Strukturierung

## Lizenz
Privat / CMK Digital. Nicht für externe Nutzung freigegeben.
