package harness

// T is the subset of testing.TB methods used by the harness.
// It is satisfied by both *testing.T and ginkgo.GinkgoTInterface,
// avoiding the private-method restriction on testing.TB.
type T interface {
	Helper()
	Fatalf(format string, args ...any)
	Fatal(args ...any)
	Errorf(format string, args ...any)
	Error(args ...any)
	Logf(format string, args ...any)
	Log(args ...any)
	TempDir() string
	Cleanup(func())
}
