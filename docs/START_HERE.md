# FYP preparation and baseline checkpoint — 8 November 2026

The active project is `C:\NUS\FYP\FYP Organized`.

**Start with the integrated explanation:** [From Sensor Data to an Exploratory Baseline](../reports/fyp_integrated_2026-11-08/FYP_Data_Preparation_to_Baseline_Report_2026-11-08.pdf) explains the research aim, full-source data, preparation decisions, provisional targets, Dinh/Muller/Quinsat relevance, baseline results, tomography-tool assessment and next steps in plain language. This is the current self-contained reader's report.

**Latest progress:** source preparation is now complete for all 64 fatigue specimens over the 142 nominal gauge layers (519–660). This produced 329,828 standardized sensor patches. Read the [source-cleaning summary](../reports/data_cleaning/source_preparation_v1/report.md) and [prepared-data catalog](../data/cleaned/snow_source_preparation_v1/catalog/README.md) for the current dataset. Candidate targets remain explicitly unvalidated; 6,548 are unknown because the XCT intensity proxy is insufficient.

**Baseline v1 is now complete:** 42 image-only descriptors, four development validation folds on 52 specimens, and a reserved test set of 12 specimens. Development-selected random forest test AP is 0.7822 versus 0.2515 for the dummy. This pooled result hides weak within-specimen discrimination (mean per-specimen ROC AUC 0.5761; zero recall on P57 and P65 at threshold 0.5). Read the [model workflow](../src/modeling/README.md), [result summary](../reports/baseline_v1_2026-11-08/report.md) and [results PDF](../reports/baseline_v1_2026-11-08/FYP_Baseline_v1_Results_2026-11-08.pdf). These are provisional annotation-prediction results, not validated physical-defect performance.

Read the [audit report](../reports/data_cleaning/2026-11-08_run01/report.md) first. The automated audit reproduces all 2,024 pilot rows but does not establish final scientific labels. Six patches depend on crop-boundary policy and one additional NIR channel needs review. All original labels and feature arrays were preserved.

- [Scientific questions for review](../results/data_quality/2026-11-08_run01/sources/supervisor_questions.md) — a draft only; nothing was sent.
- [Provisional review dataset](../data/review/2026-11-08_run01/README.md) — unchanged arrays with extra flags and provenance.
- [Data dictionary](../reports/data_cleaning/2026-11-08_run01/data_dictionary.md).
- [Repeat the audit](../src/cleaning_pipeline/README.md) — one command, new run ID, separate outputs.
- [Original handoff](FYP_Codex_Data_Cleaning_Handoff_2026-11-08.md).

The raw HDF5 remains immutable and read-only. Original scripts and processed pilot files were not overwritten. Models and feature tables are in separate versioned directories. Exact registered-grid geometry, usable XCT support and annotation semantics need clarification before finalizing scientific targets. The saved source-preparation readiness flags were not promoted by the exploratory experiment. Fold 0 has now been inspected; adaptive follow-up experiments require a fresh honest evaluation plan.
