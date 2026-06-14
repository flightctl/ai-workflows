// mock_gh is a drop-in replacement for the `gh` CLI binary used during e2e tests.
// It intercepts the calls that the implement skill's publish phase makes and
// records pr create invocations to pr-record.json in the current working directory.
// All other calls return empty JSON and exit 0.
//
// Built to fixtures/bin/gh by SynchronizedBeforeSuite before any spec runs.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

func main() {
	args := os.Args[1:]

	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "mock gh: no arguments")
		os.Exit(1)
	}

	switch {
	case isCall(args, "auth", "status"):
		handleAuthStatus()
	case isCall(args, "repo", "view"):
		handleRepoView()
	case isCall(args, "pr", "create"):
		handlePRCreate(args)
	case isCall(args, "pr", "view"):
		handlePRView(args)
	default:
		fmt.Println("{}")
	}
}

// isCall returns true when args starts with the given subcommand words.
func isCall(args []string, words ...string) bool {
	if len(args) < len(words) {
		return false
	}
	for i, w := range words {
		if args[i] != w {
			return false
		}
	}
	return true
}

func handleAuthStatus() {
	fmt.Println("github.com")
	fmt.Println("  ✓ Logged in to github.com account e2e-test (keyring)")
	fmt.Println("  - Active account: true")
	fmt.Println("  - Git operations protocol: https")
	fmt.Println("  - Token: gho_****")
	fmt.Println("  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'")
}

func handleRepoView() {
	fmt.Println(`{"isFork":false,"parent":null}`)
}

func handlePRView(args []string) {
	fmt.Println(`{"number":9999,"url":"https://github.com/flightctl/flightctl/pull/9999","state":"OPEN"}`)
}

func handlePRCreate(args []string) {
	record := map[string]string{
		"number": "9999",
		"url":    "https://github.com/flightctl/flightctl/pull/9999",
	}

	// Parse flags: --title, --body, --base, --head, --draft
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--title", "-t":
			if i+1 < len(args) {
				record["title"] = args[i+1]
				i++
			}
		case "--body", "-b":
			if i+1 < len(args) {
				record["body"] = args[i+1]
				i++
			}
		case "--body-file":
			if i+1 < len(args) {
				record["body_file"] = args[i+1]
				i++
			}
		case "--base", "-B":
			if i+1 < len(args) {
				record["base"] = args[i+1]
				i++
			}
		case "--head", "-H":
			if i+1 < len(args) {
				record["head"] = args[i+1]
				i++
			}
		case "--draft", "-d":
			record["draft"] = "true"
		case "--repo", "-R":
			if i+1 < len(args) {
				record["repo"] = args[i+1]
				i++
			}
		}
	}

	// Derive branch from head if present, otherwise from git
	if _, ok := record["head"]; !ok {
		if branch := currentBranch(); branch != "" {
			record["head"] = branch
		}
	}

	data, _ := json.MarshalIndent(record, "", "  ")
	if err := os.WriteFile("pr-record.json", data, 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "mock gh: write pr-record.json: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(record["url"])
}

func currentBranch() string {
	data, err := os.ReadFile(".git/HEAD")
	if err != nil {
		return ""
	}
	line := strings.TrimSpace(string(data))
	const prefix = "ref: refs/heads/"
	if strings.HasPrefix(line, prefix) {
		return strings.TrimPrefix(line, prefix)
	}
	return ""
}
