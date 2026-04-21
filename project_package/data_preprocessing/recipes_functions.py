from pathlib import Path

from loguru import logger
from tqdm import tqdm
import typer

from project_package.config import PROCESSED_DATA_DIR

# Data Cleaning for Recipe Dataset
import pandas as pd
import numpy as np
import re
import os
import kagglehub as kagglehub

from difflib import SequenceMatcher
from collections import Counter



app = typer.Typer()


@app.command()
def main(
    # ---- REPLACE DEFAULT PATHS AS APPROPRIATE ----
    input_path: Path = PROCESSED_DATA_DIR / "dataset.csv",
    output_path: Path = PROCESSED_DATA_DIR / "features.csv",
    # -----------------------------------------
):
    # ---- REPLACE THIS WITH YOUR OWN CODE ----
    logger.info("Generating features from dataset...")
    for i in tqdm(range(10), total=10):
        if i == 5:
            logger.info("Something happened for iteration 5.")
    logger.success("Features generation complete.")
    # -----------------------------------------


if __name__ == "__main__":
    app()

#review dataset summary
def dataset_summary(df):
    
    def safe_nunique(col):
        try:
            return col.nunique()
        except TypeError:
            return col.astype(str).nunique()
    
    summary = pd.DataFrame({
        "dtype": df.dtypes,
        "missing_count": df.isnull().sum(),
        "missing_pct": (df.isnull().sum() / len(df) * 100).round(2),
        "n_unique": df.apply(safe_nunique)
    }).sort_values(by="missing_count", ascending=False)

    return summary

# fill in missing value function

def fill_na_with_value(df, columns, value=0):
    
    for col in columns:
        if col in df.columns:
            df[col] = df[col].fillna(value)
    
    return df

#reformat columns with c() to list of strings 
def parse_c_vector(x):
    
    if pd.isna(x):
        return []
    
    x = str(x).strip()
    
    if x.startswith("c(") and x.endswith(")"):
        x = x[2:-1]   # remove c( )
        items = re.findall(r'"(.*?)"', x)
        return items
    
    return []

def clean_c_columns(df, columns):

    for col in columns:
        if col in df.columns:
            df[col] = df[col].apply(parse_c_vector)

    return df


#convert prepTime and cookTime to minutes
def iso_to_minutes(x):
    if pd.isna(x):
        return np.nan
    
    x = str(x)
    h = re.search(r"(\d+)H", x)
    m = re.search(r"(\d+)M", x)

    hours = int(h.group(1)) if h else 0
    mins = int(m.group(1)) if m else 0

    return hours * 60 + mins

def add_time_minutes(df, columns):
    for col in columns:
        if col in df.columns:
            df[col + "_Minutes"] = df[col].apply(iso_to_minutes)
    return df

def clean_date_column(df, column):
    if column in df.columns:
        df[column + "_Cleaned"] = pd.to_datetime(df[column], errors="coerce")
    return df


# Ingredient normalization

#	1.	lowercase + strip
#	2.	phrase fixes
#	3.	safe descriptor removal
#	4.	safe singularization
##	5.	curated map
#	6.	optional auto-synonym map
#	7.	final manual correction map
#	8.	deduplicate per recipe


