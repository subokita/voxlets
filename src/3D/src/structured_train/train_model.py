'''
This script brings together all the structured data and trains a RF on them
'''

import os
import numpy as np
import scipy.io
from sklearn.ensemble import RandomForestRegressor
import cPickle as pickle
import timeit
import yaml
import paths

small_model = True # if true, then only load a few of the models (v quick, good for testing)
overwrite = True  # if true, then overwrite models if they already exist

if small_model:
	print "Warning - using small dataset (don't use for final model training)"
	combined_features_path = paths.combined_train_features_small
	rf_folder_path = paths.rf_folder_path_small
else:
	combined_features_path = paths.combined_train_features
	rf_folder_path = paths.rf_folder_path

def resample_inputs(X, Y, num_samples):
	'''
	returns exactly num_samples items from X and Y. 
	Samples without replacement if num_samples < number of data points
	'''
	assert(X.shape[0]==len(Y))
	np.random.seed(1)

	if len(Y) < num_samples:
		# sample with replacement
		idxs = np.random.randint(0, len(Y), num_samples)
	else:
		# sample without replacment
		idxs = np.random.permutation(len(Y))[0:num_samples]

	return X[idxs,:], Y[idxs]


# loading the data
train_data = scipy.io.loadmat(combined_features_path)

# looping over each model from the config file
all_models = yaml.load(open(paths.model_config, 'r'))

for modeloption in all_models:

	rfmodel_path = rf_folder_path + modeloption['name'] + '.pkl'
	if not overwrite and os.path.isfile(rfmodel_path):
		print modeloption['name'] + " already exists ... skipping"
		continue
	
	print "Training model " + modeloption['name']

	number_trees = modeloption['trees']
	num_samples = modeloption['number_samples']

	if small_model and num_samples > 10000:
		print "On small model option, so skipping models with many features"
		continue

	X = [train_data[feature] for feature in modeloption['features']]
	X = np.concatenate(X, axis=1)
	Y = train_data['Y'].flatten()

	print "Before resampling..."
	print "X shape is " + str(X.shape)
	print "Y shape is " + str(Y.shape)

	# Here do some subsampling to reduce the size of the input datasets...
	X, Y = resample_inputs(X, Y, num_samples)

	print "After resampling..."
	print "X shape is " + str(X.shape)
	print "Y shape is " + str(Y.shape)

	# training the forest
	print "Training forest..."
	tic = timeit.default_timer()
	clf = RandomForestRegressor(n_estimators=number_trees,n_jobs=3,random_state=1,max_depth=20)
	clf.fit(X,Y)

	print "Saving to disk..."
	pickle.dump(clf, open(rfmodel_path, "wb") )
	print 'Done training in ' + str(timeit.default_timer() - tic)
