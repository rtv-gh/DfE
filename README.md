# DfE School Data Lab

This project includes two interfaces for comparing 2025/26 provisional Key Stage 4 subject results for schools in Bexley, Bromley and Greenwich:

- `query.html`: a local browser-based comparison tool.
- `app.py`: a Streamlit comparison app that reads the local CSV on the server.

Both use `DfE_LondonSE_KS4_2025_26.csv` from this folder.

## Start the workbench

1. Open PowerShell in this folder.
2. Run:

   ```powershell
   python -m http.server 8000 --bind 127.0.0.1
   ```

   If PowerShell cannot find `python` and your Python virtual environment is active, run `& "$env:VIRTUAL_ENV\Scripts\python.exe" -m http.server 8000 --bind 127.0.0.1` instead.

3. Open [http://localhost:8000/query.html](http://localhost:8000/query.html) in Chrome or Edge.
4. The page automatically loads `DfE_LondonSE_KS4_2025_26.csv` from the same folder as `query.html`.

The browser queries this file locally; CSV data is not uploaded. The SQL engine is loaded from jsDelivr, so an internet connection is required when the page first starts. Keep the CSV beside `query.html` and open the page from the local web server so the browser can fetch it automatically.

## Run the Streamlit app

1. Open PowerShell in this folder.
2. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If script activation is restricted, use the environment's Python directly in the following commands: `.\.venv\Scripts\python.exe`.

3. Install the project dependencies:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Start the app:

   ```powershell
   streamlit run app.py
   ```

5. Open the local URL printed by Streamlit, normally [http://localhost:8501](http://localhost:8501).

The app loads `DfE_LondonSE_KS4_2025_26.csv` from the same folder as `app.py`. It provides qualification, subject, school and optional subject-group filters; a comparison table; a stacked grade-band chart for up to six subjects; and a CSV download. No schools are selected by default, and up to seven can be compared.

For numeric 9–1 grades, use **Add common 9–1 rating groups** to add Top ratings (8–9), Mid ratings (5–7) and Below 5 (1–4). You can also create your own rating groups by naming each group and selecting its grades. A grade can only appear in one group at a time, so the stacked segments remain distinct. Subjects use separate colours, while rating groups use solid, dotted, striped and other hatch patterns. Percentages use total exam entries as the denominator; grade counts are exam entries, not unique pupils.

For Streamlit Community Cloud, push `app.py`, `requirements.txt` and the data file to a GitHub repository, then create an app in Streamlit Community Cloud with `app.py` as the entry point. The deployed app runs on the hosting server, so the CSV must be included in the repository or made available to the app through an appropriate data source. Only deploy the data if its licensing and your organization's data-sharing rules permit it.

## Key stage 4 school comparison

The comparison is limited to individual schools in the London Boroughs of Bexley, Bromley and Greenwich. To regenerate the reduced data file from the original full-size KS4 source, run this command from the project folder:

```powershell
python query.py --reduce-ks4
```

By default, the command reads `202526_subject_school_all_exam_entriesgrades_provisional.csv` and creates `DfE_LondonSE_KS4_2025_26.csv` alongside it. The original source is left unchanged, and rerunning the command regenerates the reduced file. Use `--input-csv` and `--reduced-output` to specify different paths; keep the output filename as `DfE_LondonSE_KS4_2025_26.csv` for automatic loading. The reduced file keeps all school rows for Bexley, Bromley and Greenwich and retains England National and London Regional aggregate rows when present.

For the supplied snapshot, the reduced CSV contains 11,393 school rows (3.0 MB). The source contains no England National or London Regional aggregate rows, so there are no aggregate rows in this reduced copy.

1. The page loads `DfE_LondonSE_KS4_2025_26.csv` automatically; the file name and connection status appear above the filters.
2. Choose a qualification type and detail, then search for schools by name, URN or local authority and add up to seven schools. No schools are selected by default.
3. Choose a subject for the comparison table. For charts, choose up to six subjects; English Language and Maths are preselected when available.

The comparison shows the reported pupil count and total exam entries for each school, followed by grade counts and each grade's share of the selected subject's total entries. The pupil count is shown as source context and is not used as the percentage denominator. Grade counts are exam entries, not unique pupils. A school can have more than one exam entry per pupil.

The original provisional snapshot is about 218.7 MB and contains 733,117 school-level rows for academic year 2025/26. It covers 4,907 schools, 49 subjects and seven qualification types. Grade scales vary by qualification. The CSV contains grade-detail rows and separate `Total exam entries` rows; do not add the two together. Grade buckets do not always add exactly to the reported total entries, so percentages may not sum to 100%.

The comparison tool uses DuckDB-Wasm to query the reduced file locally.

## Data source

UK Department for Education, [School pupils and their characteristics](https://explore-education-statistics.service.gov.uk/find-statistics/school-pupils-and-their-characteristics). The data is for England and includes historical periods in some files.

The comparison uses the provisional school-level key-stage-4 CSV in this folder.