class IngredientNormalizer:
    def __init__(
        self,
        descriptor_words=None,
        phrase_fixes=None,
        ingredient_map=None,
        protected_ingredients=None,
        final_fixes=None,
    ):
        self.descriptor_words = descriptor_words or set()
        self.phrase_fixes = phrase_fixes or {}
        self.ingredient_map = ingredient_map or {}
        self.protected_ingredients = protected_ingredients or set()
        self.final_fixes = final_fixes or {}

    #1st basic cleaning
    def normalize_text(self, text):
        if not isinstance(text, str):
            return ""
        text = text.lower().strip()
        text = re.sub(r"[^a-z\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def remove_descriptors(self, text):
        if not text:
            return ""

        for word in sorted(self.descriptor_words, key=len, reverse=True):
            text = re.sub(rf"\b{re.escape(word)}\b", "", text)

        text = re.sub(r"\s+", " ", text).strip()
        return text

    def simple_singularize(self, text):
        if not isinstance(text, str) or not text:
            return ""

        irregular = {
            "tomatoes": "tomato",
            "potatoes": "potato",
            "leaves": "leaf",
            "halves": "half",
            "wolves": "wolf",
            "knives": "knife",
            "wives": "wife",
            "loaves": "loaf",
            "lives": "life",
            "selves": "self",
            "mushrooms": "mushroom",
            "onions": "onion",
            "cloves": "clove",
            "peppers": "pepper",
            "chiles": "chile",
            "beans": "bean",
            "lentils": "lentil",
            "strawberries": "strawberry",
            "blueberries": "blueberry",
            "raspberries": "raspberry",
            "blackberries": "blackberry",
            "cranberries": "cranberry",
            "cherries": "cherry",
        }

        words = text.split()
        if not words:
            return text

        last = words[-1]

        if last in irregular:
            last = irregular[last]
        elif last.endswith("ies") and len(last) > 3:
            last = last[:-3] + "y"
        elif last.endswith("oes") and len(last) > 3:
            last = last[:-2]
        elif last.endswith("s") and not last.endswith("ss") and len(last) > 3:
            last = last[:-1]

        words[-1] = last
        return " ".join(words)

    #main canonicalization
    def canonicalize_ingredient(self, text):
        if not isinstance(text, str):
            return ""

        text = self.normalize_text(text)

        if text in self.phrase_fixes:
            text = self.phrase_fixes[text]

        text = self.remove_descriptors(text)

        if text in self.phrase_fixes:
            text = self.phrase_fixes[text]

        text = self.simple_singularize(text)

        if text in self.ingredient_map:
            text = self.ingredient_map[text]

        if text in self.final_fixes:
            text = self.final_fixes[text]

        text = re.sub(r"\s+", " ", text).strip()
        return text

    def canonicalize_ingredient_list(self, ingredients):
        if not isinstance(ingredients, list):
            return []

        cleaned = []
        for ing in ingredients:
            canon = self.canonicalize_ingredient(ing)
            if canon:
                cleaned.append(canon)

        return list(dict.fromkeys(cleaned))

    # explode ingredients
    def explode_ingredients(self, df, ingredient_col="RecipeIngredientParts", recipe_id_col="RecipeId"):
        rows = []

        for recipe_id, ingredients in zip(df[recipe_id_col], df[ingredient_col]):
            if isinstance(ingredients, list):
                for ing in ingredients:
                    if isinstance(ing, str) and ing.strip():
                        rows.append({
                            recipe_id_col: recipe_id,
                            "raw_ingredient": ing.strip()
                        })

        return pd.DataFrame(rows)

    # helpers for synonym discovery
    def normalize_for_synonyms(self, text):
        text = self.normalize_text(text)

        if text in self.phrase_fixes:
            text = self.phrase_fixes[text]

        text = self.remove_descriptors(text)

        if text in self.phrase_fixes:
            text = self.phrase_fixes[text]

        text = self.simple_singularize(text)

        if text in self.final_fixes:
            text = self.final_fixes[text]

        return text

    def ingredient_frequency_table(self, ingredient_df, col="normalized"):
        freq = ingredient_df[col].value_counts().reset_index()
        freq.columns = [col, "count"]
        return freq

    def get_head_word(self, text):
        if not isinstance(text, str) or not text.strip():
            return ""
        return text.split()[-1]

    def string_similarity(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    def build_candidate_synonym_pairs(self, freq_table, min_count=20, min_similarity=0.80):
        freq_dict = dict(zip(freq_table["normalized"], freq_table["count"]))
        ingredients = [x for x in freq_table["normalized"] if freq_dict[x] >= min_count]

        candidates = []

        for i in range(len(ingredients)):
            for j in range(i + 1, len(ingredients)):
                a = ingredients[i]
                b = ingredients[j]

                same_head = self.get_head_word(a) == self.get_head_word(b)
                sim = self.string_similarity(a, b)

                if same_head or sim >= min_similarity:
                    candidates.append({
                        "ingredient_a": a,
                        "ingredient_b": b,
                        "count_a": freq_dict[a],
                        "count_b": freq_dict[b],
                        "same_head": same_head,
                        "similarity": round(sim, 3)
                    })

        candidates_df = pd.DataFrame(candidates)

        if not candidates_df.empty:
            candidates_df = candidates_df.sort_values(
                by=["same_head", "similarity", "count_a", "count_b"],
                ascending=[False, False, False, False]
            )

        return candidates_df

    def choose_canonical_by_frequency(self, group, freq_dict):
        group = list(group)
        return max(group, key=lambda x: freq_dict.get(x, 0))

    def build_headword_synonym_map(self, freq_table, min_count=20, max_group_size=10):
        freq_dict = dict(zip(freq_table["normalized"], freq_table["count"]))

        grouped = {}
        for ing in freq_table["normalized"]:
            if freq_dict[ing] >= min_count:
                head = self.get_head_word(ing)
                grouped.setdefault(head, []).append(ing)

        synonym_map = {}

        for head, items in grouped.items():
            items = sorted(items, key=lambda x: freq_dict[x], reverse=True)

            if 1 < len(items) <= max_group_size:
                canonical = self.choose_canonical_by_frequency(items, freq_dict)

                for item in items:
                    if item != canonical:
                        synonym_map[item] = canonical

        return synonym_map

    def filter_synonym_map(self, synonym_map):
        filtered = {}

        for k, v in synonym_map.items():
            if k in self.protected_ingredients or v in self.protected_ingredients:
                continue
            filtered[k] = v

        return filtered

    def apply_synonym_map(self, ingredients, synonym_map):
        if not isinstance(ingredients, list):
            return []

        mapped = []
        for ing in ingredients:
            canon = synonym_map.get(ing, ing)
            if canon:
                mapped.append(canon)

        return list(dict.fromkeys(mapped))

    def apply_final_fixes(self, ingredients):
        if not isinstance(ingredients, list):
            return []

        mapped = [self.final_fixes.get(i, i) for i in ingredients if i]
        return list(dict.fromkeys(mapped))

    #go through full pipeline
    def fit_auto_synonyms(
        self,
        df,
        ingredient_col="RecipeIngredientParts",
        recipe_id_col="RecipeId",
        min_count=30,
        min_similarity=0.80,
        max_group_size=10,
    ):
        ingredient_df = self.explode_ingredients(df, ingredient_col, recipe_id_col)
        ingredient_df["normalized"] = ingredient_df["raw_ingredient"].apply(self.normalize_for_synonyms)

        freq_table = self.ingredient_frequency_table(ingredient_df, "normalized")

        candidate_pairs = self.build_candidate_synonym_pairs(
            freq_table,
            min_count=min_count,
            min_similarity=min_similarity
        )

        auto_synonyms = self.build_headword_synonym_map(
            freq_table,
            min_count=min_count,
            max_group_size=max_group_size
        )

        auto_synonyms_filtered = self.filter_synonym_map(auto_synonyms)

        return {
            "ingredient_df": ingredient_df,
            "freq_table": freq_table,
            "candidate_pairs": candidate_pairs,
            "auto_synonyms": auto_synonyms,
            "auto_synonyms_filtered": auto_synonyms_filtered,
        }

    def transform(self, df, ingredient_col="RecipeIngredientParts"):
        df = df.copy()
        df["ingredients_canonical"] = df[ingredient_col].apply(self.canonicalize_ingredient_list)
        return df

    def transform_with_auto_synonyms(self, df, auto_synonym_map):
        df = df.copy()
        df["ingredients_canonical_auto"] = df["ingredients_canonical"].apply(
            lambda x: self.apply_synonym_map(x, auto_synonym_map)
        )
        df["ingredients_canonical_final"] = df["ingredients_canonical_auto"].apply(
            self.apply_final_fixes
        )
        return df

    # take summaries
    def summarize_ingredients_column(self, df, col="ingredients_canonical_final"):
        total_recipes = len(df)
        ingredient_lists = df[col].dropna()

        total_ingredient_mentions = sum(len(i) for i in ingredient_lists if isinstance(i, list))

        all_ingredients = [
            ing
            for lst in ingredient_lists
            if isinstance(lst, list)
            for ing in lst
        ]

        unique_ingredients = set(all_ingredients)

        print("DATASET SUMMARY")
        print("------------------------")
        print("Total recipes:", total_recipes)
        print("Recipes with ingredient lists:", len(ingredient_lists))
        print("Total ingredient mentions:", total_ingredient_mentions)
        print("Unique ingredients:", len(unique_ingredients))
        if len(ingredient_lists) > 0:
            print("Average ingredients per recipe:",
                  round(total_ingredient_mentions / len(ingredient_lists), 2))

        return all_ingredients

    def ingredient_summary(self, df, col="ingredients_canonical_final", recipe_id_col="RecipeId"):
        ingredient_exploded = df[[recipe_id_col, col]].explode(col)

        summary = (
            ingredient_exploded
            .groupby(col)
            .agg(
                count=(recipe_id_col, "count")
                # recipe_ids=(recipe_id_col, lambda x: list(x))
            )
            .reset_index()
            .sort_values("count", ascending=False)
        )

        return summary
    
    
import pandas as pd
from collections import Counter


class LossyIngredientReducer:
    """
    Reduce sparse ingredient vocabularies by removing or replacing
    ingredients based on recipe-level document frequency.

    match_mode:
        'lt' -> frequency < threshold
        'le' -> frequency <= threshold
        'eq' -> frequency == threshold
        'ge' -> frequency >= threshold
    """

    def __init__(self, col="ingredients_canonical_final"):
        self.col = col
        self.docfreq = None
        self.target_set = set()
        self.threshold = None
        self.match_mode = None

    # internal helpers
    @staticmethod
    def _is_valid_list(x):
        return isinstance(x, list)

    @staticmethod
    def _deduplicate_keep_order(items):
        return list(dict.fromkeys(items))

    @staticmethod
    def _safe_len_list(x):
        return len(x) if isinstance(x, list) else 0

    # dataset summary
    def dataset_level_summary(self, df, col=None):
        """
        Summarize a dataset column containing ingredient lists.
        """
        if col is None:
            col = self.col

        total_recipes = len(df)
        valid_lists = df[col].apply(self._is_valid_list)
        ingredient_lists = df.loc[valid_lists, col]

        total_mentions = sum(len(lst) for lst in ingredient_lists)
        all_ingredients = [ing for lst in ingredient_lists for ing in lst]
        unique_ingredients = len(set(all_ingredients))
        avg_per_recipe = round(total_mentions / len(ingredient_lists), 2) if len(ingredient_lists) > 0 else 0.0

        return {
            "column": col,
            "total_recipes": total_recipes,
            "recipes_with_lists": int(valid_lists.sum()),
            "total_mentions": total_mentions,
            "unique_ingredients": unique_ingredients,
            "avg_ingredients_per_recipe": avg_per_recipe
        }

    def dataset_level_summary_df(self, df, col=None):
        return pd.DataFrame([self.dataset_level_summary(df, col=col)])

    # fit
    def fit(self, df, threshold=5, match_mode="lt", col=None):
        if col is not None:
            self.col = col

        self.threshold = threshold
        self.match_mode = match_mode

        counter = Counter()
        for lst in df[self.col]:
            if isinstance(lst, list):
                counter.update(set(lst))   # document frequency

        self.docfreq = (
            pd.DataFrame(counter.items(), columns=["ingredient", "recipe_count"])
            .sort_values(["recipe_count", "ingredient"], ascending=[False, True])
            .reset_index(drop=True)
        )

        if match_mode == "lt":
            mask = self.docfreq["recipe_count"] < threshold
        elif match_mode == "le":
            mask = self.docfreq["recipe_count"] <= threshold
        elif match_mode == "eq":
            mask = self.docfreq["recipe_count"] == threshold
        elif match_mode == "ge":
            mask = self.docfreq["recipe_count"] >= threshold
        else:
            raise ValueError("match_mode must be one of: 'lt', 'le', 'eq', 'ge'")

        self.target_set = set(self.docfreq.loc[mask, "ingredient"])
        return self

    # transform one list
    def transform_list(
        self,
        ingredients,
        mode="remove",
        replacement_token="other_target_ingredient",
        min_remaining=1,
        keep_original_if_empty=True
    ):
        if not isinstance(ingredients, list):
            return []

        original = self._deduplicate_keep_order(ingredients)

        if mode == "remove":
            cleaned = [x for x in original if x not in self.target_set]
            cleaned = self._deduplicate_keep_order(cleaned)

            if len(cleaned) < min_remaining:
                return original if keep_original_if_empty else cleaned

            return cleaned

        elif mode == "replace":
            cleaned = [
                replacement_token if x in self.target_set else x
                for x in original
            ]
            cleaned = self._deduplicate_keep_order(cleaned)

            if len(cleaned) < min_remaining:
                return original if keep_original_if_empty else cleaned

            return cleaned

        else:
            raise ValueError("mode must be 'remove' or 'replace'")

    # transform dataframe
    def transform(
        self,
        df,
        mode="remove",
        replacement_token="other_target_ingredient",
        min_remaining=1,
        keep_original_if_empty=True,
        new_col=None
    ):
        if self.docfreq is None:
            raise ValueError("You must call fit() before transform().")

        df_out = df.copy()

        if new_col is None:
            suffix = "removed" if mode == "remove" else "replaced"
            op = f"{self.match_mode}_{self.threshold}" if self.threshold is not None else "lossy"
            new_col = f"{self.col}_{op}_{suffix}"

        df_out[new_col] = df_out[self.col].apply(
            lambda x: self.transform_list(
                x,
                mode=mode,
                replacement_token=replacement_token,
                min_remaining=min_remaining,
                keep_original_if_empty=keep_original_if_empty
            )
        )

        return df_out

    # convenience fit+transform
    def fit_transform(
        self,
        df,
        threshold=5,
        match_mode="lt",
        mode="remove",
        replacement_token="other_target_ingredient",
        min_remaining=1,
        keep_original_if_empty=True,
        new_col=None,
        col=None
    ):
        self.fit(df, threshold=threshold, match_mode=match_mode, col=col)
        return self.transform(
            df,
            mode=mode,
            replacement_token=replacement_token,
            min_remaining=min_remaining,
            keep_original_if_empty=keep_original_if_empty,
            new_col=new_col
        )

    # compare before / after
    def compare_dataset_levels(self, df, new_col):
        before = self.dataset_level_summary(df, self.col)
        after = self.dataset_level_summary(df, new_col)

        rows = []
        metrics = [
            "total_recipes",
            "recipes_with_lists",
            "total_mentions",
            "unique_ingredients",
            "avg_ingredients_per_recipe"
        ]

        for metric in metrics:
            before_val = before[metric]
            after_val = after[metric]

            pct_change = None
            if isinstance(before_val, (int, float)) and before_val != 0:
                pct_change = round((after_val - before_val) / before_val, 4)

            rows.append({
                "metric": metric,
                "before": before_val,
                "after": after_val,
                "pct_change": pct_change
            })

        return pd.DataFrame(rows)

    # threshold evaluation
    def evaluate_thresholds(
        self,
        df,
        thresholds=(2, 3, 5, 7, 10),
        match_mode="le",
        mode="remove",
        replacement_token="other_target_ingredient",
        min_remaining=1,
        keep_original_if_empty=True
    ):
        """
        Evaluate multiple thresholds with recipe-level impact.
        """
        results = []

        base_summary = self.dataset_level_summary(df, self.col)
        base_unique = base_summary["unique_ingredients"]
        total_recipes_before = base_summary["total_recipes"]

        for t in thresholds:
            reducer = LossyIngredientReducer(col=self.col)
            reducer.fit(df, threshold=t, match_mode=match_mode)

            temp_col = "__temp_lossy__"
            temp_df = reducer.transform(
                df,
                mode=mode,
                replacement_token=replacement_token,
                min_remaining=min_remaining,
                keep_original_if_empty=keep_original_if_empty,
                new_col=temp_col
            )

            temp_summary = reducer.dataset_level_summary(temp_df, temp_col)

            changed_mask = temp_df[self.col] != temp_df[temp_col]
            recipes_changed = int(changed_mask.sum())

            results.append({
                "threshold": t,
                "match_mode": match_mode,
                "target_count": len(reducer.target_set),

                "total_recipes_before": total_recipes_before,
                "total_recipes_after": temp_summary["total_recipes"],

                "remaining_unique": temp_summary["unique_ingredients"],
                "unique_reduction_pct": round(
                    (base_unique - temp_summary["unique_ingredients"]) / base_unique, 4
                ) if base_unique else 0,

                "avg_ingredients_per_recipe_before": base_summary["avg_ingredients_per_recipe"],
                "avg_ingredients_per_recipe_after": temp_summary["avg_ingredients_per_recipe"],

                "recipes_changed_count": recipes_changed,
                "recipes_changed_pct": round(recipes_changed / total_recipes_before, 4) if total_recipes_before else 0
            })

        return pd.DataFrame(results)

    # target / kept ingredients
    def get_target_ingredients_df(self):
        if self.docfreq is None:
            raise ValueError("You must call fit() first.")

        return (
            self.docfreq[self.docfreq["ingredient"].isin(self.target_set)]
            .sort_values(["recipe_count", "ingredient"], ascending=[True, True])
            .reset_index(drop=True)
        )

    def get_kept_ingredients_df(self):
        if self.docfreq is None:
            raise ValueError("You must call fit() first.")

        return (
            self.docfreq[~self.docfreq["ingredient"].isin(self.target_set)]
            .sort_values(["recipe_count", "ingredient"], ascending=[False, True])
            .reset_index(drop=True)
        )
        
        
def apply_multiple_thresholds(df, col, thresholds, mode="replace"):
    df_out = df.copy()
    reducer = LossyIngredientReducer(col=col)

    for t in thresholds:
        reducer.fit(df_out, threshold=t, match_mode="le")
        new_col = f"{col}_le_{t}_{mode}"
        
        df_out = reducer.transform(
            df_out,
            mode=mode,
            new_col=new_col
        )

    return df_out

#WHO standard 

def add_energy_and_who_flags(
    df: pd.DataFrame,
    calories_col="Calories",
    fat_col="FatContent",
    satfat_col="SaturatedFatContent",
    carbs_col="CarbohydrateContent",
    protein_col="ProteinContent",
    sodium_col="SodiumContent",
    who_sodium_mg_limit=667  # per-serving proxy instead of full-day 2000 mg 2000mg/3
) -> pd.DataFrame:
    """
    Adds macro-energy columns, % energy from fat/sat fat,
    WHO compliance flags, and a WHO-based score.
    Assumes nutrient values are per serving.
    """
    df = df.copy()

    needed = [calories_col, fat_col, satfat_col, carbs_col, protein_col, sodium_col]
    for col in needed:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Energy from macros (kcal)
    df["EnergyFromFat"] = df[fat_col] * 9
    df["EnergyFromSaturatedFat"] = df[satfat_col] * 9
    df["EnergyFromCarbs"] = df[carbs_col] * 4
    df["EnergyFromProtein"] = df[protein_col] * 4

    # Avoid divide-by-zero
    denom = df[calories_col].replace({0: np.nan})

    df["SaturatedFatPercentEnergy"] = df["EnergyFromSaturatedFat"] / denom * 100
    df["FatPercentEnergy"] = df["EnergyFromFat"] / denom * 100

    # WHO-style compliance flags
    df["WHO_SatFat_Compliant"] = df["SaturatedFatPercentEnergy"] < 10
    df["WHO_Fat_Compliant"] = df["FatPercentEnergy"] < 30
    df["WHO_Sodium_Compliant"] = df[sodium_col] < who_sodium_mg_limit

    # WHO score: 0 to 3
    flags = ["WHO_SatFat_Compliant", "WHO_Fat_Compliant", "WHO_Sodium_Compliant"]
    df["WHO_Score"] = df[flags].fillna(False).astype(int).sum(axis=1)

    # Optional label
    df["WHO_Healthy"] = df["WHO_Score"] >= 2

    return df


#UK FSA standard
def add_fsa_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in [
        "Calories", "SugarContent", "SaturatedFatContent",
        "SodiumContent", "FiberContent", "ProteinContent"
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Energy_kJ"] = df["Calories"] * 4.184

    def fsa_bins(x, bins):
        if pd.isna(x):
            return np.nan
        return sum(x > b for b in bins)

    df["A_score"] = (
        df["Energy_kJ"].apply(lambda x: fsa_bins(x, [335,670,1005,1340,1675,2010,2345,2680,3015,3350])) +
        df["SugarContent"].apply(lambda x: fsa_bins(x, [4.5,9,13.5,18,22.5,27,31,36,40,45])) +
        df["SaturatedFatContent"].apply(lambda x: fsa_bins(x, [1,2,3,4,5,6,7,8,9,10])) +
        df["SodiumContent"].apply(lambda x: fsa_bins(x, [90,180,270,360,450,540,630,720,810,900]))
    )

    df["C_score"] = (
        df["FiberContent"].apply(lambda x: fsa_bins(x, [0.9,1.9,2.8,3.7,4.7])) +
        df["ProteinContent"].apply(lambda x: fsa_bins(x, [1.6,3.2,4.8,6.4,8.0]))
    )

    df["FSA_Score"] = df["A_score"] - df["C_score"]
    df["FSA_Healthy"] = df["FSA_Score"] < 4

    return df

def safe_parse(x):
    if pd.isna(x):
        return None
    if isinstance(x, dict):
        return x
    if not isinstance(x, str):
        return None

    # remove python2 unicode prefix
    x = re.sub(r"\bu'", "'", x)
    x = re.sub(r'\bu"', '"', x)

    try:
        return ast.literal_eval(x)
    except:
        return None
    
def extract_directions(x):
    parsed = safe_parse(x)
    if isinstance(parsed, dict):
        return parsed.get("directions")
    return None

def flatten_nutrition(nutrition_dict):
    if not isinstance(nutrition_dict, dict):
        return {}

    flat = {}
    for key, value in nutrition_dict.items():
        if isinstance(value, dict):
            flat[key] = value.get("amount")
    return flat


def save_in_chunks_by_size(
    df,
    max_size_mb=100,
    output_dir="data/processed/Recipes",
    file_prefix="recipes_chunk",
):
    # convert to Path object
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = max_size_mb * 1024 * 1024

    current_chunk = []
    current_size = 0
    file_idx = 0

    for _, row in df.iterrows():
        row_df = pd.DataFrame([row])
        row_size = row_df.memory_usage(deep=True).sum()

        # if adding this row exceeds size → save current chunk
        if current_chunk and current_size + row_size > max_bytes:
            chunk_df = pd.concat(current_chunk, ignore_index=True)

            file_path = output_dir / f"{file_prefix}_{file_idx}.csv"
            chunk_df.to_csv(file_path, index=False)

            print(f"Saved: {file_path} ({round(current_size / 1e6, 2)} MB)")

            file_idx += 1
            current_chunk = []
            current_size = 0

        current_chunk.append(row_df)
        current_size += row_size

    # save last chunk
    if current_chunk:
        chunk_df = pd.concat(current_chunk, ignore_index=True)
        file_path = output_dir / f"{file_prefix}_{file_idx}.csv"
        chunk_df.to_csv(file_path, index=False)

        print(f"Saved: {file_path} ({round(current_size / 1e6, 2)} MB)")