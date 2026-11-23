# Reproduction package: distance early stop for HGraph

This package backs the quality and timing numbers of the OSPP 2026 project "VSAG 支持动态搜索能力" (dynamic search for VSAG), which added an opt-in distance early stop to HGraph KNN search in [antgroup/vsag#3149](https://github.com/antgroup/vsag/pull/3149): once a search holds k results, it ends when the nearest unexpanded candidate is at least alpha times as far from the query as the current k-th result. The early stop is compared with a separately calibrated fixed `ef_search` on DBpedia (OpenAI), Cohere (Wikipedia) and LAION (CLIP) at 1M scale, cosine, k = 10 and 100, per-query recall targets R = 0.80/0.90/0.95, query coverage C = 0.90/0.95/0.99, 1 and 8 threads. The full description is in Chinese in [README.md](README.md); this page lists the commands.

## Check the delivered numbers (Python and uv only, under a minute)

```bash
uv run scripts/check_results.py
```

It recomputes the alpha selection, the held-out and fresh-query verdicts and the cross-validated margin of all 54 points from the per-query results in `results/`, regenerates `summary-v4.json` and `REPORT-v4.md` with the report phase of `recalibrate.py`, recomputes the timing medians from the 952 batch records, regenerates the report tables, and requires byte-for-byte equality with the shipped files.

## Protocol in brief

- Fixed baseline: per (dataset, k, R, C), the smallest `ef_search` whose coverage on the calibration queries reaches C_cal = (1+C)/2.
- Alpha: rule C picks, on the calibration queries at that ef, the alpha with the fewest distance computations such that it and every larger grid alpha keep coverage >= C_cal and mean recall loss + 2 SE <= 0.5 points; rule C+m (delivered) raises it to the smallest grid alpha >= 1 + (alpha_C - 1)(1 + m), m = 0.05 at C = 0.90/0.95 and 0.25 at C = 0.99, m chosen by cross-validation on the calibration queries only. Where ef <= 1.25k the PR skips early stop.
- Held-out check: fixed and early stop both reach C, and the early stop's mean recall loss is at most 0.5 points.
- Timing: upstream main `7ea909b3` fixed ef against PR head `abe7fcf4` with the chosen alpha; 1 thread on CPU 8, 8 threads on CPUs 8-15; four batches per arm in rotating order; medians.

Quality numbers were computed with the PR branch's earlier head `ef1dd0a5` ("v4"); `abe7fcf4` ("v6") reproduces all 3,443 per-query output files byte for byte (`results/quality/compare-v4-v6.json`).

## Rerun from the public data

Needs x86-64 Linux with AVX-512, VSAG's build dependencies, Ninja, zlib headers, about 40 GB of RAM and 60 GB of disk.

```bash
cp config.example.toml config.toml                  # paths and CPU sets
uv run scripts/build_vsag.py --jobs 16              # abe7fcf4 and 7ea909b3, Release, plus helpers
uv run scripts/download.py                          # Qdrant archives and one HF parquet shard, SHA256-checked
uv run scripts/prepare_inputs.py                    # HDF5 inputs, exact ground truth, array hashes compared
uv run scripts/build_indexes.py                     # HGraph FP32, max_degree 32, ef_construction 500
uv run scripts/calibrate_ef.py                      # then set [selection] fixed_points = "work/run/fixed-points.json"
for phase in alpha validate fresh validate-cm fresh-cm default-check report; do
  uv run scripts/recalibrate.py $phase
done
uv run scripts/cv_margin.py work/run/quality/pr work/run/cv_margin.json
uv run scripts/recalibrate.py timing                # about 1.6 h on a quiet machine
uv run scripts/make_report_assets.py --timing work/run/timing-results --summary work/run/summary-pr.json --out work/report
```

A rebuilt index is a different graph, so the fixed ef values, alphas and savings will move slightly; exact agreement needs the original index files, whose SHA256 are in `SHA256SUMS`. `smoke/run_smoke.py` runs the whole pipeline after the download on small synthetic data in about five minutes.

## License

Apache License 2.0, the same as VSAG; see `LICENSE`. The diff in `vsag-patches/` is derived from VSAG source and is under the same license.
