# comboFM: leveraging multi-way interactions for systematic prediction of drug combination effects

## Overview

comboFM is a machine learning framework for predicting the responses of drug combinations in pre-clinical studies, such as those based on cell lines or patient-derived cells, implemented in Python. 


## Intructions

The cross validation folds for 10x5 nested CV used in the experiments (10 outer folds, 5 inner folds) are stored in *cross-validation_folds*. The folds are designed for duplicated training data in which both of the drugs in a combination are included in both positions such that the symmetry of the drug combinations is taken into account (Drug A - Drug B, Drug B - Drug A), i.e. this informs the algorithm that the combination of drug A with drug B should be considered the same as the combination of drug B with drug A. There are three prediction settings:
1. New dose-response matrix entries: imputing random entries in otherwise known dose-response matrices.
2. New dose-response matrices: making predictions for completely left out dose-response matrices, such that the drug pair has still been observed in other cell lines.
3. New drug combinations: making predictions for completely left out drug combinations, such that the individual drugs are still be observed individually in other combinations.
In all prediction settings, it is assumed that the monotherapy responses of single drugs in a combination are known (i.e. these are included the training set).

*comboFM_nestedCV.py* contains the script for running the full nested cross-validation. The script takes a number identifying the outer CV loop as an input argument, which allows to parallelize the computations using array jobs. One should also pass the name of the prediction scenario as an input argument, which has to be one of the following options: 1) new_dose-response_matrix_entries, 2) new_dose-response_matrices or 3) new_drug_combinations. We recommend using GPUs for more efficient computations.

*comboFM_example.py* contains an example of running comboFM for one outer cross-validation fold with fixed parameters to enable testing without having to run the full nested cross-validation procedure. 


## Dependencies

- numpy
- scikit-learn
- scipy
- tqdm
- tensorflow 1.0+

comboFM also requires installation of TensorFlow-based factorization machine [1], which can be installed e.g. by pip install tffm. 


## Citing comboFM

comboFM is described in the following article:
…


## References 

[1] Mikhail Trofimov and Alexander Novikov. TFFM: TensorFlow implementation of an arbitrary order Factorization Machine, 2016. https://github.com/geffy/tffm.
