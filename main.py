from pathlib import Path
import os
import pandas as pd


def read_invoice(path: Path):
    df = pd.read_csv(path)
    print(df)


def main():
    read_invoice(Path(os.getcwd()) / "invoices" / "test.csv")


if __name__ == "__main__":
    main()
