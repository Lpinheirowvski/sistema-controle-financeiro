# Implementation validation

Checks performed on 16 November 2026 against **MySQL 8.0.46**. These are observed local results; GitHub Actions status is reported separately by GitHub.

## Existing project review

Reviewed every originally tracked file before editing: `README.md`, `.gitignore`, `01_estrutura.sql`, `02_dados.sql`, `03_relatorios.sql`, and `relatorio_financeiro.csv`. The repository contained five example transactions and no Python application or automated tests. The report selected the misspelled database `coontrole_financeiro`.

The existing `financeiro-mysql` container used `--network none` and persistent external storage. It was started and backed up before migration. Its network and source records were preserved. A new Compose database received a copy through `docker exec`, without connecting the legacy container to a network.

## Verification by stage

| Stage | Observed result |
| --- | --- |
| Input validation | 16 tests passed |
| Unit analytics, configuration and exports | 21 tests passed |
| Schema, migration, CRUD, SQL analytics, constraints | 28 total tests passed on real MySQL |
| Streamlit filters, create, edit and delete | 29 total tests passed on real MySQL |
| Backup failure, concurrent initialization, duplicate legacy values | **32 total tests passed** using the final Compose test service |

Final complete command:

```bash
docker compose --profile test run --rm tests
# 32 passed in 6.91s
```

The complete suite includes 21 unit tests and 11 integration tests. The integration fixtures create and clean up only uniquely named databases on the separate test server. All statements in `03_relatorios.sql` were executed by MySQL, rather than validated with SQLite or SQL mocks.

Additional successful checks:

- `ruff check .`, `ruff format --check .`, and `git diff --check`.
- Main Compose configuration and Dev Container Compose configuration validation.
- Production Docker image build, container startup, and Streamlit health endpoint.
- Runtime account reads all 245 transactions; an attempted schema creation is denied.
- CLI CSV/Excel report generation against the running application database.
- Repeated initialization reports zero imported and zero seeded rows; total remains 245.
- Concurrent initializers import five records and seed 240 records in total, without duplicates.

## Data preservation and financial reconciliation

The original source and staged source were compared field by field and matched exactly, including IDs, descriptions, types, amounts, and dates.

| Measure | Observed result |
| --- | ---: |
| Original source rows, before and after migration | 5 |
| Original source amount total | R$ 5,800.00 |
| Imported legacy rows | 5 |
| Imported income | R$ 4,250.00 |
| Imported expenses | R$ 1,550.00 |
| Imported net cash flow | R$ 2,700.00 |
| Fictitious rows | 240 |
| Fictitious rows per calendar month, Jan–Dec 2026 | 20 |
| Combined transaction count | 245 |
| Combined income | R$ 105,608.00 |
| Combined expenses | R$ 45,758.00 |
| Combined net cash flow | R$ 59,850.00 |

Tests also reconcile exact `0.10 + 0.20 - 0.07 = 0.23` results between Python and SQL, verify an empty February between January and March, and confirm that previous-month comparisons use February's zero balance. Deleted demo transactions stay deleted after initialization. Duplicate business values with distinct legacy IDs are preserved as distinct records.

Legacy migration JSON snapshots were verified to contain all source rows with file permissions `0600`. A simulated backup failure prevents importing data. Invalid legacy money aborts the transaction and leaves the source untouched.

## Browser verification and screenshots

Headless Chromium, controlled through Playwright, rendered the actual running application at 1600 × 1600 and 390 × 1000. No Streamlit exceptions were displayed, and the mobile document had no horizontal overflow. The screenshots in `docs/screenshots/` are real captures of that application with the 245-record dataset.

CSV and Excel files were downloaded through the browser buttons and reopened. The CSV contained 245 records. The workbook contained 245 transaction records and 12 monthly summary rows, in separate worksheets. Export tests verify spreadsheet formula escaping and preservation of monetary values.

## Environment findings and limits

- The host could not reach the isolated test database IP. Running the Python tests inside its internal Docker network resolved this without publishing MySQL ports.
- The managed environment required its trusted proxy CA during Docker dependency installation. The build succeeded using a temporary BuildKit secret, with TLS verification enabled. The CA is not copied into image layers.
- The first startup exposed a permissions problem in the runtime-user initialization script. Its executable/read permissions were corrected; runtime CRUD access and denial of schema changes were then verified.
- The first remote CI run passed all 32 tests but its startup check found test database variables overriding the application configuration. Test credentials were scoped to the pytest step so the Compose application uses its own generated credentials.
- Dev Container service profiles were validated after adding an explicit development override. The VS Code graphical attachment itself was not exercised.
- The application intentionally has no authentication, multi-currency accounting, account/category editing UI, or background scheduler. Reporting loads the selected ledger into memory.
- The SQL monthly view uses MySQL's default recursive CTE limit. Very long histories need a higher session limit, as documented in the README.
- No changes were merged into `main`. The migration does not synchronize subsequent v2 edits back into the frozen legacy source.
