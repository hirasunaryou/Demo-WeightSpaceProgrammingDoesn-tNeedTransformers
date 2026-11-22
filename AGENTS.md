# AGENTS.md — Weight-Space Programming Live Lab

## Purpose
Hyunjong Ok / Jaeho Lee (POSTECH) の原著 `Weight-Space Programming Doesn't Need Transformers`（arXiv:2611.22055、MIT）の勉強会用独立アプリ。

## Scientific fidelity (highest priority)
- Original: `effl-lab/Weight-Space-Programming`, pinned commit `c3324efa7e8aeec9ff7b7303094799b67a20793b`.
- `sources/` is a **verbatim partial original snapshot** of one published model, three published result files, and MIT license. Never silently change the source files.
- The default app is **a teaching analogue**, not the authors' PyTorch `arch.py/forward()` or ARC evaluation. Label every score/ablation accordingly. Never present illustrative results as 54.4% or 52.4% official measured performance.
- WSP: LLM writes model weights/data; then a separate fixed scoring function reads them. This is **not** gradient-descent learning, not a Transformer, not a language chat assistant, and not a broad proof that trained LLMs are inferior.
- Show source path, row number, verbatim line, source commit URL for every original fact. Local edited facts are separate and not saved into original.
- Research claims and accuracy tables must cite authors' README / arXiv. Important figures (54.4% for free LLM-designed, 52.4% for Opus our architecture; 3,530 ARC questions; 17x speed in their compared setup) must never be generalized beyond the study.
- Reproducing original Linux bwrap/PyTorch runner is optional and must not install packages or run commercial writer agents without explicit user action.

## UX
- Mac start_mac.command + Windows start_windows.bat: one-click, no venv, pip or GPU for learning mode.
- README begins with real UI screenshots. Japanese HTML help is visually rich, meaningful figures dominate dense text.
- Light/dark, font scaling, projector mode, keyboard controls; clean UI, deeper explanations only on demand.
- Three pillars: 1) weight writing, 2) evidence read and option scoring, 3) ablation/edit a row and inspect score differences.
- Attribution: independent learning interface, NOT an official WSP implementation. Original authors and MIT notice visible.

## Tests
- `python -m unittest discover -s tests -v`
- `python launch.py --self-check`
- Browser screenshots from real app data, with Japanese fonts; never claim a mock screenshot is real evidence.
