#!/usr/bin/env python3
"""
School Pupils & Characteristics 2025-26 - Data Query Tool
A Python script for querying the DfE CSV files with pandas.
"""

import pandas as pd
import os
import csv
from pathlib import Path
from typing import Optional, List, Dict, Any
import argparse

DATA_DIR = Path(__file__).parent
KS4_BOROUGHS = {"Bexley", "Bromley", "Greenwich"}
KS4_SOURCE = "202526_subject_school_all_exam_entriesgrades_provisional.csv"
KS4_REDUCED = "DfE_LondonSE_KS4_2025_26.csv"

# Dataset configurations
DATASETS = {
    'ks4_subjects': KS4_REDUCED,
    'fsm_school': 'spc_school_characteristics_fsm_api.csv',
    'key_stage': 'spc_school_characteristics_key_stage_api.csv',
    'first_lang': 'spc_school_characteristics_first_lang_api.csv',
    'age_sex_attendance': 'spc_school_characteristics_age_sex_attendance_pattern_api.csv',
    'boarding': 'spc_school_characteristics_boarding_api.csv',
    'ethnicity_language': 'spc_pupils_ethnicity_and_language.csv',
    'fsm_ethnicity_yrgp': 'spc_pupils_fsm_ethnicity_yrgp.csv',
    'yeargroup_sex': 'spc_pupils_yeargroup_and_sex.csv',
    'age_sex': 'spc_pupils_age_and_sex.csv',
    'young_carers': 'spc_pupils_young_carers_yrgp.csv',
    'fsm_api': 'spc_fsm_api.csv',
    'fsm6': 'spc_fsm6.csv',
    'uifsm': 'spc_uifsm.csv',
    'class_size': 'spc_class_size_api.csv',
    'ap_placement': 'spc_school_ap_placement.csv',
    'ap_characteristics': 'spc_school_ap_characteristics.csv',
    'ap_census_placements': 'AP_placements_AP_census.csv',
    'ap_census_reasons': 'AP_placement_reason_AP_census.csv',
    'nurseries': 'spc_nurseries_in_mainstream_schools_api.csv',
    'cross_border': 'spc_cbm.csv',
}

class SchoolDataQuery:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self._cache = {}
    
    def load(self, dataset_key: str, **kwargs) -> pd.DataFrame:
        """Load a dataset with optional dtype hints for memory efficiency."""
        if dataset_key not in DATASETS:
            raise ValueError(f"Unknown dataset: {dataset_key}. Available: {list(DATASETS.keys())}")
        
        if dataset_key in self._cache:
            return self._cache[dataset_key]
        
        filepath = self.data_dir / DATASETS[dataset_key]
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Use appropriate dtypes for memory efficiency
        dtype_hints = self._get_dtype_hints(dataset_key)
        
        df = pd.read_csv(filepath, dtype=dtype_hints, low_memory=False, **kwargs)
        self._cache[dataset_key] = df
        return df
    
    def _get_dtype_hints(self, dataset_key: str) -> Dict[str, str]:
        """Return dtype hints for efficient loading."""
        common_categorical = [
            'time_period', 'time_identifier', 'geographic_level', 'country_code',
            'country_name', 'region_code', 'region_name', 'old_la_code', 'new_la_code',
            'la_name', 'pcon_code', 'pcon_name', 'sex_of_school_description',
            'phase_type_grouping', 'type_of_establishment', 'denomination',
            'admissions_policy', 'urban_rural', 'academy_flag'
        ]
        
        hints = {col: 'category' for col in common_categorical}
        
        # Dataset-specific hints
        if dataset_key == 'age_sex_attendance':
            for i in range(20):
                hints[f'aged_{i}_pupil_count'] = 'Int64'
        
        return hints
    
    def list_datasets(self) -> List[str]:
        return list(DATASETS.keys())
    
    def get_info(self, dataset_key: str) -> Dict[str, Any]:
        df = self.load(dataset_key)
        return {
            'rows': len(df),
            'columns': list(df.columns),
            'dtypes': df.dtypes.to_dict(),
            'memory_mb': df.memory_usage(deep=True).sum() / 1024**2,
            'sample': df.head(3).to_dict('records')
        }
    
    def query(self, dataset_key: str, filters: Dict[str, Any] = None, 
              columns: List[str] = None, groupby: List[str] = None,
              agg: Dict[str, str] = None) -> pd.DataFrame:
        """Query a dataset with filters, column selection, and optional aggregation."""
        df = self.load(dataset_key)
        
        # Apply filters
        if filters:
            for col, val in filters.items():
                if col in df.columns:
                    if isinstance(val, list):
                        df = df[df[col].isin(val)]
                    else:
                        df = df[df[col] == val]
        
        # Select columns
        if columns:
            df = df[columns]
        
        # Group and aggregate
        if groupby and agg:
            df = df.groupby(groupby).agg(agg).reset_index()
        
        return df
    
    def get_la_summary(self, dataset_key: str, la_name: str) -> pd.DataFrame:
        """Get summary for a specific local authority."""
        return self.query(dataset_key, filters={'la_name': la_name})
    
    def get_national_totals(self, dataset_key: str, value_col: str, 
                            group_cols: List[str] = None) -> pd.DataFrame:
        """Get national-level totals."""
        df = self.load(dataset_key)
        df = df[df['geographic_level'] == 'National']
        
        if group_cols:
            return df.groupby(group_cols)[value_col].sum().reset_index()
        return df[[value_col]].sum()

