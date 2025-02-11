import os
import sys
# sys.path.append("..")
import numpy as np
import tensorflow as tf
import scipy.sparse as sp
from sklearn.metrics import mean_squared_error
from scipy.stats import spearmanr
from tffm import TFFMRegressor
from sys import argv
from utils import concatenate_features, standardize


def main(argv):

    seed = 123 # Random seed
    data_dir = "./data/"

    results_dir=os.path.join(data_dir, "results")
    if os.path.isfile(results_dir):
        results_dir+= '_' + os.getpid()

    if not os.path.exists(results_dir):
        os.mkdir(results_dir)

    results_dir=os.path.join(results_dir, "nested")
    if os.path.isfile(results_dir):
        results_dir+= '_' + os.getpid()

    if not os.path.exists(results_dir):
        os.mkdir(results_dir)



    n_epochs_inner = 100  # Number of epochs in the inner loop
    n_epochs_outer = 200 # Number of epochs in the outer loop
    learning_rate=0.001 # Learning rate of the optimizer
    batch_size = 1024 # Batch size
    init_std=0.01 # Initial standard deviation
    input_type='sparse' # Input type: 'sparse' or 'dense'
    order = 5 # Order of the factorization machine (comboFM)
    nfolds_outer = 10 # Number of folds in the outer loop
    nfolds_inner = 5 # Number of folds in the inner loop

    regparams = [10**2, 10**3, 10**4, 10**5] # Regularization parameter: to be optimized
    ranks = [25, 50, 75, 100] # Rank of the factorization: to be optimized

    # Experiment: 1) new_dose-response_matrix_entries, 2) new_dose-response_matrices, 3) new_drug_combinations"""
    experiment = argv[2]

    id_in = int(argv[1])
    print("\nJob ID: %d" %id_in)

    print('GPU available:')
    print(tf.test.is_gpu_available())

     # Features in position 1: Drug A - Drug B
    features_tensor_1 = ("drug1_concentration__one-hot_encoding.csv", "drug2_concentration__one-hot_encoding.csv", "drug1__one-hot_encoding.csv", "drug2__one-hot_encoding.csv", "cell_lines__one-hot_encoding.csv")
    features_auxiliary_1 = ("drug1_drug2_concentration__values.csv", "drug1__estate_fingerprints.csv", "drug2__estate_fingerprints.csv", "cell_lines__gene_expression.csv")
    X_tensor_1 = concatenate_features(data_dir, features_tensor_1)
    X_auxiliary_1 = concatenate_features(data_dir, features_auxiliary_1)
    X_1 = np.concatenate((X_tensor_1, X_auxiliary_1), axis = 1)

    # Features in position 2: Drug B - Drug A
    features_tensor_2 = ("drug2_concentration__one-hot_encoding.csv", "drug1_concentration__one-hot_encoding.csv", "drug2__one-hot_encoding.csv", "drug1__one-hot_encoding.csv", "cell_lines__one-hot_encoding.csv")
    features_auxiliary_2 =("drug2_drug1_concentration__values.csv", "drug2__estate_fingerprints.csv", "drug1__estate_fingerprints.csv", "cell_lines__gene_expression.csv")
    X_tensor_2 = concatenate_features(data_dir, features_tensor_2)
    X_auxiliary_2 = concatenate_features(data_dir, features_auxiliary_2)
    X_2 = np.concatenate((X_tensor_2, X_auxiliary_2), axis = 1)

    # Concatenate the features from both positions vertically
    X = np.concatenate((X_1, X_2), axis=0)
    print('Dataset shape: {}'.format(X.shape))
    print('Non-zeros rate: {:.05f}'.format(np.mean(X != 0)))
    print('Number of one-hot encoding features: {}'.format(X_tensor_1.shape[1]))
    print('Number of auxiliary features: {}'.format(X_auxiliary_1.shape[1]))
    i_aux = X_tensor_1.shape[1]
    del X_tensor_1, X_auxiliary_1, X_tensor_2, X_auxiliary_2, X_1, X_2

    # Read responses
    y  = np.loadtxt(os.path.join(data_dir, "responses.csv"), delimiter = ",", skiprows = 1)
    y = np.concatenate((y, y), axis=0)

    inner_folds = list(range(1, nfolds_inner+1))
    outer_folds = list(range(1, nfolds_outer+1))

    if not os.path.exists('./cross-validation_folds/%s/'%(experiment)):
        os.mkdir('./cross-validation_folds/%s/'%(experiment))

    outer_fold = outer_folds[id_in]
    te_idx = np.loadtxt('./cross-validation_folds/%s/test_idx_outer_fold-%d.txt'%(experiment, outer_fold)).astype(int)
    tr_idx = np.loadtxt('./cross-validation_folds/%s/train_idx_outer_fold-%d.txt'%(experiment, outer_fold)).astype(int)

    X_tr, X_te, y_tr, y_te = X[tr_idx,:], X[te_idx,:], y[tr_idx], y[te_idx]

    print('Training set shape: {}'.format(X_tr.shape))
    print('Test set shape: {}'.format(X_te.shape))

    CV_RMSE_reg = np.zeros([len(regparams), nfolds_inner])
    CV_RPearson_reg = np.zeros([len(regparams), nfolds_inner])
    CV_RSpearman_reg = np.zeros([len(regparams), nfolds_inner])

    rank = 50 # Fix rank first to 50 while optimizing regularization

    for reg_i in range(len(regparams)):

        reg = regparams[reg_i]

        for inner_fold in inner_folds:
            print("INNER FOLD: %d" %inner_fold)
            print("Rank: %d" %rank)
            print("Regularization: %d" %reg)

            te_idx_CV = np.loadtxt('./cross-validation_folds/%s/test_idx_outer_fold-%d_inner_fold-%d.txt'%(experiment, outer_fold, inner_fold)).astype(int)
            tr_idx_CV = np.loadtxt('./cross-validation_folds/%s/train_idx_outer_fold-%d_inner_fold-%d.txt'%(experiment, outer_fold, inner_fold)).astype(int)
            X_tr_CV, X_te_CV, y_tr_CV, y_te_CV = X[tr_idx_CV,:], X[te_idx_CV,:], y[tr_idx_CV], y[te_idx_CV]
            X_tr_CV, X_te_CV = standardize(X_tr_CV, X_te_CV, i_aux) # i_aux: length of one-hot encoding, not to be standardized

            if input_type == 'sparse':
                X_tr_CV = sp.csr_matrix(X_tr_CV)
                X_te_CV = sp.csr_matrix(X_te_CV)

            model = TFFMRegressor(
                order=order,
                rank=rank,
                n_epochs=n_epochs_inner,
                optimizer=tf.train.AdamOptimizer(learning_rate=learning_rate),
                batch_size = batch_size,
                init_std=init_std,
                reg=reg,
                input_type=input_type,
                seed=seed
            )

            # Train the model
            model.fit(X_tr_CV, y_tr_CV, show_progress=True)

            # Predict
            y_pred_te_CV = model.predict(X_te_CV)

            # Evaluate performance
            RMSE = np.sqrt(mean_squared_error(y_te_CV, y_pred_te_CV))
            CV_RMSE_reg[reg_i, inner_fold-1] = RMSE
            RPearson = np.corrcoef(y_te_CV, y_pred_te_CV)[0,1]
            CV_RPearson_reg[reg_i, inner_fold-1] = RPearson
            RSpearman,_ = spearmanr(y_te_CV, y_pred_te_CV)
            CV_RSpearman_reg[reg_i, inner_fold-1] = RSpearman

            model.destroy()

            print("RMSE: %f\nR_pearson: %f\nR_spearman: %f"%(RMSE, RPearson, RSpearman))

    CV_avg_reg = np.mean(CV_RPearson_reg, axis=1)
    reg_i= np.where(CV_avg_reg == np.max(CV_avg_reg))[0]
    reg = regparams[int(reg_i)]
    np.savetxt(os.path.join(results_dir, '%s/outer_fold-%d_reg_CV_avg_RPearson.txt'%(experiment,outer_fold)), CV_avg_reg)

    CV_RMSE_rank = np.zeros([len(ranks), nfolds_inner])
    CV_RPearson_rank = np.zeros([len(ranks), nfolds_inner])
    CV_RSpearman_rank = np.zeros([len(ranks), nfolds_inner])

    for rank_i in range(len(ranks)):
        rank = ranks[rank_i]
        for inner_fold in inner_folds:

            print("INNER FOLD: %d" %inner_fold)
            print("Rank: %d" %rank)
            print("Regularization: %d" %reg)

            te_idx_CV = np.loadtxt('./cross-validation_folds/%s/test_idx_outer_fold-%d_inner_fold-%d.txt'%(experiment, outer_fold, inner_fold)).astype(int)
            tr_idx_CV = np.loadtxt('./cross-validation_folds/%s/train_idx_outer_fold-%d_inner_fold-%d.txt'%(experiment, outer_fold, inner_fold)).astype(int)

            X_tr_CV, X_te_CV, y_tr_CV, y_te_CV = X[tr_idx_CV,:], X[te_idx_CV,:], y[tr_idx_CV], y[te_idx_CV]
            X_tr_CV, X_te_CV = standardize(X_tr_CV, X_te_CV, i_aux)

            if input_type == 'sparse':
                X_tr_CV = sp.csr_matrix(X_tr_CV)
                X_te_CV = sp.csr_matrix(X_te_CV)

            model = TFFMRegressor(
                order=order,
                rank=rank,
                n_epochs=n_epochs_inner,
                optimizer=tf.train.AdamOptimizer(learning_rate=learning_rate),
                batch_size = batch_size,
                init_std=init_std,
                reg=reg,
                input_type=input_type,
                seed=seed
            )

            # Train the model
            model.fit(X_tr_CV, y_tr_CV, show_progress=True)

            # Predict
            y_pred_te_CV = model.predict(X_te_CV)

            #  Evaluate performance
            RMSE = np.sqrt(mean_squared_error(y_te_CV, y_pred_te_CV))
            CV_RMSE_rank[rank_i, inner_fold-1] = RMSE
            RPearson = np.corrcoef(y_te_CV, y_pred_te_CV)[0,1]
            CV_RPearson_rank[rank_i, inner_fold-1] = RPearson
            RSpearman,_ = spearmanr(y_te_CV, y_pred_te_CV)
            CV_RSpearman_rank[rank_i, inner_fold-1] = RSpearman

            model.destroy()

            print("RMSE: %f\nR_pearson: %f\nR_spearman: %f"%(RMSE, RPearson, RSpearman))


    CV_avg_rank = np.mean(CV_RPearson_rank, axis=1)
    rank_i= np.where(CV_avg_rank == np.max(CV_avg_rank))[0]
    rank= ranks[int(rank_i)]

    np.savetxt(os.path.join(results_dir, '%s/outer_fold-%d_rank_CV_avg_RPearson.txt'%(experiment,outer_fold)), CV_avg_rank)

    X_tr, X_te = standardize(X_tr, X_te, i_aux)

    if input_type == 'sparse':
        X_tr = sp.csr_matrix(X_tr)
        X_te = sp.csr_matrix(X_te)

    model = TFFMRegressor(
        order=order,
        rank=rank,
        n_epochs = n_epochs_outer,
        optimizer=tf.train.AdamOptimizer(learning_rate=learning_rate),
        batch_size = batch_size,
        init_std=init_std,
        reg=reg,
        input_type=input_type,
        seed=seed
    )

    # Train the model
    model.fit(X_tr, y_tr, show_progress=True)

    # Predict
    y_pred_te = model.predict(X_te)


    RPearson = np.corrcoef(y_te, y_pred_te)[0,1]

    print("RMSE: %f\nR_pearson: %f\nR_spearman: %f"%(RMSE, RPearson, RSpearman))



    np.savetxt(os.path.join(results_dir, "%s/outer-fold-%d_y_test_order-%d_rank-%d_reg-%d_%s.txt"%(experiment, outer_fold, order, rank, reg, experiment)), y_te)
    np.savetxt(os.path.join(results_dir, "%s/outer-fold-%d_y_pred_order-%d_rank-%d_reg-%d_%s.txt"%(experiment, outer_fold, order, rank, reg, experiment)), y_pred_te)

    # Save model weights
    weights = model.weights
    for i in range(order):
        np.savetxt(os.path.join(results_dir, '%s/outer-fold-%d_P_order%d_rank-%d_reg-%.1e.txt'%(experiment, outer_fold, i+1, rank, reg)), weights[i])

main(argv)

