# HGraph 距离早停实验复现包

OSPP 2026 项目「VSAG 支持动态搜索能力」在 VSAG 的 HGraph KNN 搜索中加入了可选的距离早停（[antgroup/vsag#3149](https://github.com/antgroup/vsag/pull/3149)）：搜索已经拿到 k 个结果后，如果最近的待展开候选与查询的距离不小于当前第 k 近结果距离的 alpha 倍，就结束这条查询。实验把早停与固定 `ef_search` 基线做比较：对每个数据集、k（10、100）和单查询召回目标 R（0.80、0.90、0.95），基线的 `ef_search` 按校准查询中达到 R 的查询比例不低于给定比例来校准，这一比例称为**校准比例**。本复现包包含两次测量：

- **第一次测量**（2026-11-22 交付）：DBpedia（OpenAI）、Cohere（Wikipedia）、LAION（CLIP）三个百万级数据集，PR head `abe7fcf4` 对照上游 main `7ea909b3`。当时三档原标 C = 0.90 / 0.95 / 0.99，实际按 95% / 97.5% / 99.5% 校准固定 `ef_search`，再要求两组在保留查询上达到 R 的比例都不低于 90% / 95% / 99%（称为**检查门槛**）。文件在 `scripts/`、`frozen/`、`results/`、`report/`。
- **第二次测量**（2026-11-24/25）：十个数据集，在原有三个之外新增 Wiki-all 1M、COCO-I2I、COCO-T2I、Deep 1M、GloVe、SIFT、GIST，PR head `b98e87ab` 对照其上游基线 `4a9c99ba`，分按 99.5% 校准（即第一次测量的最高档，检查门槛 99%）、按 99% 校准、按 95% 校准和按 90% 校准四档。文件在 `more-datasets/`。

两次测量在 FP32 索引上的质量和计时数字都能在这里找到出处：包里有产生这些数字的脚本、冻结的配置、逐查询的质量结果、逐批次的计时记录，以及输入、索引和库文件的 SHA256。向量、索引和逐查询的二进制输出体积太大，两次测量都没有放进来，脚本可以从公开数据重新生成它们。

## 结果

更正：此前的统计把基准的比例标错了。表中标为 90%、95%、99% 的三档，实际对应 95%、97.5%、99.5%。现已改正标注，并补上按 90%、95%、99% 校准的结果。

下表按数据集和校准比例统计早停达标的 (k, R) 点数 / 已评估点数，括号内是达标点覆盖的不同召回目标 R 的个数。alpha 在校准查询上按规则 C（见下文）选出，质量和计时在保留查询上测定。

| 数据集 | 按 99.5% 校准 | 按 99% 校准 | 按 95% 校准 | 按 90% 校准 |
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

一个点算达标，当且仅当早停在保留查询上的平均召回损失不超过 0.5 个百分点，并且在 1 个或 8 个查询线程下满足以下三项之一：QPS 提升不少于 10%、平均延迟降低不少于 10%、P99 延迟降低不少于 10%。这一判据照官方项目页“项目产出要求”第 3 条原文：“固定 efSearch 基线须先校准至目标召回率；在召回率相对基线下降不超过 0.5 个百分点的前提下，自适应方案在至少 3～5 个数据集、多个目标召回率下实现平均延迟或 P99 延迟降低不少于 10%，或 QPS 提升不少于 10%。”把召回损失取为同一查询上固定搜索与早停的召回率之差在查询上的配对平均值，是本复现包的取法，项目页没有写明。按 99%、95%、90% 校准的三档中，规则 C 在保留查询上节省距离计算不足 8% 的点没有计时，按不达标计（三档分别有 15、23、35 个这样的点）。GloVe 和 GIST 在高比例档位上的点数少于 6，是因为有几个点在 `ef_search` 不超过 8192 的已测范围内固定搜索达不到该校准比例。

- 按 99% 校准时，十个数据集中有八个在两个以上召回目标上达标；按 99.5% 校准时有九个（除 COCO-T2I 外全部）；按 95% 校准时有四个（GloVe、GIST、LAION、Cohere）；按 90% 校准时只有 GloVe。
- COCO-T2I 在各档都不达标。按 99.5% 校准时，它的固定 `ef_search` 的距离计算次数是逐查询理想搜索宽度的 2.1 到 8.1 倍（见 `more-datasets/tables/coco-t2i.md` 的差距表），但规则 C 在通过检查的点上只消除了这一差距的 3% 到 10%。
- 按 99% 校准时，DBpedia 在 k = 10 和 k = 100、R = 0.95 两个点上，早停在保留查询上未达到 R 的查询比固定搜索多 5 条和 6 条（共 1,815 条）；Cohere 在 k = 10、R = 0.90 和 0.95 两个点上多 2 条和 5 条（共 601 条）。这些档位不设检查门槛，因此只列出条数，不做通过与否的判定。
- LAION 只有 53 条保留查询，GIST 只有 499 条。按 99.5% 校准时，GIST 的固定搜索自身在所有已评估点上的保留查询达标比例都低于 99%。
- 开启 `early_stop` 而不指定 alpha 时，使用按 k 取的默认值（k = 10 为 1.5，k = 100 为 1.15）。按 99.5% 校准时，它在 COCO-I2I、COCO-T2I 和 SIFT 上节省 0% 到 7% 的距离计算，在 Wiki-all 和 Deep 上最高分别节省 30% 和 21%（都在 R = 0.95；见 `more-datasets/tables/<dataset>.md` 的默认 alpha 小节）。
- P99 延迟变化大多在 10% 以内，只有 LAION（1 线程和 8 线程）以及 COCO-I2I、Deep、SIFT 的少数 8 线程点降低超过 10%。
- 不设置 `early_stop` 的 PR 构建对照上游 main：在 COCO-I2I 的两个点上 QPS 相差 −1.3% 到 +0.2%，在 COCO-T2I 的一个点上为 −2.2% / −1.8%（1 线程 / 8 线程）。
- 第一次测量按 99.5% 校准（检查门槛 99%）一档：在固定基线通过检查门槛的 15 个点上，规则 C 平均节省 38.64% 的距离计算，交付的规则 C+m（加余量）平均节省 27.88%。规则 C 在其中 3 个点上未通过检查（2 个因达标查询比例，1 个因平均召回损失），规则 C+m 在 15 个点上全部通过。第二次测量中，除 GIST 外每个新数据集约有 5,000 条校准查询；按 99.5% 校准（检查门槛 99%）时，不加余量的规则 C 在除 GIST（固定搜索自身未通过检查）外所有新数据集的全部点上都通过检查。

逐点数字见 `more-datasets/tables/headline.md`（以及 `headline.json`，含 `calibration_coverage_target` 和 `check_coverage_target` 两列），各数据集的细表在 `more-datasets/tables/<dataset>.md`。第一次测量的数字见 `report/tables.md`、`report/data/points.csv` 和 `results/quality/REPORT-v4.md`。

## 核对交付的数字

核对只需要 Python 和 [uv](https://docs.astral.sh/uv/)，不用构建 VSAG，也不用下载数据，约 30 秒：

```bash
uv run scripts/check_results.py                 # both measurements
uv run scripts/check_results.py --first-only    # the first measurement only
```

核对过程不运行向量搜索，而是以 `results/` 和 `more-datasets/results/` 中交付的逐查询记录与逐批次记录作为输入；它不验证这些记录是否由搜索产生（那需要索引和库文件，它们的 SHA256 在 `SHA256SUMS` 中）。

逐字节比对的内容：

- 第一次测量：由 `recalibrate.py` 的报告阶段从重算的选参和判定结果重新生成的 `summary-v4.json` 和 `REPORT-v4.md`；在校准结果上重跑得到的 `cv_margin.json` 及其打印表格；由 `make_report_assets.py` 重新生成的 `report/tables.md` 和 `report/data/points.csv`；以及加 `--delivered-labels` 重新生成的这两个文件与 2026-11-22 交付文件的 SHA256（记录在 `checksums/originals.sha256`）比对，用来确认改标只修改了表头说明并新增了列。
- 第二次测量：`more-datasets/results/*.tar.xz` 中的每个归档成员与 `more-datasets/checksums/originals.sha256` 比对；由 `calibrate_ef.py` 在缓存的各已测 `ef_search` 逐查询召回率上重跑得到的每个点的固定 `ef_search`；从逐查询记录重算的规则 C、规则 B 及其逐 alpha 统计、各实验组的保留查询判定、m = 0.25 和 m = 0.10 的规则 C+m 以及汇总文件；从批次记录重算的计时汇总；从缓存的保留查询结果重算的差距（gap）文件；以及 `headline.md`、`headline.json`、各数据集细表（`more-datasets/tables/`）、`points.json` 和 `check.json`。计时计划也会与选参结果核对：每个被计时的规则 C alpha 和固定 `ef_search` 都是选出的值，且每个计划包含的点恰好是通过筛选规则的点。核对脚本还会打印上节的达标点数表。

按解析后的 JSON 值比对（数值、键和列表相同，不计格式差异）：第一次测量的选参结果、保留组和 fresh 的判定结果、规则 C+m 的 alpha，以及 `frozen/configurations.json` 与汇总文件的对照。

按数值容差比对：第一次测量从 952 条批次记录重算的计时中位数与 `timing-summary-v6.json` 比对（容差 1e-9 个百分点）。

不核对的内容：`report/figures/` 中的图（只重新生成，不作比对，因不同机器字体不同）；比对原始搜索输出的记录（`default-check-*.json`、`compare-*.json`）；第一次测量的 `results/fixed-ef/calibration-records.json`；第二次测量的自由 ef（free-ef）组和平均召回（mean-recall）组（它们的选参和保留查询结果按原始记录交付，表格由这些记录重新生成，计时由批次记录重新计算）。

## 第一次测量的设置

**数据。** 三个数据集都来自 Qdrant 基准（[datasets.json](https://github.com/qdrant/vector-db-benchmark/blob/master/datasets/datasets.json)），度量为 cosine。

| 数据集 | 库向量 | 校准查询 | 保留查询 |
|---|---|---:|---:|
| DBpedia（OpenAI 向量） | 975,000 × 1536，FP32 | 1,270 | 1,815 |
| Cohere（Wikipedia） | 999,999 × 768，FP32 | 398 | 601 |
| LAION（CLIP） | 1,000,000 × 512，FP16 按原值转为 FP32 | 395 | 53 |

查询取自各数据集的 `tests.jsonl`，内容相同的查询只保留一条，校准和保留两组在内容上不重叠。具体行号在 `frozen/workloads/<数据集>/rows.json`，代码和文件名里保留组叫 validation。DBpedia 另有 2,048 条新查询（下称 fresh），取自 Hugging Face 上 1M 版 DBpedia OpenAI 数据集末尾不在库向量里的 25,000 行，选取时排除了此前任何查询集用过的行；行号和每行的 SHA256 在 `frozen/workloads/dbpedia/fresh.json`。

**真值与召回。** 真值对实际使用的 FP32 向量做 FP64 cosine 全量扫描，保留前 100，分数相同时按库向量行号排序。召回按距离判定：结果的精确 angular 距离不超过第 k 个真值的距离加 2e-6 就算命中，与 VSAG eval 的 `RecallMonitor` 一致；距离用 VSAG 库中的 AVX-512 内积计算（`native/native_recall.cpp`）。每条查询有自己的 recall@k，一个配置的覆盖率是 recall 达到 R 的查询所占比例。

**索引。** HGraph，FP32 编码，max_degree 32，ef_construction 500，不重排，构建线程 12。LAION 的库向量里有完全相同的向量（最多的一组有 522 条），所以打开 `support_duplicate`，阈值 0.0。创建参数在 `frozen/index/`。

**固定基线。** 每个（数据集、k、R、档位）点的固定 `ef_search`，是校准搜索找到的第一个使校准查询覆盖率（达到 R 的比例）不低于校准比例 C_cal = (1+C)/2 的值；其中 C 是保留查询上的检查门槛（90% / 95% / 99%），三档分别按 95% / 97.5% / 99.5% 校准（原标 C = 0.90 / 0.95 / 0.99），留出一半失败预算作余量。按 99.5% 校准的 18 个点从 ef = k 起倍增至不超过 8192，越过门槛后在整数上二分，每个选出的 `ef_search` 减 1 都已测过且不达标。按 95% 和 97.5% 校准的 36 个点先测网格 round(k · 1.1^i)（上限为同一数据集和 k 下按 99.5% 校准最大 ef 的 1.2 倍），再在第一个达标的网格值和它下面一个网格值之间最多取 24 个等距值细化；其中 9 个点的细化步长为 2 或 3，可能存在小 1 到 2 的达标整数。每次测过的 ef 和达标查询数都在 `results/fixed-ef/calibration-records.json`。

**alpha 的选法。** 在校准查询和固定 ef 下测 55 个 alpha（1.00 到 1.30 步长 0.01，1.32 到 1.60 步长 0.02，1.65 到 1.90 步长 0.05，2.00，以及早期用过的 1.225 和 1.31875）。规则 C 取平均距离计算次数最少的 alpha，条件是它和网格里所有更大的 alpha 都满足两点：覆盖率不低于 C_cal，平均召回损失加两倍标准误不超过 0.5 个百分点（并列时取较大的 alpha）；损失按同一查询上固定搜索与早停的 recall 之差计算。

按 99.5% 校准的 18 个固定基线在校准查询上的达标查询数都恰好位于 ceil(C_cal · n) 的整数下限上，按 95% 和 97.5% 校准的 36 个点中有 6 个高于这一整数下限（见 `results/quality/summary-v4.json` 的 `calibration_fixed.reached`）。第一次保留组检验中，按 99.5% 校准的一档有 3 个点、按 97.5% 校准的一档有 1 个点因早停不达标，于是加了余量：规则 C+m 取不小于 1 + (alpha_C − 1)(1 + m) 的最小网格值，m 在按 95% 和 97.5% 校准两档为 0.05，在按 99.5% 校准一档为 0.25。m 只用校准查询选出：每个点做 300 次 2/3 与 1/3 的随机划分，在 2/3 上用规则 C，在另外 1/3 上检验，按档位对各点的失败概率取平均，取平均值不超过 2.5% 的最小 m（`scripts/cv_margin.py`）。交付的配置用规则 C+m。`ef_search` 不超过 1.25k 时，PR 的实现跳过早停，这 5 个点按固定搜索处理，标记为 auto-off。全部 54 个点的最终配置在 `frozen/configurations.json`。

**保留组验收。** 一个点通过，要求固定基线在保留查询上的覆盖率达到检查门槛 C（90% / 95% / 99%），早停的覆盖率也达到 C，且平均召回损失不超过 0.5 个百分点。保留查询在本轮之前已用于评估早期的 alpha 选择，本轮又看过两次，一次检验规则 C，一次检验规则 C+m，所以它们不是从未接触过的测试集；m 在第二次查看之前确定，之后没有再改。fresh 查询此前只在 k = 100、R = 0.95 一个点上用过。

**计时。** 参照组（ref）是上游 main `7ea909b3` 的固定 ef 搜索，早停组（on）是 PR head `abe7fcf4` 加规则 C+m 的 alpha，共 49 个点。另有两组对照：off 是同一个 PR 库但不写 `early_stop`，测 3 个点；default 写 `early_stop` 但不给 alpha，使用按 k 取的默认值（k = 10 为 1.5，k = 100 为 1.15），测按 99.5% 校准的 18 个点。单线程绑定 CPU 8，8 线程绑定 CPU 8–15。每个批次先把保留查询完整跑一遍预热，再循环 ceil(5000/N) 遍（N 为保留查询数），记录每次查询的延迟和整批的墙钟时间。每组重复 4 个批次，四组的先后顺序轮换。表格里的 QPS、平均延迟和 P99 是 4 个批次的中位数，百分比是中位数之比。计时时后台 CPU 占用超过 2 个核的批次标记为 noisy。只有一次运行超标：LAION k = 100 的 8 线程参照组第 4 次重复，涉及 7 个点；交付表格排除了这 7 条批次记录，这些点的参照组中位数取自其余 3 次。

在 `frozen/` 和 `results/` 中，字段 `C` 是检查门槛，`C_cal` 是校准比例；档位键名 `c90`、`c95`、`c99` 是历史标识。

## 第二次测量的设置

| 数据集 | 库向量 | 度量 | 来源 | 校准 / 保留查询 |
|---|---|---|---|---|
| Wiki-all 1M | 1,000,000 × 768 | squared L2 | RAPIDS `wiki_all_1M.tar` | 5,000 / 5,000 |
| COCO-I2I | 113,287 × 512，FP16 按原值转为 FP32 | cosine | str-encoders v0.1.3 release | 5,000 / 5,000 |
| COCO-T2I | 113,287 × 512，FP16 按原值转为 FP32（图像向量；文本查询） | cosine | str-encoders v0.1.3 release | 4,980 / 4,981 |
| Deep 1M | 前 1,000,000 行 × 96 | cosine | ann-benchmarks `deep-image-96-angular` | 5,000 / 5,000 |
| GloVe | 1,183,514 × 100 | cosine | ann-benchmarks `glove-100-angular` | 5,000 / 5,000 |
| SIFT | 1,000,000 × 128 | squared L2 | ann-benchmarks `sift-128-euclidean` | 4,999 / 5,000 |
| GIST | 1,000,000 × 960 | squared L2 | ann-benchmarks `gist-960-euclidean` | 499 / 499 |
| DBpedia、Cohere、LAION | 同第一次测量（沿用其索引和查询划分） | cosine | | 1,270 / 1,815；398 / 601；395 / 53 |

**新数据集的查询划分。** 取数据文件中的测试查询，FP32 内容完全相同的只保留第一次出现的一条，其余查询用 NumPy `default_rng(20261124)` 随机打乱，前一半（向下取整）作为校准查询，其余作为保留查询。行号和内容哈希记录在 `more-datasets/frozen/inputs/<dataset>/manifest.json.xz`。

**真值与召回。** 与第一次测量相同：在 FP32 库向量上做精确的 FP64 全量扫描，保留前 100，距离相同时按库向量行号排序；cosine 距离为 1 − cos，L2 为平方距离，忽略数据文件自带的近邻。结果的距离用库中的 AVX-512 内核重新计算，不超过第 k 个真值距离加 2e-6 即算命中。

**索引。** HGraph，FP32，`max_degree` 32，`ef_construction` 500，不重排，构建线程 12，用 PR 库构建。新数据集建索引不开 `support_duplicate`；COCO 的库向量有 10 组完全相同的向量（22 行），Wiki-all 有 431 组（957 行）。索引的 SHA256 在 `SHA256SUMS` 中。

**各档的固定基线。** 按 99.5%、99% 和 90% 校准的三档使用上节所述的二分法；按 95% 校准的一档使用网格加细化，新数据集的 42 个点中有 17 个点的细化步长大于 1（最大为 GloVe 的 21），因此选出的 `ef_search` 是已测值中达标的最小值，不一定是最小的达标整数。在 `ef_search` 不超过 8192 的范围内没有达标值的点不作评估（GloVe 和 GIST 在按 99.5% 和 99% 校准两档的部分点）。

**alpha 的选法。** 各档都用上节的规则 C，不加余量；按 99.5% 校准时，各数据集细表还列出了使用第一次测量余量的规则 C+m（m = 0.25，以及六个数据集上的 m = 0.10）。DBpedia、Cohere、LAION 在按 99.5% 和 95% 校准两档沿用第一次测量的 alpha 和保留查询质量结果（库版本 `ef1dd0a5`），只重新计时；在按 99% 和 90% 校准两档，它们的质量结果用 `b98e87ab` 在原始索引上测定。

**保留组检查。** 只有按 99.5% 校准的一档保留第一次测量的检查门槛（99%），其余各档只报告保留查询上的计数，不做通过与否的判定。在这些运行的汇总文件中，`quality_pass` 和 `status` 字段将保留查询覆盖率与内部档位号比较，不对应校准比例，所有表格都不使用这两个字段。

**计时。** 用 PR 构建 `b98e87ab` 加规则 C 的 alpha 对照上游 `4a9c99ba` 的固定 `ef_search`，与上节同样测 1 个和 8 个查询线程，每组 4 个批次。QPS、平均延迟和 P99 的中位数都只取被接受的批次（后台 CPU 占用不超过 2 核），计算相对变化要求每组至少有 2 个被接受的批次。按 99.5% 校准时，所有选出规则 C alpha 的点都计时；其余各档只对距离计算节省不少于 8% 的点计时。每次重复之间轮换两组先后顺序；平均召回（mean-recall）组的 COCO-I2I 运行中，4 次重复里有 3 次是参照组先跑（每条批次记录都带有其顺序位置）。

**单数据集表中的补充对照。** 差距表（gap，只比较固定 `ef_search` 与网格上逐查询理想搜索宽度的距离计算次数，理想组不计时）、成对选参组（pair selection，早停自行选择 `ef_search`，在 COCO-I2I、COCO-T2I、SIFT 上测量）和平均召回组（mean-recall，以平均召回率而非达标查询比例为目标，同样在这三个数据集上测量）。

## 用到的 VSAG 版本

| 用途 | 版本 | 库文件 SHA256 前缀 |
|---|---|---|
| 第一次测量计时的早停组，质量结果的复核 | PR #3149 head `abe7fcf4`（开 PR 时的 head，基于 `7ea909b3`） | `03579555` |
| 第一次测量计时的参照组 | 上游 main `7ea909b3` | `b879b088` |
| 第一次测量的质量结果（alpha 选择、保留组、fresh） | 同一分支此前的本地 head `ef1dd0a5` | `b3f9ab9a` |
| 第一次测量按 95%、97.5% 校准的固定 ef 校准 | 早期实现 `f83e1910` | `30255d4b` |
| 第一次测量按 99.5% 校准的固定 ef 校准、三个索引的构建 | 上游 `44e5b072` 加 PR #2864 的 eval 覆盖率改动 | `b7798718` |
| 第二次测量计时的早停组、质量结果与新索引构建 | PR #3149 head `b98e87ab`（基于 `4a9c99ba`） | `c94bdaa0` |
| 第二次测量计时的参照组 | 上游 main `4a9c99ba` | `b96e265e` |

结果文件沿用原始运行的标签：`v4` 指 `ef1dd0a5`，`v6` 指 `abe7fcf4`。`abe7fcf4` 在全部 3,443 个质量配置上的逐查询输出（工作量、结果 ID、距离）与 `ef1dd0a5` 逐字节相同（`results/quality/compare-v4-v6.json`），不写 alpha 的 108 组搜索与显式写出默认 alpha 的结果逐字节相同（ef 不超过 1.25k 时与固定搜索相同，见 `default-check-v6.json`），所以质量数字同样是 `abe7fcf4` 的结果。固定 ef 是更早校准的，第一次测量用最终的库在这些 ef 上重跑了固定搜索，54 个点的校准覆盖率都不低于 C_cal。PR 之后若再变基，第一次测量的数字对应 `abe7fcf4`，第二次测量的数字对应 `b98e87ab`。

## 交付数字的出处

| 数字 | 文件 | 产生它的脚本 |
|---|---|---|
| 每个点的固定 `ef_search` | `frozen/fixed-points.json`，测试记录在 `results/fixed-ef/calibration-records.json` | `scripts/calibrate_ef.py`（重现两种原始校准过程） |
| 规则 C 和规则 C+m 的 alpha、校准查询上的统计 | `results/quality/v4.tar.xz` 中的 `selection-k*.json`、`selection-cm-k*.json` | `scripts/recalibrate.py alpha`（规则 C）和 `validate-cm`（规则 C+m，余量 m 来自 `scripts/cv_margin.py`） |
| 余量 m 的交叉验证 | `results/margin/cv_margin.json`、`cv_margin.txt` | `scripts/cv_margin.py` |
| 保留组和 fresh 的覆盖率、损失、距离计算节省、通过与否 | `results/quality/summary-v4.json`、`REPORT-v4.md` | `recalibrate.py validate / fresh / validate-cm / fresh-cm / report` |
| QPS、平均延迟、P99 及其变化 | `results/timing/v6/batches.json`、`plan.json` | `recalibrate.py timing`，中位数由 `scripts/make_report_assets.py` 计算 |
| 报告中的表格和图 | `report/tables.md`、`report/data/points.csv`、`report/figures/` | `scripts/make_report_assets.py` |

`v4.tar.xz` 解压后是原始运行的 `quality/v4/<数据集>/` 目录：`calibration-k*.json` 存校准查询上每个 (ef, alpha) 组合的逐查询 recall 和距离计算次数，`validation-k*.json`、`fresh-k*.json` 及其 `-cm` 版本存保留组和 fresh 上的同类数据，其余是选参和判定结果。`REPORT-v4.md` 是第一次测量选参的完整英文报告，除规则 C+m 外还列出规则 C、去掉标准误余量的规则 B、早期 alpha 和默认 alpha 的保留组结果。

第二次测量的结果存放在 `more-datasets/results/<run>.tar.xz` 中（包含逐查询记录、选参结果、保留查询结果、汇总文件、计时批次和计划、固定 `ef_search` 的校准记录与缓存、差距缓存），由 `more-datasets/scripts/` 下的脚本生成（`calibrate_ef.py`、通过 `pipeline.py` 调用的 `recalibrate.py`、`lvl_timing.py`、`orig_timing.py`、`gap.py`、`headline.py`、`tables.py`、`check.py`），生成的表格在 `more-datasets/tables/`。

## 从公开数据重跑第一次测量

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

6. 选 alpha、交叉验证余量 m、检验保留组和 fresh 查询、核对默认 alpha、生成报告，原机器上约 22 分钟。输出在 `work/run/quality/pr/` 和 `work/run/summary-pr.json`、`REPORT-pr.md`。在重建的新图上，应先在校准查询上算出并固定余量 m，再看保留查询：

   ```bash
   uv run scripts/recalibrate.py alpha
   uv run scripts/cv_margin.py work/run/quality/pr work/run/cv_margin.json   # set [selection] margins to the printed m
   for phase in validate fresh validate-cm fresh-cm default-check report; do
     uv run scripts/recalibrate.py $phase
   done
   ```

   `cv_margin.py` 在标准错误里打印每档选出的 m，运行 `validate` 等后续阶段前先把 `config.toml` 中 `[selection]` 的 `margins` 改成打印出的值。`recalibrate.py` 拒绝向已存在的搜索目录写入，因此若要更改选参协议（如换用其他余量或另一个库），需要指定新的运行目录（`RECAL_RUN=work/run2`）。

7. 计时约 1.6 小时，要求机器空闲：1 分钟平均负载不低于 `max_load`（默认 2.0）时脚本拒绝开始，需要强行开始时加 `--force`。

   ```bash
   uv run scripts/recalibrate.py timing
   ```

8. 生成表格和图：

   ```bash
   uv run scripts/make_report_assets.py --timing work/run/timing-results \
       --summary work/run/summary-pr.json --out work/report
   ```

`smoke/run_smoke.py` 用三个各有两万条向量的合成数据集，把第一次测量第 3 步之后的流程完整跑一遍（只覆盖第一次测量的流水线），在原机器上约 3 分钟，适合在正式重跑前检查构建和环境。它用 `work/builds` 下的构建，也可以用 `--pr-build` 等参数指定已有的构建树。

### 重跑结果的对照

重建的索引是不同的图，固定 `ef_search`、选出的 alpha、哪些点达标以及计时结果都会变化，且变化的幅度和方向无法事先限定，不会与交付数字逐位相同。逐位对照需要原始索引（其 SHA256 在 `SHA256SUMS` 中）：在原始索引、相同输入和同一版本编译器构建的 `abe7fcf4` 库上，第 6 步的逐查询输出应与 `checksums/quality-outputs-v4.sha256` 中 3,443 个文件的哈希一致（在 `work/run/quality/pr` 目录下执行 `sha256sum -c`；fresh 和 default-check 的文件也在其中），`summary-pr.json` 应与 `results/quality/summary-v4.json` 的数值一致。计时取决于机器，比较的是早停组相对参照组的变化，而不是 QPS 的绝对值。

## 重跑第二次测量

需要先准备好第一次测量中 DBpedia、Cohere 和 LAION 的输入与索引（上节的 `prepare_inputs.py` 和 `build_indexes.py` 两步），此外还需约 15 GB 下载空间、8.4 GB 的 HDF5 输入、9.2 GB 的索引和约 65 GB 的搜索输出；每个质量搜索进程都会载入完整的索引（各数据集的进程数由配置中的 `processes` 指定）。原始运行在 16 核机器上耗时约 15 小时。

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

输出写入 `work/more-datasets/`（表格在该目录下的 `tables/`）。原始运行的执行顺序与上面不同：各阶段由调度脚本交错执行，在每次计时阶段暂停质量搜索进程。`pipeline.py` 会跳过输出已存在的步骤。原始运行未完成 GIST 和 SIFT 的规则 C+m 计时、Deep 的 m = 0.10 规则 C+m、Deep、GIST 和 Wiki-all 的平均召回（mean-recall）组，以及 GloVe 的差距（gap）计算；这些结果不在交付表格中，完整重跑会将它们补上。

## 目录

| 位置 | 内容 |
|---|---|
| `scripts/` | 第一次测量各阶段的脚本；`config.py` 读取 `config.toml` |
| `native/` | 辅助程序：`multi_signature.cpp` 逐查询记录结果和工作量，`timing.cpp` 计时，`build_index.cpp` 建索引，`native_recall.cpp` 计算召回用的距离 |
| `frozen/` | 第一次测量冻结的配置：选参协议（`protocol.json`，含规则 C+m 的修订记录）、固定 ef 的两份校准协议（`calibration-protocols/`）、固定 ef、最终配置、索引参数、查询行号 |
| `results/` | 第一次测量原始运行的结果：质量（`quality/`）、余量交叉验证（`margin/`）、计时（`timing/`）、固定 ef 的校准记录（`fixed-ef/`） |
| `report/` | 第一次测量结项报告的表格和图 |
| `checksums/` | 第一次测量逐查询二进制输出和计时批次文件的哈希、输入数组的哈希，以及原始文件的哈希（`originals.sha256`） |
| `more-datasets/config.example.toml` | 第二次测量的配置示例：十个数据集、两个库版本、全部校准档位 |
| `more-datasets/scripts/` | 第二次测量的脚本；`config.py` 读取 `more-datasets/config.toml` |
| `more-datasets/native/native_recall.cpp` | 增加了 squared-L2 内核的召回距离计算程序；其余辅助程序沿用 `native/` |
| `more-datasets/frozen/` | 下载地址与 SHA256（`sources.json`）以及七个新数据集的输入清单 |
| `more-datasets/results/` | 逐查询记录、固定 `ef_search` 校准记录与缓存、选参结果、汇总文件、计时批次与计划、差距缓存，按运行目录打包为 `.tar.xz`（共 26 MB） |
| `more-datasets/tables/` | 汇总表和各数据集细表 |
| `more-datasets/checksums/originals.sha256` | 每个归档成员的 SHA256 及其原始路径；其中 `environment.json` 成员里的绝对路径已替换为 `$BENCH` / `$VSAG_ROOT` |
| `provenance/` | 包内脚本与两次运行所用原始脚本的差异（第二次测量在 `provenance/more-datasets/`） |
| `vsag-patches/` | `7ea909b3`..`abe7fcf4` 和 `4a9c99ba`..`b98e87ab` 两份差异，在 GitHub 不再提供 PR 提交时使用 |
| `smoke/` | 合成数据上针对第一次测量流水线的冒烟测试 |

`checksums/originals.sha256` 记录第一次测量的原始文件哈希；包内交付的副本中有 13 个文件因绝对路径被替换为占位符而与原文件不同，另有 `frozen/workloads/dbpedia/fresh.json` 由三个原始文件合并而成。`scripts/recalibrate.py`、`cv_margin.py` 和 `make_report_assets.py` 是产生第一次测量交付数字的原脚本，只把原机器上的路径换成了配置和参数，删去了把库安装进原始运行目录和写入修订记录的阶段，并把保留组判定拆成可单独调用的函数，具体改动见 `provenance/*.diff`。`native/` 下的源文件与原件相同。`prepare_workload.py` 原样取自 VSAG 分支上的提交 `ed372781`，是为 eval 写的公开输入转换；原始输入由更早的脚本从同一批公开文件生成，在原机器上，用它重新转换得到的 7 个查询数组都与原始输入逐字节相同，LAION 的近邻和距离数组也逐字节相同。`calibrate_ef.py` 和 `build_indexes.py` 是新写的。原始的按 99.5% 校准（原标 C = 0.99）和建索引用的是 VSAG 的 `eval_performance`，按 95%、97.5% 校准（原标 C = 0.90、0.95）由另一个脚本完成；这两个新脚本改用与 alpha 阶段相同的辅助程序，按原来的步骤执行（`build_index.cpp` 取自后来一次实验，与原件相同）。在原始 LAION 索引和 `abe7fcf4` 上，`calibrate_ef.py` 对全部 18 个点测过的 ef、每个 ef 下的达标查询数和最终选出的 ef 都与原始记录相同。`results/` 中的文件是原始结果的副本，只把绝对路径换成了 `$BENCH`（原基准目录）和 `$VSAG_ROOT` 两个占位符，并从计时环境记录里删去了当时的进程列表。

第二次测量的脚本取自该次运行自身的目录（`$BENCH/runs/early-stop-more-datasets-20261124/scripts/`），`provenance/more-datasets/<script>.diff` 列出了相对于原始脚本的全部改动：路径改为读取 `more-datasets/config.toml`，不再使用原运行目录和原机器路径；`prepare.py` 读取下载目录并将输出与冻结的清单比对；`gap.py` 和 `calibrate_ef.py` 只在需要运行搜索时才载入真值，且 `gap.py` 只为评估过规则 C 的档位生成行（原始运行的差距文件是在为三个数据集的成对选参组校准 97.5% 固定 `ef_search` 之前生成的）；`headline.py` 和 `tables.py` 按校准比例和检查门槛命名并添加这两个标注列；修正了 `pipeline.py`、`orig_timing.py`、`recalibrate.py` 和 `calibrate_ef.py` 中过时的文档字符串。`build_indexes.py`、`lvl_timing.py`、`freeef_timing.py`、`timing_clean.py` 和 `native_recall.cpp` 未作改动；`build_vsag.py` 是更换了提交号的 `scripts/build_vsag.py`（差异文件相对于后者生成），`download.py` 和 `check_results.py` 是新写的。原始运行的调度脚本（shell 队列和在计时阶段暂停质量搜索进程的门控脚本）未收入包内。2026-11-25 重新标注了 `report/tables.md` 和图的标题，并在 `report/data/points.csv` 中新增 `calibration_coverage_target` 和 `check_coverage_target` 两列，记录的数值未变（`provenance/make_report_assets-labels.diff`）。

## 校验和

`SHA256SUMS` 记录交付数字所依赖的输入和库。`work/data/` 开头的是公开下载的文件（含七个新数据集的下载文件；Wiki-all 压缩包本身的哈希未记录，列出的是其中的两个成员文件），下载后可以逐个核对；`frozen/index/` 是包内的索引参数；`original/` 开头的是原始运行中的 HDF5 输入、索引（含七个新数据集的原始索引 `original/indexes/<dataset>/hgraph.index`）、库和辅助程序（含 `b98e87ab` 和 `4a9c99ba` 的 `original/libraries/pr-b98e87ab/` 与 `ref-4a9c99ba/`），只作身份记录，不对应包里的路径。在本目录执行下面的命令，会核对已经存在的文件：

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

HDF5 输入重新生成后文件字节会不同，应比较数组哈希：第一次测量比对 `checksums/input-arrays.json`（第 3 步会自动比较），新数据集比对各自清单中的数组哈希（`prepare.py` 会自动比较）。

## 许可

本仓库以 Apache License 2.0 发布，见 `LICENSE`，与 VSAG 相同。`vsag-patches/` 中的差异来自 VSAG 的源码，适用同一许可。
