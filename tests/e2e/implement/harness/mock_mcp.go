package harness

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
)

// StartMockMCP starts a local HTTP server that serves Jira issue JSON from
// fixtures/{s.ID}/stories/{key}.json. The server URL should be passed to
// claude via the JIRA_MCP_URL environment variable.
//
// The server is automatically shut down via t.Cleanup when the test ends.
func StartMockMCP(t T, s Scenario) *httptest.Server {
	t.Helper()
	storiesDir := filepath.Join(fixturesRoot(), s.ID, "stories")

	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		// Accept paths like /jira/issue/EDM-3895 or /issue/EDM-3895 or /EDM-3895
		parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
		key := parts[len(parts)-1]

		data, err := os.ReadFile(filepath.Join(storiesDir, key+".json"))
		if err != nil {
			http.Error(w, "issue not found: "+key, http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(data)
	})

	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv
}
