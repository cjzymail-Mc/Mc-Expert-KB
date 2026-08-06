# HASH_PARITY.md — docx-shared-core baseline (2026-08-06, rework re-pin)

> Per-file SHA-256 baseline for the docx-shared-core scripts.
> Re-pinned after B-001 (build_docx fail-protect) + B-002 (report.py import/exit_code + verify wiring) + C_non_unique_anchor matrix case. B-003 (2026-08-06): run_matrix.py +3 cases (file_probe direct probe + verify BLOCKED negatives) + doc sync. B-004 (2026-08-06): report.py MD sync (exit_code/exit_code_contract/contract_path); manifest restructured to staging_root/target_master_root. B-005 (2026-08-06): run_matrix.py determinism conclusion honesty fix; C1 §1/§8 dangling ref + overclaim fix.
| file | sha256 |
|---|---|
| scripts/file_probe.py | 078fc882e3e26df2592848da1b84942ebac08e5805ae6db60b450c5c9f52d417 |
| scripts/resolve_core.py | 6acf5e1adf78e96e25eea4dca37da859704f4370e984d40e4f0b7bffc2831d0e |
| scripts/build_docx.py | 2cc4adcbca0bf70d65885f4cf812acf6e1c5baa803bdff4cb596ebb5025450e2 |
| scripts/verify_docx.py | 7d1f4a243a3c867d184b69fe38e461c1e34a58420af986423768ecc083c57931 |
| scripts/inspect_template.py | 4a599d28c03a73dd7bbefc686d22cc15297bb823d57ae6af9f69ed2389d9e9be |
| scripts/report.py | 43a9cfcd714093944e4bd99002419049f37fd22ec93206f8f938b103e6634fc7 |
| run_matrix.py | b9f19ae40c8fa6ef429fc9765a1b85dd7c2fad175df8d3c6b9844ef3da89a343 |
| quick_validate.py | 1fd9ce76de2eae2e7ad088fbccc22697a589970ad4bc36829211faabda5c7da7 |
| fixtures/make_fixtures.py | a0060e6dc95d3d8001e48ca2947eba15d3d72ae61b1a1cd355a8ae2f61b8e3fb |

