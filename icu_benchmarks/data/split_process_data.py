import copy
import logging
import gin
import json
import hashlib
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
import pickle

from sklearn.model_selection import StratifiedKFold, KFold, StratifiedShuffleSplit, ShuffleSplit

from icu_benchmarks.data.preprocessor import Preprocessor, DefaultClassificationPreprocessor
from icu_benchmarks.contants import RunMode
from .constants import DataSplit as Split, DataSegment as Segment, VarType as Var

##########################
# The follow section allows for specific stay_ids to be selected based on gender, age and location through a dict in the gin file under the name "filter_criteria"
def apply_filters(data, filter_criteria, vars):
    logging.info(f"Applying filters: {filter_criteria}")
    if filter_criteria is None:
        logging.info("No filter criteria provided, returning original data")
        return data

    id_column = vars[Var.group]
    logging.debug(f"Using ID column: {id_column}")

    filtered_stay_ids = set(data[Segment.outcome][id_column])
    logging.info(f"Initial number of stay IDs: {len(filtered_stay_ids)}")

    if 'age' in filter_criteria:
        min_age, max_age = filter_criteria['age']
        logging.debug(f"Filtering by age: min={min_age}, max={max_age}")
        age_filtered_ids = set(filter_by_age(data[Segment.static], min_age, max_age, id_column))
        filtered_stay_ids &= age_filtered_ids
        logging.info(f"After age filter, number of stay IDs: {len(filtered_stay_ids)}")

    if 'sex' in filter_criteria:
        gender = filter_criteria['sex']
        logging.debug(f"Filtering by gender: {gender}")
        gender_filtered_ids = set(filter_by_gender(data[Segment.static], gender, id_column))
        filtered_stay_ids &= gender_filtered_ids
        logging.info(f"After gender filter, number of stay IDs: {len(filtered_stay_ids)}")

    if 'region' in filter_criteria:
        region = filter_criteria['region']
        logging.debug(f"Filtering by region: {region}")
        region_filtered_ids = set(filter_by_region(region, data[Segment.static], data[Segment.hospital], id_column))
        filtered_stay_ids &= region_filtered_ids
        logging.info(f"After region filter, number of stay IDs: {len(filtered_stay_ids)}")

    # Apply the filtered stay_ids to all segments
    for segment in data:
        original_count = len(data[segment])
        data[segment] = data[segment][data[segment][id_column].isin(filtered_stay_ids)]
        filtered_count = len(data[segment])
        logging.info(f"Filtered {segment}: {original_count} -> {filtered_count} rows")

    return data

def filter_by_age(demographic_data, min_age, max_age, id_column):
    logging.info(f"Age filter input shape: {demographic_data.shape}")
    filtered_data = demographic_data[(demographic_data["age"] >= min_age) & (demographic_data["age"] <= max_age)]
    logging.info(f"Age filter output shape: {filtered_data.shape}")
    return filtered_data[id_column].tolist()

def filter_by_gender(demographic_data, gender, id_column):
    logging.info(f"Gender filter input shape: {demographic_data.shape} and {gender}")
    filtered_data = demographic_data[demographic_data["sex"] == gender]
    logging.info(f"Gender filter output shape: {filtered_data.shape}")
    return filtered_data[id_column].tolist()

def filter_by_region(region, patients_df, hospital_df, id_column):
    logging.info(f"Region filter input shapes: patients={patients_df.shape}, hospitals={hospital_df.shape}")
    merged_df = pd.merge(patients_df, hospital_df, on='hospitalid', how='inner')
    logging.info(f"Merged dataframe shape: {merged_df.shape}")
    region_filtered_df = merged_df[merged_df['region'] == region]
    logging.info(f"Region filter output shape: {region_filtered_df.shape}")
    return region_filtered_df[id_column].tolist()

#####################

