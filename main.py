import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from jinja2 import Template
from weasyprint import HTML

load_dotenv()

def read_invoice(path: Path):
    df = pd.read_csv(path)
    print(df)
    return df


def generate_invoice(data, template_path: Path, output_path: Path):
    with open(template_path, 'r') as f:
        template = Template(f.read())

    data["doctor_name"] = os.getenv("DOCTOR_NAME")
    data["practice_phone"] = os.getenv("PRACTICE_PHONE")
    data["practice_email"] = os.getenv("PRACTICE_EMAIL")
    data["practice_address"] = os.getenv("PRACTICE_ADDRESS").replace("\\n", "\n")
    data["practice_number"] = os.getenv("PRACTICE_NUMBER")
    data["mp_number"] = os.getenv("MP_NUMBER")

    data["bank_name"] = os.getenv("BANK_NAME")
    data["bank_account"] = os.getenv("BANK_ACCOUNT")
    data["bank_code"] = os.getenv("BANK_CODE")

    html_out = template.render(**data)
    HTML(string=html_out).write_pdf(output_path)
    print(f"Invoice generated at {output_path}")


def main():
    data = read_invoice(Path(os.getcwd()) / "invoices" / "test.csv")
    generate_invoice(data, Path('invoice_template.html'), Path('output/invoice.pdf'))


if __name__ == "__main__":
    main()
