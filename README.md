# multi-agent-system-and-eval
Multi and single agent system made for a VU Informatics Bachelor's thesis that compares the two architectures. 

## Overview

This repository contains the implementation of two LLM-based code generation systems and the evaluation infrastructure used to compare them:

- **Multi-agent system** — a pipeline of four specialized agents (Planner, Coder, Tester, Reviewer) operating in an iterative loop
- **Single-agent system** — a single agent performing all roles in one continuous loop
- **Evaluation tools** — scripts for feature-based manual grading and automated static code analysis

Both systems use the same model (DeepSeek-V4-Pro), the same tools, and the same Docker-based execution environment, isolating architecture as the primary variable.

## Tasks
This repository contains 19 tasks across 5 difficulties.

## Results
All of the results from 114 runs are stored in `results/` folder.
