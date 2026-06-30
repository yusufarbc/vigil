package api

import (
	"encoding/json"
	"net/http"
)

// Handler returns the BFF's HTTP mux.
// In Phase 1 only /healthz is exposed. Phase 7 adds analyst triage endpoints.
func Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", healthz)
	return mux
}

func healthz(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"}) //nolint:errcheck
}
