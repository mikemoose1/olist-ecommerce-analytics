# Tool spikes: Evidence, Quarto, Streamlit

Each spike drew the same two charts from the warehouse on 2026-11-18: the late rate by purchase month with a 95% band, and the late rate for the ten states with the most late orders, with 95% error bars. All three ran the same SQL on the judged orders. The spikes were throwaway code outside the repo. The numbers below are what the box measured.

| | Evidence 40.1.8 (open-source npm package) | Quarto 1.11.9 (pip `quarto-cli`) | Streamlit 1.67.0 |
|---|---|---|---|
| Install | `npm install` 20 s, 698 MB of `node_modules` | 14 s with matplotlib in a fresh venv, 836 MB | about 46 s together with Quarto, Jupyter and matplotlib |
| Reads `olist.duckdb` | No. Its DuckDB cannot open the warehouse file, which a newer DuckDB wrote. The spike had to export `fct_orders` to Parquet first | Yes, through the repo's own DuckDB | Yes, through the repo's own DuckDB |
| Build time | sources 2.2 s, then `npm run build` 33 to 34 s | `quarto render` 4.8 to 5.1 s | no build. AppTest smoke run 1.4 s. Server ready in 0.5 s, first chart in the browser after 2.4 s |
| Output | static site, 94 MB, needs an HTTP server. Opened from disk it shows "Loading..." | one self-contained HTML file, 1.4 MB, opens from disk | not static. The reader needs a running Python server |
| Charts on first try | month line came out sorted by value, not by month, so the peak looked like a steady decline. No band or error bars without custom chart code | band and error bars right on the first try (matplotlib) | same as Quarto (matplotlib) |
| Runs from `make` and in CI without a workflow edit | possible, but needs Node and npm steps beside the Python venv | yes. `quarto-cli` installs from `requirements.txt`, which `make setup` already installs | only a smoke test. CI cannot hand anyone the result |
| Can a fresh AI reader or an emailed manager open it | needs a server | yes, one file | no |

The Evidence template on GitHub now points to Evidence Studio, a hosted product whose CLI needs a login. The spike used the last open-source npm release instead.

## Pick: Quarto

The reader is an operations manager who will get a file, and the known-answer test hands the same file to fresh AI readers. Quarto is the only one of the three that produces one static file that opens from disk. It also builds in about 5 seconds from the same Python venv that `make` already sets up, so CI runs it with no workflow change. GitHub Actions run 44328349710 confirmed it: the unchanged workflow installed `quarto-cli` during `make setup` and built the page in 4.2 s inside `make verify`. The story renders charts with matplotlib in `story/build_story.py` and lets Quarto assemble the page, so the build needs no Jupyter kernel.
