from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
import streamlit as st
from matplotlib.figure import Figure
from matplotlib.patches import Patch


DATA_FILE = Path(__file__).parent / "DfE_LondonSE_KS4_2025_26.csv"
BOROUGHS = ("Bexley", "Bromley", "Greenwich")
MAX_SCHOOLS = 7
MAX_CHART_SUBJECTS = 6
REQUIRED_COLUMNS = {
    "geographic_level",
    "school_urn",
    "school_name",
    "la_name",
    "establishment_type_group",
    "pupil_count",
    "qualification_type",
    "qualification_detailed",
    "subject",
    "subject_discount_group",
    "grade",
    "number_achieving",
}
GRADE_RANKS = {
    "a*": 0,
    "a": 1,
    "b": 2,
    "c": 3,
    "d": 4,
    "e": 5,
    "f": 6,
    "g": 7,
    "level 2 distinction star": 10,
    "level 2 distinction": 11,
    "distinction": 12,
    "level 2 merit": 13,
    "merit": 14,
    "level 2 pass": 15,
    "pass": 16,
    "level 1 distinction star": 20,
    "level 1 distinction": 21,
    "level 1 merit": 22,
    "level 1 pass": 23,
    "u": 90,
    "x": 91,
}
SUBJECT_COLORS = (
    "#0057B8",
    "#D62828",
    "#008A5B",
    "#7B2CBF",
    "#E07A00",
    "#007C91",
)
BAND_HATCHES = ("", "..", "//", "xx", "\\\\")
BAND_PATTERN_NAMES = ("solid", "dotted", "striped", "crosshatched", "diagonal")


@st.cache_data(show_spinner="Loading the KS4 data file…")
def load_data(file_path: str, modified_time: float) -> pd.DataFrame:
    del modified_time
    data = pd.read_csv(file_path, dtype="string", low_memory=False)
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"The KS4 data file is missing required columns: {missing}")

    data = data.loc[
        data["geographic_level"].eq("School") & data["la_name"].isin(BOROUGHS)
    ].copy()
    data["number_achieving"] = pd.to_numeric(data["number_achieving"], errors="coerce")
    data["pupil_count"] = pd.to_numeric(data["pupil_count"], errors="coerce")
    return data


def grade_sort_key(grade: str) -> tuple[int, Any]:
    normalized = grade.casefold()
    if normalized.isdigit():
        return (0, -int(normalized))
    if normalized in GRADE_RANKS:
        return (1, GRADE_RANKS[normalized])
    return (2, normalized)


def school_label(school: dict[str, Any]) -> str:
    return f"{school['school_name']} — {school['la_name']} (URN {school['school_urn']})"


def get_comparison_rows(
    data: pd.DataFrame,
    qualification_type: str,
    qualification_detail: str,
    subject: str,
    subject_group: str,
    school_urns: list[str],
) -> pd.DataFrame:
    selected = data.loc[
        data["qualification_type"].eq(qualification_type)
        & data["qualification_detailed"].eq(qualification_detail)
        & data["subject"].eq(subject)
        & data["school_urn"].isin(school_urns)
    ]
    if subject_group:
        selected = selected.loc[selected["subject_discount_group"].eq(subject_group)]

    return (
        selected.groupby(
            [
                "school_urn",
                "school_name",
                "la_name",
                "establishment_type_group",
                "grade",
            ],
            as_index=False,
            observed=True,
        )
        .agg(
            entry_count=("number_achieving", "sum"),
            reported_pupil_count=("pupil_count", "max"),
        )
    )


