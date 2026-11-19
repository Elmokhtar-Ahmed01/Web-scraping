import re
import time

import pandas as pd

INPUT_FILE = "amazon_keyboards.csv"
OUTPUT_XLSX = "amazon_keyboards_clean.xlsx"
OUTPUT_CSV = "amazon_keyboards_clean.csv"

KNOWN_BRANDS = [
    "Redragon",
    "T-DAGGER",
    "AULA",
    "EPOMAKER",
    "ONIKUMA",
    "Onkuma",
    "FANTECH",
    "Aigo",
    "ATTACK SHARK",
    "JeDEL",
    "Logitech",
    "Razer",
    "HyperX",
    "Corsair",
    "SteelSeries",
    "Keychron",
    "Royal Kludge",
    "Havit",
    "Lenovo",
    "Asus",
    "MSI",
    "Dell",
    "HP",
    "A4Tech",
    "Rapoo",
    "Cooler Master",
    "Zero",
    "Porodo",
    "Xiaomi",
]
GENERIC_FIRST_WORDS = {
    "mechanical",
    "gaming",
    "wireless",
    "wired",
    "rgb",
    "keyboard",
    "for",
    "usb",
    "full",
    "compact",
    "led",
    "tkl",
}
MODEL_PATTERN = re.compile(r"\b([A-Z]{1,5}-?\d{2,4}[A-Z0-9]*)\b")


def extract_brand(name):
    for brand in KNOWN_BRANDS:
        if re.search(rf"\b{re.escape(brand)}\b", name, flags=re.IGNORECASE):
            return brand.upper()
    first = re.sub(r"[^\w\-]", "", name.split()[0]) if name.split() else ""
    if not first or first.lower() in GENERIC_FIRST_WORDS or any(c.isdigit() for c in first):
        return "UNKNOWN"
    return first.upper()


def extract_model(name):
    match = MODEL_PATTERN.search(name)
    return match.group(1) if match else ""


def normalize_name(name):
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()[:60]


def save(df):
    for path, writer in (
        (OUTPUT_XLSX, lambda p: df.to_excel(p, index=False, engine="openpyxl")),
        (OUTPUT_CSV, lambda p: df.to_csv(p, index=False, encoding="utf-8-sig")),
    ):
        try:
            writer(path)
        except PermissionError:
            fallback = path.replace("_clean", f"_clean_{int(time.time())}")
            writer(fallback)
            print(f"{path} is open. Saved to {fallback} instead.")


def main():
    df = pd.read_csv(INPUT_FILE, dtype={"ASIN": str})
    total_in = len(df)

    sponsored_removed = 0
    if "Sponsored" in df.columns:
        mask = df["Sponsored"].astype(str).str.lower().eq("true")
        sponsored_removed = int(mask.sum())
        df = df[~mask].drop(columns=["Sponsored"])
    else:
        print("No 'Sponsored' column in input (re-scrape with the updated scraper to get it).")

    df = df.drop_duplicates("ASIN").reset_index(drop=True)

    df["Brand"] = df["Product Name"].apply(extract_brand)
    df["Model"] = df["Product Name"].apply(extract_model)
    df["Group Key"] = [
        f"{b}|{m}" if m else f"name|{normalize_name(n)}"
        for b, m, n in zip(df["Brand"], df["Model"], df["Product Name"])
    ]

    grouped = df.groupby("Group Key", sort=False)
    df["Variants"] = grouped["ASIN"].transform("count")
    df["Min Price (EGP)"] = grouped["Price (EGP)"].transform("min")
    df["Max Price (EGP)"] = grouped["Price (EGP)"].transform("max")

    clean = df.drop_duplicates("Group Key", keep="first").drop(columns=["Group Key"])
    clean = clean[
        [
            "ASIN",
            "Brand",
            "Model",
            "Product Name",
            "Price (EGP)",
            "Min Price (EGP)",
            "Max Price (EGP)",
            "Variants",
            "Rating",
            "Product Link",
        ]
    ].reset_index(drop=True)

    save(clean)

    print(f"Rows in: {total_in}")
    print(f"Sponsored removed: {sponsored_removed}")
    print(f"Unique products after merging variants: {len(clean)}")
    print(f"Missing price: {int(clean['Price (EGP)'].isna().sum())}")
    print(f"Missing rating: {int(clean['Rating'].isna().sum())}")
    print(f"Unknown brand: {int((clean['Brand'] == 'UNKNOWN').sum())}")
    print(f"No model detected: {int((clean['Model'] == '').sum())}")
    print(clean.head(10).to_string())


if __name__ == "__main__":
    main()