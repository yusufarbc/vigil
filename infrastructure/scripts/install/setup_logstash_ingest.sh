#!/usr/bin/env bash
set -euo pipefail

### ======== USER CONFIGURATION (modify if needed) ========
ES_URL="${ES_URL:-https://localhost:9200}"
CA_CERT="${CA_CERT:-/etc/logstash/certs/ca.crt}"       # fallback to /etc/elasticsearch/certs/ca.crt
ELASTIC_USER="${ELASTIC_USER:-elastic}"                # ES admin user
ELASTIC_PW="${ELASTIC_PW:-}"                           # if empty, script will prompt (hidden)
ROLE_NAME="${ROLE_NAME:-logstash_windows_writer}"
LS_USER="${LS_USER:-logstash_ingest}"
LS_PW="${LS_PW:-}"                                     # if empty, auto-generated
DATASTREAM_NAME="${DATASTREAM_NAME:-logs-windows-default}"

# Logstash configuration paths
LS_SETTINGS="/etc/logstash"
LS_KEYSTORE="$LS_SETTINGS/logstash.keystore"

### ======== PRELIMINARY CHECKS ========
require_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "[ERR] '$1' not found"; exit 1; }; }
require_cmd curl
require_cmd jq || echo "[WARN] 'jq' not available; JSON output will be plain."

# Try Elasticsearch CA if Logstash CA doesn't exist
if [[ ! -f "$CA_CERT" ]]; then
  if [[ -f /etc/elasticsearch/certs/ca.crt ]]; then
    CA_CERT="/etc/elasticsearch/certs/ca.crt"
  fi
fi
if [[ ! -f "$CA_CERT" ]]; then
  echo "[ERR] CA certificate not found: $CA_CERT"
  echo "      Set CA_CERT variable to point to the correct path."
  exit 1
fi

if [[ -z "$ELASTIC_PW" ]]; then
  read -s -p "Elastic ($ELASTIC_USER) password: " ELASTIC_PW
  echo
fi

# Auto-generate LS_PW if not provided
if [[ -z "$LS_PW" ]]; then
  if command -v openssl >/dev/null 2>&1; then
    LS_PW="$(openssl rand -base64 24)"
  else
    LS_PW="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)"
  fi
  AUTO_GEN=1
else
  AUTO_GEN=0
fi

### ======== HELPER FUNCTIONS ========
api_put() { # $1 path, $2 json body
  curl -sS -u "$ELASTIC_USER:$ELASTIC_PW" --cacert "$CA_CERT" \
       -H 'Content-Type: application/json' -X PUT "$ES_URL$1" -d "$2"
}
api_post() { # $1 path, $2 json body
  curl -sS -u "$ELASTIC_USER:$ELASTIC_PW" --cacert "$CA_CERT" \
       -H 'Content-Type: application/json' -X POST "$ES_URL$1" -d "$2"
}
api_get() { # $1 path
  curl -sS -u "$ELASTIC_USER:$ELASTIC_PW" --cacert "$CA_CERT" "$ES_URL$1"
}

### ======== TEST ELASTICSEARCH CONNECTIVITY ========
echo "[*] Testing Elasticsearch connection: $ES_URL"
api_get "/_security/_authenticate" >/dev/null
echo "[OK] Elasticsearch access successful."

### ======== CREATE/UPDATE ROLE: write to logs-windows-default data stream ========
echo "[*] Creating/updating role: $ROLE_NAME"
ROLE_BODY=$(cat <<JSON
{
  "indices": [
    {
      "names": ["$DATASTREAM_NAME"],
      "privileges": ["auto_configure", "create_doc", "write"]
    }
  ]
}
JSON
)
api_put "/_security/role/$ROLE_NAME" "$ROLE_BODY" >/dev/null
echo "[OK] Role ready: $ROLE_NAME (names: [$DATASTREAM_NAME])"

### ======== CREATE/UPDATE USER: logstash_ingest ========
echo "[*] Creating/updating user: $LS_USER"
USER_BODY=$(cat <<JSON
{
  "password": "$LS_PW",
  "roles": ["$ROLE_NAME"],
  "enabled": true
}
JSON
)
# Idempotent create/update user with PUT
api_put "/_security/user/$LS_USER" "$USER_BODY" >/dev/null
echo "[OK] User ready: $LS_USER (role: $ROLE_NAME)"
if [[ "$AUTO_GEN" -eq 1 ]]; then
  echo "[INFO] Auto-generated password for ${LS_USER}: $LS_PW"
fi

### ======== LOGSTASH KEYSTORE ========
echo "[*] Preparing Logstash keystore: $LS_KEYSTORE"
sudo /usr/share/logstash/bin/logstash-keystore --path.settings "$LS_SETTINGS" create >/dev/null 2>&1 || true

# Add ES_PW non-interactively using --stdin
echo -n "$LS_PW" | sudo /usr/share/logstash/bin/logstash-keystore --path.settings "$LS_SETTINGS" add ES_PW --stdin
sudo chown logstash:logstash "$LS_KEYSTORE"
sudo chmod 600 "$LS_KEYSTORE"
echo "[OK] Keystore updated: ES_PW added."

### ======== QUICK TEST AND SERVICE ========
echo "[*] Testing Logstash configuration:"
sudo /usr/share/logstash/bin/logstash -t --path.settings "$LS_SETTINGS" || { echo "[ERR] Logstash config test FAILED"; exit 1; }

echo "[*] Restarting Logstash..."
sudo systemctl restart logstash

echo "[*] Logstash status:"
sudo systemctl --no-pager -l status logstash | sed -n '1,12p'

echo "[*] Checking port 5045 listener:"
sudo ss -ltnp | grep -E ':(5045)\b' || echo "[WARN] Port 5045 not visible; check beats input configuration."

echo "[DONE] Process completed."
