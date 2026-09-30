# Named sFlow transfer in Grafana, September 30, 2026

The source test and raw records are in the sibling blog-sandbox repository's
`telemetry/evidence/sflow-useful-20260930/`. Two completed 256 MiB transfers
passed byte-count and SHA-256 checks. The enriched repeat used TCP destination
port 47933 and produced an exact forward sample from DCA-Leaf02.

`transfer/grafana-transfer-query.json` records the actual Grafana datasource
response for that transfer's time window. It contains both server names,
their original addresses and ports, the exporter identity, sampling rate and
one observed sample. `transfer/browser-transfer.json` verifies the filtered
dashboard received the named data without JavaScript or query errors.
`transfer/named-sflow-transfer.png` captures the rendered table and raw record.

The browser check caught a scalar-variable quoting problem: the JSON formatter
left the port regex unquoted in the VictoriaLogs plugin's actual request. The
dashboard now uses the doublequote formatter, verified in the rendered view.
An API-only substitution test did not catch that discrepancy. The browser's
table rendering also required checking its data response and screenshot rather
than treating cell values as visible DOM text locators.

`panel-checks-final.json` and `panel-checks-port-filter.json` contain 68 successful
backend checks across All, CE1, DCA-Leaf01 and CE2. The earlier `panel-checks.json`
and `panel-checks-current.json` retain the initial overly strict expectation
that CE1 must have syslog events in every 24-hour window. The verifier now
reports a quiet syslog window without treating it as a query failure or proof
of current sender delivery. It still fails datasource errors.

Ownership comes from a reviewed Nautobot snapshot, not a live API call per
sample. Raw IP fields remain intact, unknown/ambiguous addresses are not
guessed, and older records are not backfilled. The destination-port filter
applies only to the two conversation tables and raw flow detail; SNMP, syslog
and SuzieQ remain independent views.
