import argparse
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from jinja2 import Template
from weasyprint import HTML

load_dotenv()


def parse_date(date_str: str) -> datetime:
    """Parse DD/MM/YYYY format to datetime."""
    return datetime.strptime(date_str, "%d/%m/%Y")


def sanitize_filename(name: str) -> str:
    """Convert patient name to safe filename."""
    return name.replace(" ", "_").replace("/", "-").replace("\\", "-")


def get_next_invoice_number() -> int:
    """Get the next invoice number from the counter file."""
    counter_file = Path(os.getcwd()) / "invoice_counter.txt"

    if counter_file.exists():
        with open(counter_file, 'r') as f:
            return int(f.read().strip())
    return 1


def save_invoice_number(number: int):
    """Save the last used invoice number to the counter file."""
    counter_file = Path(os.getcwd()) / "invoice_counter.txt"
    with open(counter_file, 'w') as f:
        f.write(str(number))


def read_invoice(path: Path):
    # Specify dtype for columns that should be strings (to preserve leading zeros)
    dtype_spec = {
        'Cell number': str,
        'Next of kin cellphone number': str,
        'Second next of kin cellphone number': str,
        'Medical aid number': str,
        'P. Code': str,
    }
    df = pd.read_csv(path, dtype=dtype_spec)
    return df


def group_by_patient_month(df: pd.DataFrame):
    """Group invoice data by patient name and month."""
    # Parse dates and add year-month column
    df['parsed_date'] = df['Date'].apply(parse_date)
    df['year_month'] = df['parsed_date'].dt.to_period('M')

    # Group by patient name and year-month
    grouped = df.groupby(['Patient name', 'year_month'])

    return [(name, group) for name, group in grouped]


def transform_group_to_invoice_data(group_df: pd.DataFrame, invoice_number: str, year_month):
    """Transform grouped DataFrame into invoice data dict."""
    first_row = group_df.iloc[0]

    data = {
        'patient_name': first_row['Patient name'],
        'patient_address': first_row['Patient address'].replace('\n', '<br>'),
        'patient_cell': first_row['Cell number'],
        'patient_email': first_row['Email'],
    }

    if pd.notna(first_row['Medical aid name']):
        data['medical_aid_name'] = first_row['Medical aid name']
        data['medical_aid_number'] = first_row['Medical aid number']

    if pd.notna(first_row['Next of kin name']):
        data['next_of_kin_name'] = first_row['Next of kin name']
        data['next_of_kin_cell'] = first_row['Next of kin cellphone number']
        if pd.notna(first_row.get('Next of kin email')):
            data['next_of_kin_email'] = first_row['Next of kin email']

    if pd.notna(first_row['Second next of kin name']):
        data['second_next_of_kin_name'] = first_row['Second next of kin name']
        data['second_next_of_kin_cell'] = first_row['Second next of kin cellphone number']
        if pd.notna(first_row.get('Second next of kin email')):
            data['second_next_of_kin_email'] = first_row['Second next of kin email']

    # Generate invoice metadata
    data['invoice_number'] = invoice_number
    data['invoice_date'] = datetime.now().strftime("%d %B %Y")
    data['period'] = year_month.strftime("%B %Y")

    line_items = []
    for _, row in group_df.iterrows():
        line_items.append({
            'date': row['Date'],
            'p_code': row['P. Code'] if pd.notna(row['P. Code']) else '',
            'icd_code': row['ICD Code'] if pd.notna(row['ICD Code']) else '',
        })

    data['line_items'] = line_items

    return data


def generate_invoice(data, template_path: Path, output_path: Path):
    with open(template_path, 'r') as f:
        template = Template(f.read())

    data["doctor_name"] = os.getenv("DOCTOR_NAME")
    data["practice_phone"] = os.getenv("PRACTICE_PHONE")
    data["practice_email"] = os.getenv("PRACTICE_EMAIL")
    data["practice_address"] = os.getenv("PRACTICE_ADDRESS")
    data["practice_number"] = os.getenv("PRACTICE_NUMBER")
    data["mp_number"] = os.getenv("MP_NUMBER")

    data["bank_name"] = os.getenv("BANK_NAME")
    data["bank_account"] = os.getenv("BANK_ACCOUNT")
    data["bank_code"] = os.getenv("BANK_CODE")

    html_out = template.render(**data)
    HTML(string=html_out).write_pdf(output_path)
    print(f"Invoice generated at {output_path}")


def generate_invoices_from_csv(csv_path: Path, output_dir: Path = None, month_filter: str = None):
    """Generate multiple invoices from CSV, grouped by patient and month.

    Args:
        csv_path: Path to the CSV file
        output_dir: Directory to save PDFs (default: output/)
        month_filter: Optional filter in format 'YYYY-MM' (e.g., '2025-11') to only generate invoices for that month
    """
    # Set default output directory
    if output_dir is None:
        output_dir = Path(os.getcwd()) / "output"

    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)

    # Read and group data
    df = read_invoice(csv_path)
    groups = group_by_patient_month(df)

    # Filter by month if specified
    if month_filter:
        groups = [(key, group) for key, group in groups if str(key[1]) == month_filter]
        if not groups:
            print(f"No data found for month {month_filter}")
            return

    print(f"Found {len(groups)} patient-month group(s)")

    # Get starting invoice number
    current_invoice_num = get_next_invoice_number()
    print(f"Starting from invoice number: INV-{current_invoice_num:04d}")

    # Generate invoice for each group
    template_path = Path('invoice_template.html')

    for (patient_name, year_month), group_df in groups:
        # Generate sequential invoice number
        invoice_number = f"INV-{current_invoice_num:04d}"

        # Transform to invoice data
        invoice_data = transform_group_to_invoice_data(group_df, invoice_number, year_month)

        # Generate output filename
        safe_name = sanitize_filename(patient_name)
        ym_str = str(year_month).replace('-', '_')
        output_filename = f"invoice_{safe_name}_{ym_str}.pdf"
        output_path = output_dir / output_filename

        # Generate PDF
        generate_invoice(invoice_data, template_path, output_path)
        print(f"  Generated: {output_filename}")
        current_invoice_num += 1

    save_invoice_number(current_invoice_num)
    print(f"\nCompleted: {len(groups)} invoice(s) in {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate medical invoices from CSV data, grouped by patient and month.'
    )
    parser.add_argument(
        '--month',
        nargs='?',
        default=datetime.now().strftime("%Y-%m"),
        help='Month to generate invoices for in YYYY-MM format (default: current month)'
    )
    parser.add_argument(
        '--csv',
        default=Path(os.getcwd()) / "invoices" / "test.csv",
        type=Path,
        help='Path to the CSV file (default: invoices/test.csv)'
    )
    parser.add_argument(
        '--output',
        default=None,
        type=Path,
        help='Output directory for PDFs (default: output/)'
    )

    args = parser.parse_args()

    print(f"Generating invoices for month: {args.month}")
    generate_invoices_from_csv(args.csv, output_dir=args.output, month_filter=args.month)


if __name__ == "__main__":
    main()
