# Reproduction package: distance early stop for HGraph

This package backs the quality and timing numbers of the OSPP 2026 project "VSAG 支持动态搜索能力" (dynamic search for VSAG), which added an opt-in distance early stop to HGraph KNN search in [antgroup/vsag#3149](https://github.com/antgroup/vsag/pull/3149): once a search holds k results, it ends when the nearest unexpanded candidate is at least alpha times as far from the query as the current k-th result. The early stop is compared with a fixed `ef_search` baseline. For each dataset, k (10, 100) and per-query recall target R (0.80, 0.90, 0.95), the baseline's `ef_search` is calibrated so that a given share of the calibration queries reaches R; this share is the *calibration level*. The package holds two measurements:

- **First measurement** (delivered 2026-11-22): DBpedia (OpenAI), Cohere (Wikipedia) and LAION (CLIP) at 1M scale, PR head `abe7fcf4` against upstream main `7ea909b3`. Its three tiers were labelled C = 0.90 / 0.95 / 0.99. They calibrated the fixed `ef_search` at 95% / 97.5% / 99.5%, and then required both arms to reach R on at least 90% / 95% / 99% of the held-out queries (the *check-set gate*). Files: `scripts/`, `frozen/`, `results/`, `report/`.
- **Second measurement** (2026-11-24/25): ten datasets, the three above plus Wiki-all 1M, COCO-I2I, COCO-T2I, Deep 1M, GloVe, SIFT and GIST, PR head `b98e87ab` against its upstream base `4a9c99ba`, at calibration levels 99.5% (the first measurement's top tier, check-set gate 99%), 99%, 95% and 90%. Files: `more-datasets/`.

The Chinese [README.md](README.md) describes the first measurement in more detail.

## Results

Correction: earlier tables mislabelled the calibration level of the fixed baseline. The tiers labelled 90%, 95% and 99% were calibrated at 95%, 97.5% and 99.5%. The labels are corrected here, and results calibrated at 90%, 95% and 99% are added.

The table counts, per dataset and calibration level, the (k, R) points at which the early stop meets the requirement, out of the points evaluated; the number of distinct R among the points that meet it is in parentheses. Alpha is chosen by rule C (below) on the calibration queries; quality and timing come from the held-out queries.

| Dataset | Calibrated at 99.5% | 99% | 95% | 90% |
|---|---|---|---|---|
| Wiki-all 1M | 6/6 (3) | 6/6 (3) | 0/6 | 0/6 |
| COCO-I2I | 4/6 (3) | 4/6 (3) | 1/6 (1) | 0/6 |
| COCO-T2I | 0/6 | 0/6 | 0/6 | 0/6 |
| DBpedia | 6/6 (3) | 3/6 (2) | 1/6 (1) | 1/6 (1) |
| Cohere | 5/6 (3) | 5/6 (3) | 2/6 (2) | 0/6 |
| LAION | 5/6 (3) | 4/6 (2) | 3/6 (2) | 1/6 (1) |
| Deep 1M | 5/6 (3) | 5/6 (3) | 1/6 (1) | 0/6 |
| GloVe | 4/4 (2) | 5/5 (3) | 6/6 (3) | 6/6 (3) |
| GIST | 5/5 (3) | 4/5 (3) | 4/6 (3) | 1/6 (1) |
| SIFT | 3/6 (3) | 1/6 (1) | 0/6 | 0/6 |

A point meets the requirement when the early stop's mean recall loss on the held-out queries is at most 0.5 percentage points and at least one of these holds at 1 or 8 query threads: QPS up by at least 10%, mean latency down by at least 10%, P99 latency down by at least 10%. This follows item 3 of the project page's output requirements (a fixed `efSearch` baseline calibrated to the target recall; recall at most 0.5 points below it; a 10% gain in mean or P99 latency or QPS on several datasets and recall targets). Taking the loss as the mean over queries of the paired difference (fixed recall minus early-stop recall on the same query) is our reading; the project page does not specify it. At the 99%, 95% and 90% levels, points where rule C saves less than 8% of the distance computations on the held-out queries were not timed and count as not meeting the requirement (15, 23 and 35 such points). GloVe and GIST have fewer points at the strict levels because fixed search reaches the level at no tested `ef_search` up to 8192 there.

- At 99%, eight of the ten datasets meet the requirement at two or more recall targets; at 99.5%, nine (all but COCO-T2I); at 95%, four (GloVe, GIST, LAION, Cohere); at 90%, GloVe alone.
- COCO-T2I meets it at no level. Its fixed `ef_search` does 2.1 to 8.1 times the distance computations of a per-query ideal width at 99.5% (`more-datasets/tables/coco-t2i.md`, gap table), but rule C removes only 3% to 10% of that difference where it passes its check.
- At 99%, the early stop leaves 5 and 6 more held-out queries below R than fixed search at DBpedia k = 10 and k = 100, R = 0.95 (out of 1,815), and 2 and 5 more at Cohere k = 10, R = 0.90 and 0.95 (out of 601). These levels have no check-set gate, so the counts are reported, not judged.
- LAION has 53 held-out queries and GIST 499. At 99.5%, GIST's fixed search itself reaches R on fewer than 99% of its held-out queries at every evaluated point.
- `early_stop` without alpha uses a default by k (1.5 at k = 10, 1.15 at k = 100). At 99.5% it saves 0% to 7% of the distance computations on COCO-I2I, COCO-T2I and SIFT, and at most 30% (Wiki-all) and 21% (Deep), both at R = 0.95 (`more-datasets/tables/<dataset>.md`, default alpha section).
- P99 latency mostly stays within 10%. It falls by more than 10% at LAION (1 and 8 threads) and at a few 8-thread points of COCO-I2I, Deep and SIFT.
- The PR build without `early_stop` against upstream main: QPS −1.3% to +0.2% at two COCO-I2I points and −2.2% / −1.8% (1 / 8 threads) at one COCO-T2I point.
- First measurement, calibrated at 99.5% with the 99% gate: on the 15 points whose fixed baseline passes the gate, rule C saves 38.64% of the distance computations on average and rule C+m (the delivered rule, with margin) 27.88%. Rule C fails the check at 3 of them (two by coverage, one by mean loss); rule C+m passes all 15. In the second measurement, with about 5,000 calibration queries per new dataset, rule C without margin passes the 99.5%/99% check at every point of the new datasets except GIST, where fixed search itself fails.

Per-point numbers: `more-datasets/tables/headline.md` (and `headline.json`, with columns `calibration_coverage_target` and `check_coverage_target`), per-dataset detail in `more-datasets/tables/<dataset>.md`. First measurement: `report/tables.md`, `report/data/points.csv`, `results/quality/REPORT-v4.md`.

## Check the shipped numbers (Python and uv only, about 30 seconds)

```bash
uv run scripts/check_results.py                 # both measurements
uv run scripts/check_results.py --first-only    # the first measurement only
```

No search runs. The per-query and per-batch records shipped in `results/` and `more-datasets/results/` are the inputs of the check; it does not confirm that they came from the searches, which would need the indexes and libraries (their SHA256 are in `SHA256SUMS`).

Compared byte for byte:

- First measurement: `summary-v4.json` and `REPORT-v4.md` regenerated by the report phase of `recalibrate.py` from the recomputed selections and verdicts; `cv_margin.json` and its printed table, rerun on the calibration results; `report/tables.md` and `report/data/points.csv`, regenerated by `make_report_assets.py`; the same two files regenerated with `--delivered-labels` against the SHA256 of the files delivered on 2026-11-22 (`checksums/originals.sha256`), which shows that relabelling changed captions and added columns only.
- Second measurement: every member of `more-datasets/results/*.tar.xz` against `more-datasets/checksums/originals.sha256`; the fixed `ef_search` of every point, rerun by `calibrate_ef.py` on the cached per-query recalls of every tested `ef_search`; rule C, rule B and their per-alpha statistics, the held-out verdicts of every arm, rule C+m with m = 0.25 and m = 0.10, and the summaries, from the per-query records; the timing summaries, from the batch records; the gap files, from the cached held-out results; `headline.md`, `headline.json`, the per-dataset tables, `points.json` and `check.json`. The timing plans are also checked against the selections: every timed rule C alpha and fixed `ef_search` is the selected one, and each plan holds exactly the points its screen admits. The check prints the counts of the table above.

Compared as decoded JSON values (the same numbers, keys and lists, regardless of formatting): the first measurement's selections, held-out and fresh verdicts and rule C+m alphas, and `frozen/configurations.json` against the summary.

Compared within a numerical tolerance: the first measurement's timing medians, recomputed from 952 batch records, against `timing-summary-v6.json` (1e-9 percentage points).

Not checked: the figures in `report/figures/` (regenerated, not compared; fonts differ between machines); the records that compare raw search outputs (`default-check-*.json`, `compare-*.json`); the first measurement's `results/fixed-ef/calibration-records.json`; the free-ef and mean-recall arms of the second measurement (their selections and held-out results are shipped as recorded; their tables are regenerated from those records and their timing from the batches).

## Protocol of the first measurement

- Fixed baseline: per (dataset, k, R, tier), the first `ef_search` found by the calibration search whose coverage on the calibration queries (the share reaching R) is at least the calibration level C_cal = (1+C)/2, that is 95% / 97.5% / 99.5%. At 99.5% the search doubles from k up to 8192, then bisects on integers; the `ef_search` one below each selected value was tested and fails. At 95% and 97.5% it tests the grid round(k · 1.1^i) and then at most 24 equal steps between the first passing grid value and the one below; at 9 of these 36 points the step was 2 or 3, so a passing integer up to 2 lower may exist. All 18 fixed baselines at 99.5% sit exactly on the integer minimum of passing calibration queries; at 95% and 97.5% six exceed it. Tested values and counts: `results/fixed-ef/calibration-records.json`.
- Alpha: rule C picks, on the calibration queries at that `ef_search`, the grid alpha with the fewest mean distance computations such that it and every larger grid alpha keep coverage at least C_cal and mean recall loss plus two standard errors at most 0.5 points; ties go to the larger alpha. Rule C+m, the delivered rule, raises it to the smallest grid alpha at least 1 + (alpha_C − 1)(1 + m), with m = 0.05 at the 95% and 97.5% levels and 0.25 at 99.5%. The margin was introduced after the first look at the held-out queries, where rule C failed at 3 points of the 99.5% tier and 1 of the 97.5% tier; the value of m was then chosen by cross-validation on the calibration queries alone (`scripts/cv_margin.py`) and the same held-out queries were checked again. Where `ef_search` <= 1.25k the PR skips early stop (5 points).
- Held-out check: fixed search and early stop both reach R on at least C (90% / 95% / 99%) of the held-out queries, and the early stop's mean recall loss is at most 0.5 points. The held-out queries share no content with the calibration queries, but they had been used to evaluate earlier alpha choices before this protocol.
- Timing: upstream main `7ea909b3` at the fixed `ef_search` against PR head `abe7fcf4` with the chosen alpha; 1 query thread on CPU 8 and 8 query threads on CPUs 8-15, each thread issuing one query per call; four batches per arm in rotating order; medians, and changes as ratios of medians. The 7 batch records flagged for background CPU use above 2 cores are excluded from the delivered tables.

Quality numbers were computed with the PR branch's earlier head `ef1dd0a5` ("v4"); `abe7fcf4` ("v6") reproduces all 3,443 per-query output files byte for byte (`results/quality/compare-v4-v6.json`). In `frozen/` and `results/`, the field `C` is the check-set gate and `C_cal` the calibration level; the tier keys (`c90`, `c95`, `c99`) are historical identifiers.

## Protocol of the second measurement

| Dataset | Base | Metric | Source | Calibration / held-out queries |
|---|---|---|---|---|
| Wiki-all 1M | 1,000,000 × 768 | squared L2 | RAPIDS `wiki_all_1M.tar` | 5,000 / 5,000 |
| COCO-I2I | 113,287 × 512, FP16 widened to FP32 | cosine | str-encoders v0.1.3 release | 5,000 / 5,000 |
| COCO-T2I | 113,287 × 512, FP16 widened to FP32 (image vectors; text queries) | cosine | str-encoders v0.1.3 release | 4,980 / 4,981 |
| Deep 1M | first 1,000,000 rows × 96 | cosine | ann-benchmarks `deep-image-96-angular` | 5,000 / 5,000 |
| GloVe | 1,183,514 × 100 | cosine | ann-benchmarks `glove-100-angular` | 5,000 / 5,000 |
| SIFT | 1,000,000 × 128 | squared L2 | ann-benchmarks `sift-128-euclidean` | 4,999 / 5,000 |
| GIST | 1,000,000 × 960 | squared L2 | ann-benchmarks `gist-960-euclidean` | 499 / 499 |
| DBpedia, Cohere, LAION | as in the first measurement (its indexes and query roles) | cosine | | 1,270 / 1,815; 398 / 601; 395 / 53 |

- Queries of a new dataset: the file's test queries; identical FP32 contents keep their first occurrence; the rest are permuted with NumPy `default_rng(20261124)`, the first half (floor) is for calibration and the rest is held out. Rows and content hashes are in `more-datasets/frozen/inputs/<dataset>/manifest.json.xz`.
- Ground truth: exact FP64 scan over the FP32 base, top 100, ties by base row; cosine distance 1 − cos, L2 as squared distance. The files' own neighbours are ignored. Recall counts a result when its distance, recomputed with the library's AVX-512 kernel, is at most the k-th true distance plus 2e-6.
- Index: HGraph, FP32, `max_degree` 32, `ef_construction` 500, no reorder, 12 build threads, built with the PR library. The new datasets are built without `support_duplicate`; COCO's base has 10 groups of identical vectors (22 rows) and Wiki-all's 431 (957 rows). Index SHA256 are in `SHA256SUMS`.
- Fixed baseline per level: at 99.5%, 99% and 90%, the bisection described above; at 95%, the grid with refinement, where the refinement step exceeded 1 at 17 of the 42 points of the new datasets (up to 21, at GloVe), so the chosen `ef_search` is the smallest passing value tested, not necessarily the smallest passing integer. Points with no passing `ef_search` up to 8192 are not evaluated (GloVe and GIST, at 99.5% and 99%).
- Alpha: rule C as above, without margin, at every level; at 99.5% the per-dataset tables also give rule C+m with the first measurement's margins (m = 0.25, and m = 0.10 for six datasets). For DBpedia, Cohere and LAION at 99.5% and 95%, the alphas and held-out quality are the first measurement's (library `ef1dd0a5`); only their timing is new. At 99% and 90% their quality was measured on the original indexes with `b98e87ab`.
- Check: only the 99.5% level keeps the first measurement's check-set gate (99%). The other levels report held-out counts without a verdict. In the summaries of those runs, the fields `quality_pass` and `status` compare held-out coverage with the internal tier number (0.98, 0.90, 0.80), not with a level; no table uses them.
- Timing: PR build `b98e87ab` with the rule C alpha against upstream `4a9c99ba` at the fixed `ef_search`, 1 and 8 query threads as above, four batches per arm. Medians use accepted batches only (background CPU use at most 2 cores), for QPS, mean latency and P99 alike; a change needs at least two accepted batches per arm. At 99.5% every point with a rule C alpha was timed; at the other levels only points saving at least 8% of the distance computations. The arm order rotates between repeats; in the mean-recall arm's COCO-I2I run the reference arm went first in 3 of 4 repeats (each batch record carries its position).
- Supplementary arms in the per-dataset tables: gap (fixed `ef_search` against a per-query ideal width on a grid, in distance computations only; no ideal arm was timed), pair selection (early stop choosing its own `ef_search`, COCO-I2I, COCO-T2I, SIFT), and a mean-recall arm (targets on mean recall instead of coverage, same three datasets). The internal tier numbers 0.99, 0.98, 0.90, 0.80 name the levels 99.5%, 99%, 95%, 90% in file names and JSON keys.

## Rerun the first measurement from the public data

Needs x86-64 Linux with AVX-512, VSAG's build dependencies, Ninja, zlib headers (or `LIBRARY_PATH` pointing at a `libz`), about 40 GB of RAM and 60 GB of disk.

```bash
cp config.example.toml config.toml                  # paths and CPU sets
uv run scripts/build_vsag.py --jobs 16              # abe7fcf4 and 7ea909b3, Release, plus helpers
uv run scripts/download.py                          # Qdrant archives and one HF parquet shard, SHA256-checked
uv run scripts/prepare_inputs.py                    # HDF5 inputs, exact ground truth, array hashes compared
uv run scripts/build_indexes.py                     # HGraph FP32, max_degree 32, ef_construction 500
uv run scripts/calibrate_ef.py                      # then set [selection] fixed_points = "work/run/fixed-points.json"
uv run scripts/recalibrate.py alpha
uv run scripts/cv_margin.py work/run/quality/pr work/run/cv_margin.json   # set [selection] margins to the printed m
for phase in validate fresh validate-cm fresh-cm default-check report; do
  uv run scripts/recalibrate.py $phase
done
uv run scripts/recalibrate.py timing                # about 1.6 h on a quiet machine
uv run scripts/make_report_assets.py --timing work/run/timing-results --summary work/run/summary-pr.json --out work/report
```

On a new graph, compute and fix the margins before looking at the held-out queries, as above. A rebuilt index is a different graph, so the fixed `ef_search`, the alphas, which points pass and the timing can all change, by amounts no one can bound in advance; exact agreement needs the original index files, whose SHA256 are in `SHA256SUMS`. `recalibrate.py` refuses to write into an existing search folder, so a changed protocol (other margins, another library) needs a new run directory (`RECAL_RUN=work/run2`). `smoke/run_smoke.py` runs this pipeline after the download on small synthetic data in a few minutes.

## Rerun the second measurement

Needs the first measurement's inputs and indexes of DBpedia, Cohere and LAION (steps `prepare_inputs.py` and `build_indexes.py` above), about 15 GB more of downloads, 8.4 GB of HDF5 inputs, 9.2 GB of indexes and about 65 GB of search outputs; each quality process loads a whole index (`processes` per dataset in the config). The original run took about 15 hours on a 16-core machine.

```bash
cp more-datasets/config.example.toml more-datasets/config.toml
uv run more-datasets/scripts/build_vsag.py --jobs 16       # b98e87ab and 4a9c99ba, Release, plus helpers
uv run more-datasets/scripts/download.py                   # seven datasets, SHA256-checked
NEW="coco-i2i coco-t2i wiki-all sift deep glove gist"; ORIG="dbpedia cohere laion"
uv run more-datasets/scripts/prepare.py $NEW               # inputs; compared with the frozen manifests
uv run more-datasets/scripts/build_indexes.py $NEW
P="uv run more-datasets/scripts/pipeline.py"
for ds in $NEW; do $P c99-quality $ds; $P lvl-quality $ds; $P l95-quality $ds; done
for ds in $ORIG; do $P lvl-quality $ds; done
# timing, one stage at a time on a quiet machine (no quality stage running)
for ds in $NEW; do $P c99r-timing $ds; $P lvl99-timing $ds; $P lvl90-timing $ds; $P l95-timing $ds; done
for ds in $ORIG; do $P orig-timing $ds; $P o95-timing $ds; $P lvl99-timing $ds; $P lvl90-timing $ds; done
for ds in coco-i2i coco-t2i; do $P c99-timing $ds; done     # rule C+m, m = 0.10, PR without early_stop, default alpha
for ds in coco-i2i coco-t2i wiki-all sift deep gist $ORIG; do $P gap $ds; done
for ds in coco-i2i coco-t2i sift; do $P mr-quality $ds; $P free-quality $ds; $P mr-timing $ds; $P free-timing $ds; done
uv run more-datasets/scripts/headline.py
uv run more-datasets/scripts/tables.py $NEW $ORIG
uv run more-datasets/scripts/check.py                      # expected rows, missing timing, cross-run consistency
```

Outputs go to `work/more-datasets/` (`tables/` there). The original run's order differed: stages were interleaved by a scheduler that paused quality processes during each timing stage. `pipeline.py` skips a step whose output exists. The run did not complete rule C+m timing for GIST and SIFT, rule C+m with m = 0.10 for Deep, the mean-recall arm for Deep, GIST and Wiki-all, or the gap for GloVe; those results are absent from the tables, and a complete rerun adds them.

## Layout

| Path | Contents |
|---|---|
| `scripts/`, `native/`, `frozen/`, `results/`, `report/`, `checksums/` | First measurement: scripts, helper sources, frozen configuration, per-query and per-batch records, report tables and figures, hashes of the original files and outputs |
| `more-datasets/config.example.toml` | Second measurement: ten datasets, both libraries, all levels |
| `more-datasets/scripts/` | Its scripts; `config.py` reads `more-datasets/config.toml` |
| `more-datasets/native/native_recall.cpp` | The recall helper with an added squared-L2 kernel; the other helpers are those in `native/` |
| `more-datasets/frozen/` | Download sources with SHA256 (`sources.json`) and the input manifests of the seven new datasets |
| `more-datasets/results/` | Per-query records, fixed-`ef_search` calibration records and caches, selections, summaries, timing batches and plans, gap caches, as `.tar.xz` per run directory (26 MB) |
| `more-datasets/tables/` | Headline and per-dataset tables |
| `more-datasets/checksums/originals.sha256` | SHA256 of every archive member and its original path; `environment.json` members had absolute paths replaced by `$BENCH` / `$VSAG_ROOT` |
| `provenance/` | Differences between the shipped scripts and the scripts the runs used (`more-datasets/` for the second measurement) |
| `vsag-patches/` | `7ea909b3`..`abe7fcf4` and `4a9c99ba`..`b98e87ab`, used when GitHub no longer serves a PR commit |
| `smoke/` | Smoke test of the first measurement's pipeline on synthetic data |

`checksums/originals.sha256` records the first measurement's original files; 13 shipped copies differ from them because absolute paths were replaced by placeholders, and `frozen/workloads/dbpedia/fresh.json` combines three originals. The second measurement's scripts are the run's own (`$BENCH/runs/early-stop-more-datasets-20261124/scripts/`), and `provenance/more-datasets/<script>.diff` lists every change against them: paths come from `more-datasets/config.toml` instead of the run directory and this machine; `prepare.py` reads the download directory and compares its output with the frozen manifests; `gap.py` and `calibrate_ef.py` load ground truth only when a search has to run, and `gap.py` gives rows only to levels whose rule C was evaluated (the run's gap files were made before a 97.5% fixed `ef_search` was calibrated for three datasets, for the pair-selection arm); `headline.py` and `tables.py` name calibration levels and check-set gates and add the two label columns; stale docstrings of `pipeline.py`, `orig_timing.py`, `recalibrate.py` and `calibrate_ef.py` are corrected. `build_indexes.py`, `lvl_timing.py`, `freeef_timing.py`, `timing_clean.py` and `native_recall.cpp` are unchanged; `build_vsag.py` is `scripts/build_vsag.py` with the new commits (diff against it), and `download.py` and `check_results.py` are new. The run's scheduler scripts (shell queues and a timing gate that paused quality processes) are not shipped. On 2026-11-25 the captions of `report/tables.md` and the figures were relabelled and `report/data/points.csv` gained the columns `calibration_coverage_target` and `check_coverage_target`; the recorded values are unchanged (`provenance/make_report_assets-labels.diff`).

## License

Apache License 2.0, the same as VSAG; see `LICENSE`. The diffs in `vsag-patches/` are derived from VSAG source and are under the same license.
