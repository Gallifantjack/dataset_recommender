#!/bin/bash

# Arrays for datasets and models
datasets=("mimic" "eicu" "hirid")
models=("GRU" "LGBMClassifier" "LSTM" "LogisticRegression" "TCN")
trained_datasets=("miiv" "eicu" "hirid" "aumc")
finetune_samples=(100 500 1000 2000 4000 6000 8000 10000 12000)

# Log the start of the script
echo "Starting the ICU Benchmarks Finetuning and Evaluation Script..."
echo "Datasets for finetuning and evaluation: ${datasets[*]}"
echo "Models: ${models[*]}"
echo "Trained datasets (source of pretrained models): ${trained_datasets[*]}"
echo "Finetuning sample sizes: ${finetune_samples[*]}"
echo "---------------------------------------------"

# Loop over each trained dataset (source of pretrained model)
for source_dataset in "${trained_datasets[@]}"
do
    echo "Using pretrained models from dataset: $source_dataset"

    # Loop over each model
    for model in "${models[@]}"
    do
        echo "Processing model: $model"
        
        # Loop over each dataset for finetuning
        for finetune_dataset in "${datasets[@]}"
        do
            echo "Finetuning $model on dataset: $finetune_dataset"
            
            # Loop over finetuning sample sizes
            for ft_samples in "${finetune_samples[@]}"
            do
                echo "Finetuning with $ft_samples samples"
                
                # Finetuning command
                icu-benchmarks -ft 0 \
                    -d ../data/mortality24/"$finetune_dataset" \
                    -t BinaryClassification \
                    --log-dir ../yaib_logs_finetune \
                    --tune \
                    --wandb-sweep \
                    -gc \
                    -lc \
                    -sn "$finetune_dataset" \
                    --source-dir ../YAIB-models/mortality24/"$source_dataset"/"${source_dataset}"_mortality24_"$model"_repetition_0_fold_0_model/ \
                    --fine_tune "$ft_samples" \
                    --model "$model" \
                    --seed 1111 \
                    --use_pretrained_imputation None
                
                echo "Finetuning completed for $model (pretrained on $source_dataset) finetuned on $finetune_dataset with $ft_samples samples"
                
                # Evaluation on all datasets
                for eval_dataset in "${datasets[@]}"
                do
                    echo "Evaluating finetuned $model on dataset: $eval_dataset"
                    
                    icu-benchmarks evaluate \
                        -d ../../../data/mortality24/"$eval_dataset" \
                        -n "$eval_dataset" \
                        -t BinaryClassification \
                        -tn Mortality24 \
                        -m "$model" \
                        --generate_cache \
                        --load_cache \
                        -s 2222 \
                        -l ../yaib_logs_evaluate \
                        -sn "${source_dataset}_${finetune_dataset}_ft${ft_samples}" \
                        --source-dir ../yaib_logs_finetune/"${finetune_dataset}_ft${ft_samples}_${model}_finetuned/
                    
                    echo "Evaluation completed for finetuned $model on $eval_dataset"
                done
            done
            
            echo "Completed finetuning and evaluation for $model (pretrained on $source_dataset) finetuned on $finetune_dataset"
            echo "---------------------------------------------"
        done
    done
done