def make_comparison_table(
    rows: pd.DataFrame,
    selected_schools: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    total_rows = rows.loc[rows["grade"].str.casefold().eq("total exam entries")]
    grade_rows = rows.loc[~rows["grade"].str.casefold().eq("total exam entries")]
    grades = sorted(grade_rows["grade"].dropna().unique().tolist(), key=grade_sort_key)
    summary_records: list[dict[str, Any]] = []
    table: dict[str, list[str]] = {"Reported grade": grades}
    warnings: list[str] = []

    for _, school in selected_schools.iterrows():
        urn = school["school_urn"]
        school_rows = rows.loc[rows["school_urn"].eq(urn)]
        school_grades = grade_rows.loc[grade_rows["school_urn"].eq(urn)]
        reported_totals = total_rows.loc[total_rows["school_urn"].eq(urn), "entry_count"]
        total_entries = float(reported_totals.sum()) if not reported_totals.empty else float(
            school_grades["entry_count"].sum()
        )
        if reported_totals.empty and not school_grades.empty:
            warnings.append(
                f"{school['school_name']}: no total-entry row was reported; the displayed total "
                "uses the sum of its grade counts."
            )
        grade_total = float(school_grades["entry_count"].sum())
        if not reported_totals.empty and grade_total != total_entries:
            warnings.append(
                f"{school['school_name']}: grade counts do not add exactly to reported total "
                "exam entries; percentages use the reported total."
            )

        pupil_values = school_rows["reported_pupil_count"].dropna()
        summary_records.append(
            {
                "School": school["school_name"],
                "Local authority": school["la_name"],
                "URN": urn,
                "Establishment type": school["establishment_type_group"],
                "Reported pupil count": int(pupil_values.max()) if not pupil_values.empty else None,
                "Total exam entries": int(total_entries) if pd.notna(total_entries) else None,
            }
        )

        school_name = str(school["school_name"])
        counts = school_grades.set_index("grade")["entry_count"].to_dict()
        table[school_name] = [
            "—"
            if grade not in counts or total_entries <= 0
            else f"{counts[grade]:,.0f} ({counts[grade] / total_entries * 100:.1f}%)"
            for grade in grades
        ]

    return pd.DataFrame(summary_records), pd.DataFrame(table), list(dict.fromkeys(warnings))


def common_numeric_grade_bands(grades: list[str]) -> list[dict[str, Any]]:
    grade_values = {grade for grade in grades if grade.isdigit()}
    band_definitions = (
        ("Top ratings (8–9)", {"8", "9"}),
        ("Mid ratings (5–7)", {"5", "6", "7"}),
        ("Below 5 (1–4)", {"1", "2", "3", "4"}),
    )
    return [
        {"label": label, "grades": sorted(grade_values & band_grades, key=grade_sort_key)}
        for label, band_grades in band_definitions
        if grade_values & band_grades
    ]


def build_chart_data(
    data: pd.DataFrame,
    qualification_type: str,
    qualification_detail: str,
    subject_group: str,
    school_urns: list[str],
    chart_subjects: list[str],
    bands: list[dict[str, Any]],
) -> pd.DataFrame:
    selected = data.loc[
        data["qualification_type"].eq(qualification_type)
        & data["qualification_detailed"].eq(qualification_detail)
        & data["subject"].isin(chart_subjects)
        & data["school_urn"].isin(school_urns)
    ]
    if subject_group:
        selected = selected.loc[selected["subject_discount_group"].eq(subject_group)]

    keys = ["school_urn", "subject"]
    total_rows = selected.loc[
        selected["grade"].str.casefold().eq("total exam entries")
    ]
    grade_rows = selected.loc[
        ~selected["grade"].str.casefold().eq("total exam entries")
    ]
    totals = total_rows.groupby(keys, observed=True)["number_achieving"].sum()
    grade_totals = grade_rows.groupby(keys, observed=True)["number_achieving"].sum()
    totals = totals.combine_first(grade_totals)
    grade_counts = grade_rows.groupby(
        [*keys, "grade"], observed=True
    )["number_achieving"].sum()

    records: list[dict[str, Any]] = []
    for school_urn in school_urns:
        for subject in chart_subjects:
            total_entries = float(totals.get((school_urn, subject), 0))
            for band in bands:
                entries = sum(
                    float(grade_counts.get((school_urn, subject, grade), 0))
                    for grade in band["grades"]
                )
                records.append(
                    {
                        "school_urn": school_urn,
                        "subject": subject,
                        "band": band["label"],
                        "grades": ", ".join(band["grades"]),
                        "entries": entries,
                        "total_entries": total_entries,
                        "percentage": (
                            entries / total_entries * 100 if total_entries > 0 else None
                        ),
                    }
                )
    return pd.DataFrame(records)


def make_grade_band_figure(
    chart_data: pd.DataFrame,
    selected_schools: pd.DataFrame,
    chart_subjects: list[str],
    bands: list[dict[str, Any]],
) -> Figure:
    school_records = selected_schools.to_dict("records")
    figure_width = max(10, len(school_records) * 1.65)
    figure, axis = plt.subplots(figsize=(figure_width, 6.2))
    group_width = 0.8
    subject_width = group_width / max(1, len(chart_subjects))
    x_positions = list(range(len(school_records)))

    for subject_index, subject in enumerate(chart_subjects):
        color = SUBJECT_COLORS[subject_index % len(SUBJECT_COLORS)]
        subject_x = [
            x + (subject_index - (len(chart_subjects) - 1) / 2) * subject_width
            for x in x_positions
        ]
        bottoms = [0.0] * len(school_records)
        for band_index, band in enumerate(bands):
            band_rows = chart_data.loc[
                chart_data["subject"].eq(subject)
                & chart_data["band"].eq(band["label"])
            ].set_index("school_urn")["percentage"].to_dict()
            heights = [
                float(band_rows[school["school_urn"]])
                if school["school_urn"] in band_rows
                and pd.notna(band_rows[school["school_urn"]])
                else 0.0
                for school in school_records
            ]
            axis.bar(
                subject_x,
                heights,
                subject_width * 0.9,
                bottom=bottoms,
                color=color,
                edgecolor="#172b3a",
                linewidth=0.55,
                hatch=BAND_HATCHES[band_index % len(BAND_HATCHES)],
            )
            bottoms = [bottom + height for bottom, height in zip(bottoms, heights)]

    axis.set_xticks(x_positions)
    axis.set_xticklabels(
        [
            f"{school['school_name']}\n{school['la_name']}"
            for school in school_records
        ],
        rotation=0,
        ha="center",
    )
    axis.set_ylabel("Share of total exam entries (%)")
    axis.set_ylim(0, 100)
    axis.set_yticks(range(0, 100, 10))
    axis.set_title("Grade-band distribution by school and subject")
    axis.grid(axis="y", color="#010a10", linewidth=0.9)
    axis.set_axisbelow(True)

    subject_legend = [
        Patch(facecolor=SUBJECT_COLORS[index % len(SUBJECT_COLORS)], label=subject)
        for index, subject in enumerate(chart_subjects)
    ]
    band_legend = [
        Patch(
            facecolor="#e7edf1",
            edgecolor="#172b3a",
            hatch=BAND_HATCHES[index % len(BAND_HATCHES)],
            label=f"{band['label']} ({BAND_PATTERN_NAMES[index % len(BAND_PATTERN_NAMES)]})",
        )
        for index, band in enumerate(bands)
    ]
    legend = axis.legend(
        handles=[*subject_legend, *band_legend],
        loc="upper left",
        bbox_to_anchor=(0.05, 0.95),
        borderaxespad=0,
        frameon=True,
        ncol=min(3, len(subject_legend) or 1),
    )
    axis.add_artist(legend)
    figure.tight_layout(rect=(0, 0, 0.75, 1))
    return figure


def make_grade_band_chart(
    chart_data: pd.DataFrame,
    selected_schools: pd.DataFrame,
    chart_subjects: list[str],
    bands: list[dict[str, Any]],
) -> alt.Chart:
    school_labels = selected_schools.set_index("school_urn").apply(
        lambda school: f"{school['school_name']} — {school['la_name']}", axis=1
    ).to_dict()
    plot_data = chart_data.copy()
    plot_data["school"] = plot_data["school_urn"].map(school_labels)
    band_order = [band["label"] for band in bands]
    plot_data["band"] = pd.Categorical(plot_data["band"], categories=band_order, ordered=True)
    band_ranks = {label: index for index, label in enumerate(band_order)}
    plot_data["band_order"] = plot_data["band"].map(band_ranks).astype("int64")
    plot_data["entries"] = plot_data["entries"].round().astype("int64")
    plot_data["total_entries"] = plot_data["total_entries"].round().astype("int64")
    plot_data["percentage"] = plot_data["percentage"].fillna(0).round(1)
    plot_data = plot_data.sort_values(["school_urn", "subject", "band_order"])
    plot_data["band_end"] = plot_data.groupby(
        ["school_urn", "subject"], observed=True
    )["percentage"].cumsum()
    plot_data["band_start"] = plot_data["band_end"] - plot_data["percentage"]

    return (
        alt.Chart(plot_data)
        .mark_bar(cornerRadius=1)
        .encode(
            x=alt.X("school:N", title=None, sort=list(school_labels.values()),
                    axis=alt.Axis(labelAngle=0, labelFontSize=10, labelLimit=150)),
            xOffset=alt.XOffset("subject:N", sort=chart_subjects),
            y=alt.Y("band_end:Q", title="Share of total exam entries (%)",
                    scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(labelFontSize=10)),
            y2=alt.Y2("band_start:Q"),
            color=alt.Color(
                "subject:N",
                title="Subject",
                sort=chart_subjects,
                scale=alt.Scale(
                    domain=chart_subjects,
                    range=[SUBJECT_COLORS[index % len(SUBJECT_COLORS)]
                           for index in range(len(chart_subjects))],
                ),
            ),
            opacity=alt.Opacity(
                "band:N",
                title="Rating group",
                sort=band_order,
                scale=alt.Scale(
                    domain=band_order,
                    range=[1.0, *([0.58] * max(0, len(band_order) - 1))],
                ),
            ),
            tooltip=[
                alt.Tooltip("school:N", title="School"),
                alt.Tooltip("subject:N", title="Subject"),
                alt.Tooltip("band:N", title="Rating group"),
                alt.Tooltip("grades:N", title="Grades included"),
                alt.Tooltip("percentage:Q", title="Share", format=".1f"),
                alt.Tooltip("entries:Q", title="Entries in group", format=","),
                alt.Tooltip("total_entries:Q", title="Total exam entries", format=","),
            ],
        )
        .properties(
            height=360,
            title="Grade-band distribution by school and subject",
        )
        .configure_view(stroke=None)
        .configure_axis(gridColor="#d8e1e7")
        .configure_legend(
            labelFontSize=13,
            titleFontSize=14,
            titleFontWeight="bold",
            symbolSize=190,
            symbolStrokeWidth=0,
            padding=12,
            rowPadding=8,
            columnPadding=20,
            labelLimit=220,
        )
        .interactive()
    )


def main() -> None:
    st.set_page_config(page_title="DfE KS4 Data Lab", layout="wide")
    st.title("DfE KS4 Data Lab")
    st.caption("Provisional 2025/26 outcomes for secondary schools in Bexley, Bromley and Greenwich.")
    st.info(f"Data file: **{DATA_FILE.name}** · loaded from this app's folder.")

    if not DATA_FILE.is_file():
        st.error(
            f"Could not find `{DATA_FILE.name}`. Place the CSV in the same folder as `app.py` "
            "and restart or rerun the app."
        )
        st.stop()

    data = load_data(str(DATA_FILE), DATA_FILE.stat().st_mtime)
    if data.empty:
        st.error(f"`{DATA_FILE.name}` contains no school rows for the configured boroughs.")
        st.stop()

    st.caption(
        f"Loaded {len(data):,} school-level rows for {data['school_urn'].nunique():,} schools. "
        "Data is read locally by the Streamlit server."
    )

    with st.sidebar:
        st.header("Comparison filters")
        qualification_types = sorted(data["qualification_type"].dropna().unique().tolist())
        qualification_type = st.selectbox("Qualification type", qualification_types)

        qualification_details = sorted(
            data.loc[data["qualification_type"].eq(qualification_type), "qualification_detailed"]
            .dropna()
            .unique()
            .tolist()
        )
        qualification_detail = st.selectbox("Qualification detail", qualification_details)

        subjects = sorted(
            data.loc[
                data["qualification_type"].eq(qualification_type)
                & data["qualification_detailed"].eq(qualification_detail),
                "subject",
            ]
            .dropna()
            .unique()
            .tolist()
        )
        comparison_subject = st.selectbox("Comparison subject", subjects)
        subject_groups = sorted(
            data.loc[
                data["qualification_type"].eq(qualification_type)
                & data["qualification_detailed"].eq(qualification_detail)
                & data["subject"].eq(comparison_subject),
                "subject_discount_group",
            ]
            .dropna()
            .unique()
            .tolist()
        )
        subject_group = st.selectbox("Subject group", ["All groups", *subject_groups])

        schools = (
            data.loc[:, ["school_urn", "school_name", "la_name", "establishment_type_group"]]
            .drop_duplicates("school_urn")
            .sort_values(["school_name", "school_urn"])
        )
        schools_by_urn = schools.set_index("school_urn", drop=False).to_dict("index")
        selected_urns = st.multiselect(
            f"Schools to compare (up to {MAX_SCHOOLS})",
            options=schools["school_urn"].tolist(),
            format_func=lambda urn: school_label(schools_by_urn[urn]),
            max_selections=MAX_SCHOOLS,
            help="Search by school name, borough or URN. No schools are selected initially.",
        )

    if not selected_urns:
        st.warning("Select one or more schools in the sidebar to see their results.")
        st.stop()

    selected_schools = schools.loc[schools["school_urn"].isin(selected_urns)].copy()
    comparison_rows = get_comparison_rows(
        data,
        qualification_type,
        qualification_detail,
        comparison_subject,
        "" if subject_group == "All groups" else subject_group,
        selected_urns,
    )
    summary, comparison_table, comparison_warnings = make_comparison_table(
        comparison_rows,
        selected_schools,
    )

    st.subheader(f"{comparison_subject} comparison")
    st.caption(
        f"{qualification_type} · {qualification_detail}"
        + (f" · {subject_group}" if subject_group != "All groups" else "")
    )
    if comparison_rows.empty:
        st.info("No results matched the selected schools and filters.")
    else:
        st.dataframe(summary, hide_index=True, use_container_width=True)
        st.dataframe(comparison_table, hide_index=True, use_container_width=True)
        if comparison_warnings:
            for warning in comparison_warnings:
                st.caption(warning)
        st.download_button(
            "Download comparison CSV",
            comparison_table.to_csv(index=False).encode("utf-8-sig"),
            file_name="DfE_KS4_school_comparison.csv",
            mime="text/csv",
        )

    st.divider()
    st.subheader("Grade-band chart")
    st.caption(
        "Rating groups stack from bottom to top in the order added. Each subject has its own "
        "colour; rating groups use solid, dotted and striped fills. Percentages use total exam entries."
    )
    chart_subjects = st.multiselect(
        f"Chart subjects (up to {MAX_CHART_SUBJECTS})",
        options=subjects,
        default=[subject for subject in ("English Language", "Mathematics", "Maths") if subject in subjects][:2],
        max_selections=MAX_CHART_SUBJECTS,
        help="Choose up to six subjects. English Language and Maths are preselected when available.",
    )
    chart_source = data.loc[
        data["qualification_type"].eq(qualification_type)
        & data["qualification_detailed"].eq(qualification_detail)
        & data["subject"].isin(chart_subjects)
        & data["school_urn"].isin(selected_urns)
    ]
    if subject_group != "All groups":
        chart_source = chart_source.loc[
            chart_source["subject_discount_group"].eq(subject_group)
        ]
    chart_grade_options = sorted(
        chart_source.loc[
            ~chart_source["grade"].str.casefold().eq("total exam entries"), "grade"
        ]
        .dropna()
        .unique()
        .tolist(),
        key=grade_sort_key,
    )
    band_context = (qualification_type, qualification_detail, subject_group)
    if st.session_state.get("chart_band_context") != band_context:
        st.session_state["chart_band_context"] = band_context
        st.session_state["chart_bands"] = []

    chart_bands: list[dict[str, Any]] = st.session_state.setdefault("chart_bands", [])
    assigned_grades = {grade for band in chart_bands for grade in band["grades"]}
    preset_bands = common_numeric_grade_bands(chart_grade_options)
    if preset_bands and any(
        grade not in assigned_grades
        for band in preset_bands
        for grade in band["grades"]
    ):
        if st.button("Add common 9–1 rating groups", key="add_common_grade_bands"):
            for band in preset_bands:
                remaining_grades = [
                    grade
                    for grade in band["grades"]
                    if grade not in assigned_grades
                ]
                if remaining_grades:
                    chart_bands.append(
                        {"label": band["label"], "grades": remaining_grades}
                    )
                    assigned_grades.update(remaining_grades)

    st.markdown("**Configure rating groups**")
    unassigned_grades = [
        grade for grade in chart_grade_options if grade not in assigned_grades
    ]
    with st.form("add_grade_band", clear_on_submit=True):
        band_label = st.text_input(
            "Rating group name", placeholder="For example, Grades 8–9"
        )
        band_grades = st.multiselect(
            "Grades to include",
            options=unassigned_grades,
            help="A grade can belong to only one group in a stacked chart.",
        )
        add_band = st.form_submit_button("Add rating group")
    if add_band:
        if not band_label.strip():
            st.error("Enter a name for the rating group.")
        elif not band_grades:
            st.error("Select at least one grade for the rating group.")
        else:
            chart_bands.append({"label": band_label.strip(), "grades": band_grades})

    if chart_bands:
        st.markdown("**Current rating groups**")
        for band_index, band in enumerate(list(chart_bands)):
            band_column, remove_column = st.columns([8, 1])
            band_column.write(f"{band['label']}: {', '.join(band['grades'])}")
            if remove_column.button(
                "Remove",
                key=f"remove_grade_band_{band_index}",
                help=f"Remove rating group {band['label']}",
            ):
                chart_bands.pop(band_index)

    if chart_subjects and chart_bands:
        chart_data = build_chart_data(
            data,
            qualification_type,
            qualification_detail,
            "" if subject_group == "All groups" else subject_group,
            selected_urns,
            chart_subjects,
            chart_bands,
        )
        if chart_data.empty or chart_data["total_entries"].le(0).all():
            st.info("No results were found for the selected chart subjects and rating groups.")
        else:
            chart = make_grade_band_chart(
                chart_data, selected_schools, chart_subjects, chart_bands
            )
            st.altair_chart(chart, use_container_width=True)
            chart_table = chart_data.merge(
                selected_schools[["school_urn", "school_name", "la_name"]],
                on="school_urn",
                how="left",
            )
            st.dataframe(
                chart_table[
                    [
                        "subject",
                        "band",
                        "grades",
                        "school_name",
                        "la_name",
                        "entries",
                        "total_entries",
                        "percentage",
                    ]
                ].rename(
                    columns={
                        "subject": "Subject",
                        "band": "Rating group",
                        "grades": "Grades included",
                        "school_name": "School",
                        "la_name": "Borough",
                        "entries": "Entries in group",
                        "total_entries": "Total exam entries",
                        "percentage": "Percentage",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
    elif not chart_subjects:
        st.caption("Select at least one chart subject.")
    elif not chart_bands:
        st.caption("Add rating groups to draw the stacked chart.")

    st.caption(
        "Grade counts are exam entries, not unique pupils. The separate reported pupil count "
        "is shown for context and is not the percentage denominator."
    )


if __name__ == "__main__":
    main()
