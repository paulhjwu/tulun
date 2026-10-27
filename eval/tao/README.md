# Chinese → Tao (Yami) evaluation

Experiments on translating Traditional Chinese into Tao (`tao_Latn`, a language not in NLLB-200), using a fine-tuned NLLB draft that Gemma 4 post-edits with retrieval from a translation memory and glossary. The workflow follows [`../tetun_bislama/`](../tetun_bislama/).

## Contents

| File | Purpose |
| --- | --- |
| [`tao_nllb_finetune.ipynb`](./tao_nllb_finetune.ipynb) | Part 1 (Google Colab GPU). Fine-tunes NLLB on data A and saves it to `models/nllb-tao-ft/`. |
| [`tao_nllb_gemma.ipynb`](./tao_nllb_gemma.ipynb) | Part 2 (local GPU). Loads the fine-tuned model, runs NLLB → Gemma 4 RAG post-editing on data B, and scores with chrF++ / BLEU. |
| [`tao_eval_cunp89t_vs_chang.ipynb`](./tao_eval_cunp89t_vs_chang.ipynb) | Scores the CUNP89T Ruth/Jonah text against the Chang text, which serves as the reference. |
| [`align_verses.py`](./align_verses.py) | Aligns Chang and CUNP89T verses for Ruth and Jonah. |
| [`benchmark_data/`](./benchmark_data/) | Ruth and Jonah texts and the aligned verse file. |
| [`results/`](./results/) | CSV outputs from the CUNP89T vs. Chang evaluation. |

## 1. Fine-tune and post-edit

Both notebooks read the same data layout, relative to the repo root. Each folder can hold `.json`, `.jsonl` or `.csv` files.

```
data/finetune/        A  fine-tuning pairs
data/eval/            B  evaluation pairs
data/memory/          C  translation memory (retrieval pool)
data/glossary/        D  Chinese-Tao glossary
models/nllb-tao-ft/   fine-tuned model from Part 1 (or models/nllb-tao-ft.zip)
```

- A, B, C: records with `chinese_sentence` and `tao_sentence` (aliases `zh` / `tao`).
- D: records with `zh` and `tao` (aliases `key` / `value`).
- Keep B out of A and C. The notebook warns about exact duplicates; for Bible-style data, also split by book or chapter.

Steps:

1. Run `tao_nllb_finetune.ipynb` on a Colab GPU runtime. It starts from the `tgl_Latn` embedding for the new `tao_Latn` token, saves the model to Google Drive, and offers a zip download. Copy the repo's `data/` to `MyDrive/tulun/data/` first.
2. Put the model in `models/nllb-tao-ft/` in the repo, by syncing Drive or unzipping the download.
3. Install a CUDA build of PyTorch, then run `tao_nllb_gemma.ipynb` from this folder. Set `DEEPINFRA_API_KEY` in the environment or a `.env` file.

Retrieval uses BM25 over the Chinese side of the memory, segmented with `jieba`, plus substring matches against the glossary. LLM responses and translations are cached on disk under `cache/`, so re-runs are free.

## 2. CUNP89T vs. Chang

`tao_eval_cunp89t_vs_chang.ipynb` measures how far the CUNP89T translation of Ruth and Jonah is from the Chang translation. It uses the alignment in `benchmark_data/aligned-RUT-JON.json`.

To rebuild the alignment from the source HTML:

```bash
python align_verses.py
```

Chang is the reference. Each Chang verse, or verse range such as `1-2`, becomes one entry, and the CUNP89T verses in that range are joined. Keys have the form `BBCCCVVV-VVV` (book, chapter, first verse, last verse), for example `08001001-002` for Ruth 1:1-2.

Scores are corpus-level chrF++ (`word_order=2`) and BLEU from `sacrebleu`, on raw text and on normalized text. Normalization applies NFKC, lowercases, drops bracketed notes such as `[10]`, and strips punctuation.

| | chrF++ | BLEU | n |
| --- | --- | --- | --- |
| raw | 33.86 | 9.46 | 127 |
| normalized | 37.06 | 11.81 | 127 |

Per-verse scores are in [`results/tao_cunp89t_vs_chang.csv`](./results/tao_cunp89t_vs_chang.csv) and the summary is in [`results/tao_cunp89t_vs_chang_summary.csv`](./results/tao_cunp89t_vs_chang_summary.csv).
