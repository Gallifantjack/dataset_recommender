#!/bin/bash

# Array of datasets for the -n parameter
datasets=("mimic" "eicu" "hirid")

# Array of models for the -m parameter
models=("GRU" "LGBMClassifier" "LSTM" "LogisticRegression" "TCN")

# Array of datasets that models were trained on
trained_datasets=("miiv" "eicu" "hirid" "aumc")

# Log the start of the script
echo "Starting the ICU Benchmarks Evaluation Script..."
echo "Evaluating models on datasets: ${datasets[*]}"
echo "Models to be evaluated: ${models[*]}"
echo "Trained datasets for the models: ${trained_datasets[*]}"
echo "---------------------------------------------"

# Loop over each dataset and model combination
for trained_dataset in "${trained_datasets[@]}"
do
    echo "Starting evaluations for models trained on dataset: $trained_dataset"
    
    for dataset in "${datasets[@]}"
    do
        echo "Evaluating on dataset: $dataset for models trained on: $trained_dataset"
        
        for model in "${models[@]}"
        do
            # Log current model and dataset combination
            echo "Starting evaluation for model: $model on dataset: $dataset (trained on: $trained_dataset)"
            
            # Execute the icu-benchmarks evaluate command and log the details
            echo "Running icu-benchmarks evaluate with model: $model on dataset: $dataset..."
            icu-benchmarks evaluate \
                -d ../../../data/mortality24/"$dataset" \
                -n "$dataset" \
                -t BinaryClassification \
                -tn Mortality24 \
                -m "$model" \
                --generate_cache \
                -s 2222 \
                -l ../yaib_logs \
                -sn "$trained_dataset" \
                --source-dir ../YAIB-models/mortality24/"$trained_dataset"/miiv_mortality24_"$model"_repetition_0_fold_0_model/
                --samples 100
            # Log completion of the evaluation for the current model
            echo "Completed evaluation for model: $model on dataset: $dataset (trained on: $trained_dataset)"
        done
        
        # Log the completion of all models for the current dataset
        echo "Finished all model evaluations on dataset: $dataset for models trained on: $trained_dataset"
    done
    
    # Log the completion of all datasets for the current trained dataset
    echo "Finished all evaluations for models trained on: $trained_dataset"
    echo "---------------------------------------------"
done

# Log the end of the script
echo "ICU Benchmarks Evaluation Script completed successfully."