@gin.configurable("preprocess")
def preprocess_data(
    data_dir: Path,
    file_names: dict[str] = gin.REQUIRED,
    preprocessor: Preprocessor = DefaultClassificationPreprocessor,
    use_static: bool = True,
    vars: dict[str] = gin.REQUIRED,
    seed: int = 42,
    debug: bool = False,
    cv_repetitions: int = 5,
    repetition_index: int = 0,
    cv_folds: int = 5,
    train_size: int = None,
    load_cache: bool = False,
    generate_cache: bool = False,
    fold_index: int = 0,
    pretrained_imputation_model: str = None,
    complete_train: bool = False,
    runmode: RunMode = RunMode.classification,
    filter_criteria: dict = None, #new 
) -> dict[dict[pd.DataFrame]]:
    """Perform loading, splitting, imputing and normalising of task data.

    Args:
        use_static: Whether to use static features (for DL models).
        complete_train: Whether to use all data for training/validation.
        runmode: Run mode. Can be one of the values of RunMode
        preprocessor: Define the preprocessor.
        data_dir: Path to the directory holding the data.
        file_names: Contains the parquet file names in data_dir.
        vars: Contains the names of columns in the data.
        seed: Random seed.
        debug: Load less data if true.
        cv_repetitions: Number of times to repeat cross validation.
        repetition_index: Index of the repetition to return.
        cv_folds: Number of folds to use for cross validation.
        train_size: Fixed size of train split (including validation data).
        load_cache: Use cached preprocessed data if true.
        generate_cache: Generate cached preprocessed data if true.
        fold_index: Index of the fold to return.
        pretrained_imputation_model: pretrained imputation model to use. if None, standard imputation is used.
        filter_criteria: A dictionary specifying filtering criteria. Can include 'age' (tuple of min and max age),
                     'sex' (string), and 'region' (string).
                     
    Returns:
        Preprocessed data as DataFrame in a hierarchical dict with features type (STATIC) / DYNAMIC/ OUTCOME
            nested within split (train/val/test).
    """

    logging.info(f"\t -------------- Complete Gin configuration --------------")
    logging.info(gin.config_str())

    cache_dir = data_dir / "cache"

    if not use_static:
        file_names.pop(Segment.static)
        vars.pop(Segment.static)

    dumped_file_names = json.dumps(file_names, sort_keys=True)
    dumped_vars = json.dumps(vars, sort_keys=True)

    cache_filename = f"s_{seed}_r_{repetition_index}_f_{fold_index}_t_{train_size}_d_{debug}"

    logging.log(logging.INFO, f"Using preprocessor: {preprocessor.__name__}")
    preprocessor = preprocessor(use_static_features=use_static, save_cache=data_dir / "preproc" / (cache_filename + "_recipe"))
    if isinstance(preprocessor, DefaultClassificationPreprocessor):
        preprocessor.set_imputation_model(pretrained_imputation_model)

    hash_config = hashlib.md5(f"{preprocessor.to_cache_string()}{dumped_file_names}{dumped_vars}".encode("utf-8"))
    cache_filename += f"_{hash_config.hexdigest()}"
    cache_file = cache_dir / cache_filename

    if load_cache:
        if cache_file.exists():
            with open(cache_file, "rb") as f:
                logging.info(f"Loading cached data from {cache_file}.")
                return pickle.load(f)
        else:
            logging.info(f"No cached data found in {cache_file}, loading raw features.")
    
    # Read parquet files into pandas dataframes and remove the parquet file from memory
    logging.info(f"Loading data from directory {data_dir.absolute()}")
    data = {f: pq.read_table(data_dir / file_names[f]).to_pandas(self_destruct=True) for f in file_names.keys()}
    
    # Apply filters if specified
    if filter_criteria:
        logging.info(f"\t --------- Demographic segmentation ---------")
        logging.info(f"{filter_criteria}.")
        data = apply_filters(data, filter_criteria, vars)
        

    # Generate the splits
    logging.info("Generating splits.")
    if not complete_train:
        data = make_single_split(
            data,
            vars,
            cv_repetitions,
            repetition_index,
            cv_folds,
            fold_index,
            train_size=train_size,
            seed=seed,
            debug=debug,
            runmode=runmode,
        )
    else:
        # If full train is set, we use all data for training/validation
        data = make_train_val(data, vars, train_size=0.8, seed=seed, debug=debug, runmode=runmode)

    # Apply preprocessing
    data = preprocessor.apply(data, vars)

    # Generate cache
    if generate_cache:
        caching(cache_dir, cache_file, data, load_cache)
    else:
        logging.info("Cache will not be saved.")

   
    # Log the size of the data
    if isinstance(data, dict):
        for key, value in data.items():
            logging.info(f"Size of {key} data: {len(value)}")
    elif hasattr(data, '__len__'):
        logging.info(f"Size of data: {len(data)}")
    else:
        logging.info("Unable to determine the size of data.")
    
    logging.info("Finished preprocessing.")
    return data


def make_train_val(
    data: dict[pd.DataFrame],
    vars: dict[str],
    train_size=0.8,
    seed: int = 42,
    debug: bool = False,
    runmode: RunMode = RunMode.classification,
) -> dict[dict[pd.DataFrame]]:
    """Randomly split the data into training and validation sets for fitting a full model.

    Args:
        data: dictionary containing data divided int OUTCOME, STATIC, and DYNAMIC.
        vars: Contains the names of columns in the data.
        train_size: Fixed size of train split (including validation data).
        seed: Random seed.
        debug: Load less data if true.
    Returns:
        Input data divided into 'train', 'val', and 'test'.
    """
    # ID variable
    id = vars[Var.group]

    # Get stay IDs from outcome segment
    stays = pd.Series(data[Segment.outcome][id].unique(), name=id)

    if debug:
        # Only use 1% of the data
        stays = stays.sample(frac=0.01, random_state=seed)

    # If there are labels, and the task is classification, use stratified k-fold
    if Var.label in vars and runmode is RunMode.classification:
        # Get labels from outcome data (takes the highest value (or True) in case seq2seq classification)
        labels = data[Segment.outcome].groupby(id).max()[vars[Var.label]].reset_index(drop=True)
        if train_size:
            train_val = StratifiedShuffleSplit(train_size=train_size, random_state=seed, n_splits=1)
        train, val = list(train_val.split(stays, labels))[0]
    else:
        # If there are no labels, use random split
        train_val = ShuffleSplit(train_size=train_size, random_state=seed)
        train, val = list(train_val.split(stays))[0]

    split = {Split.train: stays.iloc[train], Split.val: stays.iloc[val]}

    data_split = {}

    for fold in split.keys():  # Loop through splits (train / val / test)
        # Loop through segments (DYNAMIC / STATIC / OUTCOME)
        # set sort to true to make sure that IDs are reordered after scrambling earlier
        data_split[fold] = {
            data_type: data[data_type].merge(split[fold], on=id, how="right", sort=True) for data_type in data.keys()
        }
    # Maintain compatibility with test split
    data_split[Split.test] = copy.deepcopy(data_split[Split.val])
    return data_split


