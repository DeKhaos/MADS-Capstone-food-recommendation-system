import pandas as pd
from sklearn.model_selection import train_test_split

# File name (same directory as script)
INPUT_FILE = "recipes_1_cleaned_scaled.csv"

# Output files
TRAIN_FILE = "/data/train.csv"
VAL_FILE = "/data/val.csv"
TEST_FILE = "/data/test.csv"

# Load dataset
df = pd.read_csv(INPUT_FILE)
print(f"Loaded {len(df)} rows")

# Optional: drop duplicates if you have recipe_id
if "recipe_id" in df.columns:
    df = df.drop_duplicates(subset=["recipe_id"])
    print(f"After deduplication: {len(df)} rows")

# First split: 60% train, 40% temp
train_df, temp_df = train_test_split(
    df,
    test_size=0.4,
    random_state=42,
    shuffle=True
)

# Second split: 20% val, 20% test
val_df, test_df = train_test_split(
    temp_df,
    test_size=0.5,
    random_state=42,
    shuffle=True
)

# Save splits
train_df.to_csv(TRAIN_FILE, index=False)
val_df.to_csv(VAL_FILE, index=False)
test_df.to_csv(TEST_FILE, index=False)

print("\nSplit complete:")
print(f"Train: {len(train_df)} rows -> {TRAIN_FILE}")
print(f"Validation: {len(val_df)} rows -> {VAL_FILE}")
print(f"Test: {len(test_df)} rows -> {TEST_FILE}")