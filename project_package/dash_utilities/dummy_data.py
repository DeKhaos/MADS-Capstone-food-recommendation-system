import numpy as np
import pandas as pd

def generate_recipe_statistic(
        filter_info: dict, 
        preferences: dict, 
        n_samples: int = 5, 
        seed=None
    ):
    """
    Generate recipe statistic for dummy display.

    Parameters
    ----------

    filter_info: dict
        The stored filter values.

    preferences: dict
        TThe user profile preferences.

    n_samples: int
        The number of samples to generate.

    seed: int
        Random seed.

    Returns
    ----------

    recipe_list: list[dict]
        The list of generated recipe, each recipe is a dictionary with meta info.
    """

    np.random.seed(seed)

    recipe_indexes = np.arange(1, 1 + n_samples)
    recipe_list = []

    recipe_name = list('QWERTYUIOPASDFGHJKLZXCVBNM')
    recipe_name = ['Recipe ' + char for char in recipe_name]
    
    filter_df = pd.DataFrame(filter_info)
    filter_df = filter_df.loc[~filter_df['filter_value'].isin([None,[]])]  # remove filters that have no selection

    macro_df = filter_df.loc[filter_df['filter_name']=='macro_nutrient']
    macro_empty = macro_df.empty
    n_macro = macro_df.shape[0]
    exact_macro = 'exact' in macro_df['priority_type']

    vitamin_df = filter_df.loc[filter_df['filter_name']=='vitamin_nutrient']
    vitamin_empty = vitamin_df.empty
    n_vitamin = vitamin_df.shape[0]
    exact_vitamin = 'exact' in vitamin_df['priority_type']
    
    mineral_df = filter_df.loc[filter_df['filter_name']=='mineral_nutrient']
    mineral_empty = mineral_df.empty
    n_mineral = mineral_df.shape[0]
    exact_mineral = 'exact' in mineral_df['priority_type']

    if filter_df.shape[0] != 0:
        for recipe_id in recipe_indexes:
            recipe_template = {"badges":[]}  # badge will be list of tuple (filter_name,priority_type,filter_match)
            recipe_template['recipe_id'] = int(recipe_id)
            recipe_template['recipe_name'] = str(np.random.choice(recipe_name,1)[0])
            recipe_template['long_term'] = np.random.rand()
            recipe_template['short_term'] = np.random.rand()
            recipe_template['average_metric'] = 0.7*recipe_template['long_term'] + 0.3*recipe_template['short_term']

            sample_df = filter_df.copy()

            sample_df = sample_df.loc[
                ~sample_df['filter_name'].isin(['macro_nutrient','vitamin_nutrient','mineral_nutrient'])
            ]

            sample_df['filter_match'] = np.random.choice([True,False],sample_df.shape[0])
            sample_df.loc[(sample_df['priority_type'] == 'exact'),'filter_match'] = True

            for _,row in sample_df.iterrows():
                recipe_template['badges'].append((row['filter_name'],row['priority_type'],row['filter_match']))

            if not macro_empty:
                if not exact_macro:
                    match = np.random.randint(0,n_macro + 1)
                    recipe_template['badges'].append(('macro_nutrient','priority',f'{match}/{n_macro}'))
                elif exact_macro and (np.random.rand()>=0.5):
                    recipe_template['badges'].append(('macro_nutrient','exact',True))
                
            if not vitamin_empty:
                if not exact_vitamin:
                    match = np.random.randint(0,n_vitamin + 1)
                    recipe_template['badges'].append(('vitamin_nutrient','priority',f'{match}/{n_vitamin}'))
                elif exact_vitamin and (np.random.rand()>=0.5):
                    recipe_template['badges'].append(('vitamin_nutrient','exact',True))
                
            if not mineral_empty:
                if not exact_mineral:
                    match = np.random.randint(0,n_mineral + 1)
                    recipe_template['badges'].append(('mineral_nutrient','priority',f'{match}/{n_mineral}'))
                elif exact_mineral and (np.random.rand()>=0.5):
                    recipe_template['badges'].append(('mineral_nutrient','exact',True))

            recipe_list.append(recipe_template)

        #TODO: generate match preference

    recipe_list = sorted(recipe_list,key=lambda item_dict:item_dict['average_metric'],reverse=True)

    return recipe_list
