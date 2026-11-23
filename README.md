# HGraph 距离早停实验复现包

OSPP 2026 项目「VSAG 支持动态搜索能力」在 VSAG 的 HGraph KNN 搜索中加入了可选的距离早停（[antgroup/vsag#3149](https://github.com/antgroup/vsag/pull/3149)）：搜索已经拿到 k 个结果后，如果最近的待展开候选与查询的距离不小于当前第 k 近结果距离的 alpha 倍，就结束这条查询。结项报告把它与单独校准的固定 `ef_search` 基线做了比较，范围是 DBpedia、Cohere、LAION 三个公开的百万级数据集，k = 10 和 100，召回目标 R = 0.80、0.90、0.95，覆盖率 C = 0.90、0.95、0.99，单线程和 8 线程。

报告中 FP32 索引上的质量和计时数字都能在这里找到出处：包里有产生这些数字的脚本、冻结的配置、逐查询的质量结果、逐批次的计时记录，以及输入、索引和库文件的 SHA256。向量、索引和逐查询的二进制输出体积太大，没有放进来，脚本可以从公开数据重新生成它们。

## 先核对交付的数字

核对只需要 Python 和 [uv](https://docs.astral.sh/uv/)，不用构建 VSAG，也不用下载数据，运行不到一分钟：

```bash
uv run scripts/check_results.py
```

它从 `results/` 里的逐查询结果重新计算全部 54 个 (数据集, k, R, C) 点的 alpha 选择、保留查询上的质量判定和交叉验证得到的余量，再用 `recalibrate.py` 的报告阶段生成 `summary-v4.json` 和 `REPORT-v4.md`；计时部分从 952 条批次记录重算中位数，最后重新生成报告用的表格。所有结果都要与包里的文件逐字节一致，任何一项不一致都会以非零状态退出。

## 实验设置

**数据。** 三个数据集都来自 Qdrant 基准（[datasets.json](https://github.com/qdrant/vector-db-benchmark/blob/master/datasets/datasets.json)），度量为 cosine。

| 数据集 | 库向量 | 校准查询 | 保留查询 |
|---|---|---:|---:|
| DBpedia（OpenAI 向量） | 975,000 × 1536，FP32 | 1,270 | 1,815 |
| Cohere（Wikipedia） | 999,999 × 768，FP32 | 398 | 601 |
| LAION（CLIP） | 1,000,000 × 512，FP16 按原值转为 FP32 | 395 | 53 |

查询取自各数据集的 `tests.jsonl`，内容相同的查询只保留一条，校准和保留两组在内容上不重叠。具体行号在 `frozen/workloads/<数据集>/rows.json`，代码和文件名里保留组叫 validation。DBpedia 另有 2,048 条新查询（下称 fresh），取自 Hugging Face 上 1M 版 DBpedia OpenAI 数据集末尾不在库向量里的 25,000 行，选取时排除了此前任何查询集用过的行；行号和每行的 SHA256 在 `frozen/workloads/dbpedia/fresh.json`。

**真值与召回。** 真值对实际使用的 FP32 向量做 FP64 cosine 全量扫描，保留前 100，分数相同时按库向量行号排序。召回按距离判定：结果的精确 angular 距离不超过第 k 个真值的距离加 2e-6 就算命中，与 VSAG eval 的 `RecallMonitor` 一致；距离用 VSAG 库中的 AVX-512 内积计算（`native/native_recall.cpp`）。每条查询有自己的 recall@k，一个配置的覆盖率是 recall 达到 R 的查询所占比例。

**索引。** HGraph，FP32 编码，max_degree 32，ef_construction 500，不重排，构建线程 12。LAION 的库向量里有完全相同的向量（最多的一组有 522 条），所以打开 `support_duplicate`，阈值 0.0。创建参数在 `frozen/index/`。

**固定基线。** 每个点的固定 `ef_search` 是在校准查询上覆盖率达到 C_cal = (1+C)/2 的最小 ef，也就是 C = 0.99 时按 0.995 校准，留出一半失败预算作余量。C = 0.99 的 18 个点从 ef = k 起倍增，越过门槛后在整数上二分，最终 ef 减 1 都已测过且不达标。C = 0.90、0.95 的 36 个点先测网格 round(k · 1.1^i)（上限为同一数据集和 k 下 C = 0.99 最大 ef 的 1.2 倍），再在第一个达标的网格值和它下面一个网格值之间最多取 24 个等距值细化；其中 9 个点的细化步长为 2 或 3，真正的最小整数可能还要小 1 到 2。每次测过的 ef 和达标查询数都在 `results/fixed-ef/calibration-records.json`。

**alpha 的选法。** 在校准查询和固定 ef 下测 55 个 alpha（1.00 到 1.30 步长 0.01，1.32 到 1.60 步长 0.02，1.65 到 1.90 步长 0.05，2.00，以及早期用过的 1.225 和 1.31875）。规则 C 取平均距离计算次数最少的 alpha，条件是它和网格里所有更大的 alpha 都满足两点：覆盖率不低于 C_cal，平均召回损失加两倍标准误不超过 0.5 个百分点；损失按同一查询上固定搜索与早停的 recall 之差计算。

规则 C 没有给覆盖率留余量：校准查询上的固定 ef 恰好卡在 C_cal，规则 C 选出的 alpha 只是碰巧没有在校准查询上新增失败。第一次保留组检验中，C = 0.99 有 3 个点、C = 0.95 有 1 个点因早停不达标，于是加了余量：规则 C+m 取不小于 1 + (alpha_C − 1)(1 + m) 的最小网格值，m 在 C = 0.90、0.95 时为 0.05，在 C = 0.99 时为 0.25。m 只用校准查询选出：每个点做 300 次 2/3 与 1/3 的随机划分，在 2/3 上用规则 C，在另外 1/3 上检验，按 C 档对各点的失败概率取平均，取平均值不超过 2.5% 的最小 m（`scripts/cv_margin.py`）。交付的配置用规则 C+m。`ef_search` 不超过 1.25k 时，PR 的实现跳过早停，这 5 个点按固定搜索处理，标记为 auto-off。全部 54 个点的最终配置在 `frozen/configurations.json`。

**保留组验收。** 一个点通过，要求固定基线在保留查询上的覆盖率达到 C，早停的覆盖率也达到 C，且平均召回损失不超过 0.5 个百分点。保留查询在本轮之前已用于评估早期的 alpha 选择，本轮又看过两次，一次检验规则 C，一次检验规则 C+m，所以它们不是从未接触过的测试集；m 在第二次查看之前确定，之后没有再改。fresh 查询此前只在 k = 100、R = 0.95 一个点上用过。

**计时。** 参照组（ref）是上游 main `7ea909b3` 的固定 ef 搜索，早停组（on）是 PR head `abe7fcf4` 加规则 C+m 的 alpha，共 49 个点。另有两组对照：off 是同一个 PR 库但不写 `early_stop`，测 3 个点；default 写 `early_stop` 但不给 alpha，使用按 k 取的默认值（k = 10 为 1.5，k = 100 为 1.15），测 C = 0.99 的 18 个点。单线程绑定 CPU 8，8 线程绑定 CPU 8–15。每个批次先把保留查询完整跑一遍预热，再循环 ceil(5000/N) 遍（N 为保留查询数），记录每次查询的延迟和整批的墙钟时间。每组重复 4 个批次，四组的先后顺序轮换。表格里的 QPS、平均延迟和 P99 是 4 个批次的中位数，百分比是中位数之比。计时时后台 CPU 占用超过 2 个核的批次标记为 noisy。只有一次运行超标：LAION k = 100 的 8 线程参照组第 4 次重复，涉及 7 个点；交付表格排除了这 7 条批次记录，这些点的参照组中位数取自其余 3 次。

## 用到的 VSAG 版本

| 用途 | 版本 | 库文件 SHA256 前缀 |
|---|---|---|
| 计时的早停组，质量结果的复核 | PR #3149 head `abe7fcf4`（开 PR 时的 head，基于 `7ea909b3`） | `03579555` |
| 计时的参照组 | 上游 main `7ea909b3` | `b879b088` |
| 质量结果（alpha 选择、保留组、fresh） | 同一分支此前的本地 head `ef1dd0a5` | `b3f9ab9a` |
| C = 0.90、0.95 的固定 ef 校准 | 早期实现 `f83e1910` | `30255d4b` |
| C = 0.99 的固定 ef 校准、三个索引的构建 | 上游 `44e5b072` 加 PR #2864 的 eval 覆盖率改动 | `b7798718` |

结果文件沿用原始运行的标签：`v4` 指 `ef1dd0a5`，`v6` 指 `abe7fcf4`。`abe7fcf4` 在全部 3,443 个质量配置上的逐查询输出（工作量、结果 ID、距离）与 `ef1dd0a5` 逐字节相同（`results/quality/compare-v4-v6.json`），不写 alpha 的 108 组搜索与显式写出默认 alpha 的结果逐字节相同（ef 不超过 1.25k 时与固定搜索相同，见 `default-check-v6.json`），所以质量数字同样是 `abe7fcf4` 的结果。固定 ef 是更早校准的，本轮用最终的库在这些 ef 上重跑了固定搜索，54 个点的校准覆盖率都不低于 C_cal。PR 之后若再变基，本包的数字仍然只对应 `abe7fcf4`。

## 交付数字的出处

| 数字 | 文件 | 产生它的脚本 |
|---|---|---|
| 每个点的固定 `ef_search` | `frozen/fixed-points.json`，测试记录在 `results/fixed-ef/calibration-records.json` | `scripts/calibrate_ef.py`（重现两种原始校准过程） |
| 规则 C 和规则 C+m 的 alpha、校准查询上的统计 | `results/quality/v4.tar.xz` 中的 `selection-k*.json`、`selection-cm-k*.json` | `scripts/recalibrate.py alpha`（规则 C）和 `validate-cm`（规则 C+m，余量 m 来自 `scripts/cv_margin.py`） |
| 余量 m 的交叉验证 | `results/margin/cv_margin.json`、`cv_margin.txt` | `scripts/cv_margin.py` |
| 保留组和 fresh 的覆盖率、损失、距离计算节省、通过与否 | `results/quality/summary-v4.json`、`REPORT-v4.md` | `recalibrate.py validate / fresh / validate-cm / fresh-cm / report` |
| QPS、平均延迟、P99 及其变化 | `results/timing/v6/batches.json`、`plan.json` | `recalibrate.py timing`，中位数由 `scripts/make_report_assets.py` 计算 |
| 报告中的表格和图 | `report/tables.md`、`report/data/points.csv`、`report/figures/` | `scripts/make_report_assets.py` |

`v4.tar.xz` 解压后是原始运行的 `quality/v4/<数据集>/` 目录：`calibration-k*.json` 存校准查询上每个 (ef, alpha) 组合的逐查询 recall 和距离计算次数，`validation-k*.json`、`fresh-k*.json` 及其 `-cm` 版本存保留组和 fresh 上的同类数据，其余是选参和判定结果。`REPORT-v4.md` 是本轮选参的完整英文报告，除规则 C+m 外还列出规则 C、去掉标准误余量的规则 B、早期 alpha 和默认 alpha 的保留组结果。

## 从公开数据重跑

### 环境

原始运行的机器是 AMD Ryzen 9 9950X（16 核 32 线程）、93 GB 内存、Ubuntu 24.04、GCC 13.3、CMake 3.28，VSAG 用 Release 构建（`-O3`，自带的 OpenBLAS）。重跑需要：

- x86-64 Linux，CPU 支持 AVX-512。召回计算直接调用 VSAG 的 AVX-512 内积，没有 AVX-512 的机器会因非法指令退出。
- VSAG 的构建依赖，见其 `DEVELOPMENT.md`；Ubuntu 可在 VSAG 源码树里运行 `sudo env VSAG_INSTALL_INTEL_MKL=OFF bash scripts/deps/install_deps_ubuntu.sh`。另需 Ninja、zlib 开发文件（`zlib1g-dev`；装在别处时用 `LIBRARY_PATH` 指过去）、git、curl 和 uv。
- 内存：DBpedia 的质量阶段同时开 5 个搜索进程，每个载入 6.3 GB 的索引，连同召回计算载入的库向量约需 40 GB；可在 `config.toml` 里减少进程数。DBpedia 的真值计算要 12 GB 的 FP64 副本。
- 磁盘约 60 GB：压缩包 9.6 GB，解压后的向量 10 GB，HDF5 输入 11 GB，索引 11.5 GB，两棵构建树约 10 GB，搜索输出约 3 GB。解压后加 `--remove-archives` 可以删掉压缩包。
- 默认的 CPU 分配按 32 个逻辑 CPU 设置：质量阶段用 0–7 和 16–23，计时用 8–15，建索引用 0–11。

### 步骤

以下命令都在本目录执行。先复制配置文件，按机器修改路径和 CPU：

```bash
cp config.example.toml config.toml
```

1. 构建 VSAG。脚本克隆 VSAG，在 `work/builds/pr` 和 `work/builds/upstream` 分别检出 `abe7fcf4` 和 `7ea909b3`，按原始构建的 CMake 选项编译 `vsag` 和 `hdf5` 两个目标，再编译 `native/` 下的辅助程序。PR 分支以后若被改写，GitHub 不再提供 `abe7fcf4` 时，脚本在 `7ea909b3` 上应用 `vsag-patches/pr3149-abe7fcf4.diff`，并核对结果与 `abe7fcf4` 的 tree（`f91ed741`）一致。构建中最慢的是自带的 OpenBLAS，每棵构建树单线程编译约 20 分钟。

   ```bash
   uv run scripts/build_vsag.py --jobs 16
   ```

2. 下载数据并核对 SHA256（共 9.6 GB）：

   ```bash
   uv run scripts/download.py
   ```

3. 生成 HDF5 输入和真值，约 10 分钟。脚本最后把每个查询、近邻和距离数组的哈希与原始输入（`checksums/input-arrays.json`）比较。查询数组必须一致；真值来自 FP64 矩阵乘法，换一个 BLAS 可能让最后一位舍入不同、使几乎并列的近邻换序，这种情况只报告不中止。

   ```bash
   uv run scripts/prepare_inputs.py
   ```

4. 建索引，原始构建分别用了 857 秒（DBpedia）、293 秒（Cohere）和 234 秒（LAION）。HGraph 多线程构建，图不是逐字节可复现的，新索引的 SHA256 不会等于原始值。

   ```bash
   uv run scripts/build_indexes.py
   ```

5. 在新索引上校准固定 ef，约半小时。结果写到 `work/run/fixed-points.json`，测试记录的格式与 `results/fixed-ef/calibration-records.json` 相同。之后把 `config.toml` 中 `[selection]` 的 `fixed_points` 改成 `"work/run/fixed-points.json"`。如果拿到了原始索引（在 `[datasets.<数据集>]` 里用 `index` 指定），可以跳过这一步，直接用冻结的 ef。

   ```bash
   uv run scripts/calibrate_ef.py
   ```

6. 选 alpha、检验保留组和 fresh 查询、核对默认 alpha、生成报告，原机器上约 22 分钟。输出在 `work/run/quality/pr/` 和 `work/run/summary-pr.json`、`REPORT-pr.md`。

   ```bash
   for phase in alpha validate fresh validate-cm fresh-cm default-check report; do
     uv run scripts/recalibrate.py $phase
   done
   uv run scripts/cv_margin.py work/run/quality/pr work/run/cv_margin.json
   ```

   `cv_margin.py` 在标准错误里打印每档 C 选出的 m。若与配置里的余量不同，按新值修改 `config.toml` 的 `margins` 后从 `validate-cm` 起重跑。

7. 计时约 1.6 小时，要求机器空闲：1 分钟平均负载不低于 `max_load`（默认 2.0）时脚本拒绝开始，需要强行开始时加 `--force`。

   ```bash
   uv run scripts/recalibrate.py timing
   ```

8. 生成表格和图：

   ```bash
   uv run scripts/make_report_assets.py --timing work/run/timing-results \
       --summary work/run/summary-pr.json --out work/report
   ```

`smoke/run_smoke.py` 用三个各有两万条向量的合成数据集，把第 3 步之后的流程完整跑一遍，约 5 分钟，适合在正式重跑前检查构建和环境。它用 `work/builds` 下的构建，也可以用 `--pr-build` 等参数指定已有的构建树。

### 重跑结果怎样对照

重建的索引是不同的图，固定 ef 会有小幅变化，alpha、覆盖率和距离计算节省随之变化，不会与交付数字逐位相同。逐位对照需要原始索引：在原始索引、相同输入和同一版本编译器构建的 `abe7fcf4` 库上，第 6 步的逐查询输出应与 `checksums/quality-outputs-v4.sha256` 中 3,443 个文件的哈希一致（在 `work/run/quality/pr` 目录下执行 `sha256sum -c`；fresh 和 default-check 的文件也在其中），`summary-pr.json` 应与 `results/quality/summary-v4.json` 的数值一致。计时取决于机器，比较的是早停组相对参照组的变化，而不是 QPS 的绝对值。

## 目录

| 位置 | 内容 |
|---|---|
| `scripts/` | 各阶段的脚本；`config.py` 读取 `config.toml` |
| `native/` | 辅助程序：`multi_signature.cpp` 逐查询记录结果和工作量，`timing.cpp` 计时，`build_index.cpp` 建索引，`native_recall.cpp` 计算召回用的距离 |
| `frozen/` | 冻结的配置：选参协议（`protocol.json`，含规则 C+m 的修订记录）、固定 ef 的两份校准协议（`calibration-protocols/`）、固定 ef、最终配置、索引参数、查询行号 |
| `results/` | 原始运行的结果：质量（`quality/`）、余量交叉验证（`margin/`）、计时（`timing/`）、固定 ef 的校准记录（`fixed-ef/`） |
| `report/` | 结项报告的表格和图 |
| `checksums/` | 逐查询二进制输出和计时批次文件的哈希、输入数组的哈希，以及包内各文件对应的原始文件及其哈希（`originals.sha256`） |
| `provenance/` | 包内脚本与原始脚本的差异 |
| `vsag-patches/` | `7ea909b3` 到 `abe7fcf4` 的完整差异 |
| `smoke/` | 合成数据上的冒烟测试 |

`scripts/recalibrate.py`、`cv_margin.py` 和 `make_report_assets.py` 是产生交付数字的原脚本，只把原机器上的路径换成了配置和参数，删去了把库安装进原始运行目录和写入修订记录的阶段，并把保留组判定拆成可单独调用的函数，具体改动见 `provenance/*.diff`。`native/` 下的源文件与原件相同。`prepare_workload.py` 原样取自 VSAG 分支上的提交 `ed372781`，是为 eval 工具写的公开输入转换；原始输入由更早的脚本从同一批公开文件生成，在原机器上，用它重新转换得到的 7 个查询数组都与原始输入逐字节相同，LAION 的近邻和距离数组也逐字节相同。`calibrate_ef.py` 和 `build_indexes.py` 是新写的。原始的 C = 0.99 校准和建索引用的是 VSAG 的 `eval_performance`，C = 0.90、0.95 的校准由另一个脚本完成；这两个新脚本改用与 alpha 阶段相同的辅助程序，按原来的步骤执行（`build_index.cpp` 取自后来一次实验，与原件相同）。在原始 LAION 索引和 `abe7fcf4` 上，`calibrate_ef.py` 对全部 18 个点测过的 ef、每个 ef 下的达标查询数和最终选出的 ef 都与原始记录相同。`results/` 中的文件是原始结果的副本，只把绝对路径换成了 `$BENCH`（原基准目录）和 `$VSAG_ROOT` 两个占位符，并从计时环境记录里删去了当时的进程列表。

## 校验和

`SHA256SUMS` 记录交付数字所依赖的输入和库。`work/data/` 开头的是公开下载的文件，下载后可以逐个核对；`frozen/index/` 是包内的索引参数；`original/` 开头的是原始运行中的 HDF5 输入、索引、库和辅助程序，只作身份记录，不对应包里的路径。在本目录执行下面的命令，会核对已经存在的文件：

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

HDF5 输入重新生成后文件字节会不同，应比较数组哈希（`checksums/input-arrays.json`，第 3 步会自动比较）。

## 许可

本仓库以 Apache License 2.0 发布，见 `LICENSE`，与 VSAG 相同。`vsag-patches/` 中的差异来自 VSAG 的源码，适用同一许可。