def reduce_ks4_csv(input_path: Path, output_path: Path) -> Dict[str, int]:
    """Write KS4 rows for the selected boroughs and England/London aggregates."""
    if input_path.resolve() == output_path.resolve():
        raise ValueError("The reduced output must be a different file from the source.")

    kept = {"school": 0, "aggregate": 0}
    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError(f"No CSV header found in {input_path}.")
        required = {"geographic_level", "la_name", "country_name"}
        missing = required.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing required KS4 columns: {', '.join(sorted(missing))}")

        with output_path.open("w", encoding="utf-8-sig", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                geography = row["geographic_level"]
                if geography == "School" and row["la_name"] in KS4_BOROUGHS:
                    kept["school"] += 1
                elif geography == "National" and row["country_name"] == "England":
                    kept["aggregate"] += 1
                elif geography == "Regional" and (
                    row.get("region_name") == "London" or row["la_name"] == "London"
                ):
                    kept["aggregate"] += 1
                else:
                    continue
                writer.writerow(row)
    return kept

def main():
    parser = argparse.ArgumentParser(description='Query DfE School Pupils Data')
    parser.add_argument('--list', action='store_true', help='List available datasets')
    parser.add_argument('--info', type=str, help='Show info for a dataset')
    parser.add_argument(
        '--reduce-ks4',
        action='store_true',
        help='Create a smaller KS4 CSV for Bexley, Bromley and Greenwich, retaining England/London aggregates'
    )
    parser.add_argument(
        '--input-csv',
        type=Path,
        default=DATA_DIR / KS4_SOURCE,
        help=f'KS4 source CSV (default: {KS4_SOURCE})'
    )
    parser.add_argument(
        '--reduced-output',
        type=Path,
        default=DATA_DIR / KS4_REDUCED,
        help=f'Reduced KS4 output CSV (default: {KS4_REDUCED})'
    )
    parser.add_argument('--dataset', type=str, help='Dataset to query')
    parser.add_argument('--la', type=str, help='Filter by local authority name')
    parser.add_argument('--phase', type=str, help='Filter by phase type grouping')
    parser.add_argument('--year', type=str, help='Filter by time period (e.g., 202526)')
    parser.add_argument('--columns', type=str, help='Comma-separated columns to show')
    parser.add_argument('--groupby', type=str, help='Comma-separated columns to group by')
    parser.add_argument('--sum', type=str, help='Column to sum (requires --groupby)')
    parser.add_argument('--head', type=int, default=20, help='Number of rows to show')
    parser.add_argument('--output', type=str, help='Output CSV file')
    
    args = parser.parse_args()
    
    query = SchoolDataQuery()

    if args.reduce_ks4:
        counts = reduce_ks4_csv(args.input_csv, args.reduced_output)
        print(f"Saved reduced KS4 data to {args.reduced_output}")
        print(f"School rows: {counts['school']:,}")
        print(f"England/London aggregate rows: {counts['aggregate']:,}")
        print(f"Total retained rows: {sum(counts.values()):,}")
        return

    if args.list:
        print("Available datasets:")
        for key, filename in DATASETS.items():
            print(f"  {key:30s} - {filename}")
        return
    
    if args.info:
        info = query.get_info(args.info)
        print(f"Dataset: {args.info}")
        print(f"Rows: {info['rows']:,}")
        print(f"Memory: {info['memory_mb']:.1f} MB")
        print(f"Columns: {', '.join(info['columns'])}")
        print("\nSample data:")
        for row in info['sample']:
            print(row)
        return
    
    if not args.dataset:
        parser.error("--dataset is required for queries")
    
    filters = {}
    if args.la:
        filters['la_name'] = args.la
    if args.phase:
        filters['phase_type_grouping'] = args.phase
    if args.year:
        filters['time_period'] = args.year
    
    columns = args.columns.split(',') if args.columns else None
    groupby = args.groupby.split(',') if args.groupby else None
    agg = {args.sum: 'sum'} if args.sum and groupby else None
    
    result = query.query(args.dataset, filters=filters, columns=columns, 
                         groupby=groupby, agg=agg)
    
    print(f"Results: {len(result):,} rows")
    print(result.head(args.head).to_string(index=False))
    
    if args.output:
        result.to_csv(args.output, index=False)
        print(f"\nSaved to {args.output}")

if __name__ == '__main__':
    main()