def make_single_split(
    data: dict[pd.DataFrame],
    vars: dict[str],
    cv_repetitions: int,
    repetition_index: int,
    cv_folds: int,
    fold_index: int,
    train_size: int = None,
    seed: int = 42,
    debug: bool = False,
    runmode: RunMode = RunMode.classification,
) -> dict[dict[pd.DataFrame]]:
    """Randomly split the data into training, validation, and test set.

    Args:
        runmode: Run mode. Can be one of the values of RunMode
        data: dictionary containing data divided int OUTCOME, STATIC, and DYNAMIC.
        vars: Contains the names of columns in the data.
        cv_repetitions: Number of times to repeat cross validation.
        repetition_index: Index of the repetition to return.
        cv_folds: Number of folds for cross validation.
        fold_index: Index of the fold to return.
        train_size: Fixed size of train split (including validation data).
        seed: Random seed.
        debug: Load less data if true.

    Returns:
        Input data divided into 'train', 'val', and 'test'.
    """
    # ID variable
    id = vars[Var.group]

    if debug:
        # Only use 1% of the data
        logging.info("Using only 1% of the data for debugging. Note that this might lead to errors for small datasets.")
        data[Segment.outcome] = data[Segment.outcome].sample(frac=0.01, random_state=seed)
    # Get stay IDs from outcome segment
    stays = pd.Series(data[Segment.outcome][id].unique(), name=id)

    # If there are labels, and the task is classification, use stratified k-fold
    if Var.label in vars and runmode is RunMode.classification:
        # Get labels from outcome data (takes the highest value (or True) in case seq2seq classification)
        labels = data[Segment.outcome].groupby(id).max()[vars[Var.label]].reset_index(drop=True)
        if labels.value_counts().min() < cv_folds:
            raise Exception(
                f"The smallest amount of samples in a class is: {labels.value_counts().min()}, "
                f"but {cv_folds} folds are requested. Reduce the number of folds or use more data."
            )
        if train_size:
            outer_cv = StratifiedShuffleSplit(cv_repetitions, train_size=train_size)
        else:
            outer_cv = StratifiedKFold(cv_repetitions, shuffle=True, random_state=seed)
        inner_cv = StratifiedKFold(cv_folds, shuffle=True, random_state=seed)

        dev, test = list(outer_cv.split(stays, labels))[repetition_index]
        dev_stays = stays.iloc[dev]
        train, val = list(inner_cv.split(dev_stays, labels.iloc[dev]))[fold_index]
    else:
        # If there are no labels, or the task is regression, use regular k-fold.
        if train_size:
            outer_cv = ShuffleSplit(cv_repetitions, train_size=train_size)
        else:
            outer_cv = KFold(cv_repetitions, shuffle=True, random_state=seed)
        inner_cv = KFold(cv_folds, shuffle=True, random_state=seed)

        dev, test = list(outer_cv.split(stays))[repetition_index]
        dev_stays = stays.iloc[dev]
        train, val = list(inner_cv.split(dev_stays))[fold_index]

    split = {
        Split.train: dev_stays.iloc[train],
        Split.val: dev_stays.iloc[val],
        Split.test: stays.iloc[test],
    }
    data_split = {}

    for fold in split.keys():  # Loop through splits (train / val / test)
        # Loop through segments (DYNAMIC / STATIC / OUTCOME)
        # set sort to true to make sure that IDs are reordered after scrambling earlier
        data_split[fold] = {
            data_type: data[data_type].merge(split[fold], on=id, how="right", sort=True) for data_type in data.keys()
        }

    return data_split


def caching(cache_dir, cache_file, data, use_cache, overwrite=True):
    if use_cache and (not overwrite or not cache_file.exists()):
        if not cache_dir.exists():
            cache_dir.mkdir()
        cache_file.touch()
        with open(cache_file, "wb") as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
        logging.info(f"Cached data in {cache_file}.")
