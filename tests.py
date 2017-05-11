# -*- coding: utf-8 -*-

"""Copyright 2015-Present Randal S. Olson.

This file is part of the TPOT library.

TPOT is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

TPOT is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with TPOT. If not, see <http://www.gnu.org/licenses/>.

"""

from tpot import TPOTClassifier, TPOTRegressor
from tpot.base import TPOTBase
from tpot.driver import positive_integer, float_range, _get_arg_parser, _print_args
from tpot.export_utils import export_pipeline, generate_import_code, _indent, generate_pipeline_code, get_by_name
from tpot.gp_types import Output_Array
from tpot.gp_deap import mutNodeReplacement

from tpot.operator_utils import TPOTOperatorClassFactory, set_sample_weight
from tpot.config_classifier import classifier_config_dict
from tpot.config_classifier_light import classifier_config_dict_light
from tpot.config_regressor_light import regressor_config_dict_light
from tpot.config_classifier_mdr import tpot_mdr_classifier_config_dict

import numpy as np
import inspect
import random
import subprocess
import sys

from sklearn.datasets import load_digits, load_boston
from sklearn.model_selection import train_test_split, cross_val_score
from deap import creator
from tqdm import tqdm
from nose.tools import assert_raises
from unittest import TestCase
from contextlib import contextmanager
try:
    from StringIO import StringIO
except:
    from io import StringIO

# Set up the MNIST data set for testing
mnist_data = load_digits()
training_features, testing_features, training_classes, testing_classes = \
    train_test_split(mnist_data.data.astype(np.float64), mnist_data.target.astype(np.float64), random_state=42)

# Set up the Boston data set for testing
boston_data = load_boston()
training_features_r, testing_features_r, training_classes_r, testing_classes_r = \
    train_test_split(boston_data.data, boston_data.target, random_state=42)

np.random.seed(42)
random.seed(42)

test_operator_key = 'sklearn.feature_selection.SelectPercentile'
TPOTSelectPercentile, TPOTSelectPercentile_args = TPOTOperatorClassFactory(
    test_operator_key,
    classifier_config_dict[test_operator_key]
)


@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def test_driver():
    """Assert that the TPOT driver output normal result."""
    batcmd = "python -m tpot.driver tests.csv -is , -target class -g 2 -p 2 -os 4 -cv 5 -s 45 -v 1"
    ret_stdout = subprocess.check_output(batcmd, shell=True)
    try:
        ret_val = float(ret_stdout.decode('UTF-8').split('\n')[-2].split(': ')[-1])
    except Exception:
        ret_val = -float('inf')
    assert ret_val > 0.0


class ParserTest(TestCase):
    def setUp(self):
        self.parser = _get_arg_parser()

    def test_default_param(self):
        """Assert that the TPOT driver stores correct default values for all parameters"""
        args = self.parser.parse_args(['tests.csv'])
        self.assertEqual(args.CROSSOVER_RATE, 0.1)
        self.assertEqual(args.DISABLE_UPDATE_CHECK, False)
        self.assertEqual(args.GENERATIONS, 100)
        self.assertEqual(args.INPUT_FILE, 'tests.csv')
        self.assertEqual(args.INPUT_SEPARATOR, '\t')
        self.assertEqual(args.MAX_EVAL_MINS, 5)
        self.assertEqual(args.MUTATION_RATE, 0.9)
        self.assertEqual(args.NUM_CV_FOLDS, 5)
        self.assertEqual(args.NUM_JOBS, 1)
        self.assertEqual(args.OFFSPRING_SIZE, None)
        self.assertEqual(args.OUTPUT_FILE, '')
        self.assertEqual(args.POPULATION_SIZE, 100)
        self.assertEqual(args.RANDOM_STATE, None)
        self.assertEqual(args.SCORING_FN, None)
        self.assertEqual(args.TARGET_NAME, 'class')
        self.assertEqual(args.TPOT_MODE, 'classification')
        self.assertEqual(args.VERBOSITY, 1)

    def test_print_args(self):
        """Assert that _print_args prints correct values for all parameters"""
        args = self.parser.parse_args(['tests.csv'])
        with captured_output() as (out, err):
            _print_args(args)
        output = out.getvalue()
        expected_output = """
TPOT settings:
CONFIG_FILE\t=\t
CROSSOVER_RATE\t=\t0.1
GENERATIONS\t=\t100
INPUT_FILE\t=\ttests.csv
INPUT_SEPARATOR\t=\t\t
MAX_EVAL_MINS\t=\t5
MAX_TIME_MINS\t=\tNone
MUTATION_RATE\t=\t0.9
NUM_CV_FOLDS\t=\t5
NUM_JOBS\t=\t1
OFFSPRING_SIZE\t=\tNone
OUTPUT_FILE\t=\t
POPULATION_SIZE\t=\t100
RANDOM_STATE\t=\tNone
SCORING_FN\t=\taccuracy
TARGET_NAME\t=\tclass
TPOT_MODE\t=\tclassification
VERBOSITY\t=\t1

"""
        self.assertEqual(expected_output, output)


def test_init_custom_parameters():
    """Assert that the TPOT instantiator stores the TPOT variables properly."""
    tpot_obj = TPOTClassifier(
        population_size=500,
        generations=1000,
        offspring_size=2000,
        mutation_rate=0.05,
        crossover_rate=0.9,
        scoring='accuracy',
        cv=10,
        verbosity=1,
        random_state=42,
        disable_update_check=True,
        warm_start=True
    )

    assert tpot_obj.population_size == 500
    assert tpot_obj.generations == 1000
    assert tpot_obj.offspring_size == 2000
    assert tpot_obj.mutation_rate == 0.05
    assert tpot_obj.crossover_rate == 0.9
    assert tpot_obj.scoring_function == 'accuracy'
    assert tpot_obj.cv == 10
    assert tpot_obj.max_time_mins is None
    assert tpot_obj.warm_start is True
    assert tpot_obj.verbosity == 1
    assert tpot_obj._optimized_pipeline is None
    assert tpot_obj._fitted_pipeline is None
    assert not (tpot_obj._pset is None)
    assert not (tpot_obj._toolbox is None)


def test_init_default_scoring():
    """Assert that TPOT intitializes with the correct default scoring function."""
    tpot_obj = TPOTRegressor()
    assert tpot_obj.scoring_function == 'neg_mean_squared_error'

    tpot_obj = TPOTClassifier()
    assert tpot_obj.scoring_function == 'accuracy'


def test_invaild_score_warning():
    """Assert that the TPOT fit function raises a ValueError when the scoring metrics is not available in SCORERS."""
    # Mis-spelled scorer
    assert_raises(ValueError, TPOTClassifier, scoring='balanced_accuray')
    # Correctly spelled
    TPOTClassifier(scoring='balanced_accuracy')


def test_invaild_dataset_warning():
    """Assert that the TPOT fit function raises a ValueError when dataset is not in right format."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=1,
        offspring_size=2,
        generations=1,
        verbosity=0
    )
    # common mistake in classes
    bad_training_classes = training_classes.reshape((1, len(training_classes)))
    assert_raises(ValueError, tpot_obj.fit, training_features, bad_training_classes)


def test_init_max_time_mins():
    """Assert that the TPOT init stores max run time and sets generations to 1000000."""
    tpot_obj = TPOTClassifier(max_time_mins=30, generations=1000)

    assert tpot_obj.generations == 1000000
    assert tpot_obj.max_time_mins == 30


def test_get_params():
    """Assert that get_params returns the exact dictionary of parameters used by TPOT."""
    kwargs = {
        'population_size': 500,
        'generations': 1000,
        'config_dict': 'TPOT light',
        'offspring_size': 2000,
        'verbosity': 1
    }

    tpot_obj = TPOTClassifier(**kwargs)
    # Get default parameters of TPOT and merge with our specified parameters
    initializer = inspect.getargspec(TPOTBase.__init__)
    default_kwargs = dict(zip(initializer.args[1:], initializer.defaults))
    default_kwargs.update(kwargs)
    # update to dictionary instead of input string
    default_kwargs.update({'config_dict': classifier_config_dict_light})
    assert tpot_obj.get_params()['config_dict'] == default_kwargs['config_dict']
    assert tpot_obj.get_params() == default_kwargs


def test_set_params():
    """Assert that set_params returns a reference to the TPOT instance."""
    tpot_obj = TPOTClassifier()
    assert tpot_obj.set_params() is tpot_obj


def test_set_params_2():
    """Assert that set_params updates TPOT's instance variables."""
    tpot_obj = TPOTClassifier(generations=2)
    tpot_obj.set_params(generations=3)

    assert tpot_obj.generations == 3


def test_conf_dict():
    """Assert that TPOT uses the pre-configured dictionary of operators when config_dict is 'TPOT light' or 'TPOT MDR'."""
    tpot_obj = TPOTClassifier(config_dict='TPOT light')
    assert tpot_obj.config_dict == classifier_config_dict_light

    tpot_obj = TPOTClassifier(config_dict='TPOT MDR')
    assert tpot_obj.config_dict == tpot_mdr_classifier_config_dict

    tpot_obj = TPOTRegressor(config_dict='TPOT light')
    assert tpot_obj.config_dict == regressor_config_dict_light

    assert_raises(TypeError, TPOTRegressor, config_dict='TPOT MDR')


def test_conf_dict_2():
    """Assert that TPOT uses a custom dictionary of operators when config_dict is Python dictionary."""
    tpot_obj = TPOTClassifier(config_dict=tpot_mdr_classifier_config_dict)
    assert tpot_obj.config_dict == tpot_mdr_classifier_config_dict


def test_conf_dict_3():
    """Assert that TPOT uses a custom dictionary of operators when config_dict is the path of Python dictionary."""
    tpot_obj = TPOTRegressor(config_dict='tests.conf')
    tested_config_dict = {
        'sklearn.naive_bayes.GaussianNB': {
        },

        'sklearn.naive_bayes.BernoulliNB': {
            'alpha': [1e-3, 1e-2, 1e-1, 1., 10., 100.],
            'fit_prior': [True, False]
        },

        'sklearn.naive_bayes.MultinomialNB': {
            'alpha': [1e-3, 1e-2, 1e-1, 1., 10., 100.],
            'fit_prior': [True, False]
        }
    }
    assert isinstance(tpot_obj.config_dict, dict)
    assert tpot_obj.config_dict == tested_config_dict


def test_random_ind():
    """Assert that the TPOTClassifier can generate the same pipeline with same random seed."""
    tpot_obj = TPOTClassifier(random_state=43)
    pipeline1 = str(tpot_obj._toolbox.individual())
    tpot_obj = TPOTClassifier(random_state=43)
    pipeline2 = str(tpot_obj._toolbox.individual())
    assert pipeline1 == pipeline2


def test_random_ind_2():
    """Assert that the TPOTClassifier can generate the same pipeline export with random seed of 39."""
    tpot_obj = TPOTClassifier(random_state=39)
    tpot_obj._pbar = tqdm(total=1, disable=True)
    pipeline = tpot_obj._toolbox.individual()
    expected_code = """import numpy as np

from sklearn.feature_selection import SelectPercentile, f_classif
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.tree import DecisionTreeClassifier

# NOTE: Make sure that the class is labeled 'class' in the data file
tpot_data = np.recfromcsv('PATH/TO/DATA/FILE', delimiter='COLUMN_SEPARATOR', dtype=np.float64)
features = np.delete(tpot_data.view(np.float64).reshape(tpot_data.size, -1), tpot_data.dtype.names.index('class'), axis=1)
training_features, testing_features, training_classes, testing_classes = \\
    train_test_split(features, tpot_data['class'], random_state=42)

exported_pipeline = make_pipeline(
    SelectPercentile(score_func=f_classif, percentile=65),
    DecisionTreeClassifier(criterion="gini", max_depth=7, min_samples_leaf=4, min_samples_split=18)
)

exported_pipeline.fit(training_features, training_classes)
results = exported_pipeline.predict(testing_features)
"""

    assert expected_code == export_pipeline(pipeline, tpot_obj.operators, tpot_obj._pset)


def test_score():
    """Assert that the TPOT score function raises a RuntimeError when no optimized pipeline exists."""
    tpot_obj = TPOTClassifier()
    assert_raises(RuntimeError, tpot_obj.score, testing_features, testing_classes)


def test_score_2():
    """Assert that the TPOTClassifier score function outputs a known score for a fixed pipeline."""
    tpot_obj = TPOTClassifier(random_state=34)
    known_score = 0.977777777778  # Assumes use of the TPOT accuracy function

    # Create a pipeline with a known score
    pipeline_string = (
        'KNeighborsClassifier('
        'input_matrix, '
        'KNeighborsClassifier__n_neighbors=10, '
        'KNeighborsClassifier__p=1, '
        'KNeighborsClassifier__weights=uniform'
        ')'
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features, training_classes)
    # Get score from TPOT
    score = tpot_obj.score(testing_features, testing_classes)

    assert np.allclose(known_score, score)


def test_score_3():
    """Assert that the TPOTRegressor score function outputs a known score for a fixed pipeline."""
    tpot_obj = TPOTRegressor(scoring='neg_mean_squared_error', random_state=72)
    known_score = 11.594597099  # Assumes use of mse

    # Reify pipeline with known score
    pipeline_string = (
        "ExtraTreesRegressor("
        "GradientBoostingRegressor(input_matrix, GradientBoostingRegressor__alpha=0.8,"
        "GradientBoostingRegressor__learning_rate=0.1,GradientBoostingRegressor__loss=huber,"
        "GradientBoostingRegressor__max_depth=5, GradientBoostingRegressor__max_features=0.5,"
        "GradientBoostingRegressor__min_samples_leaf=5, GradientBoostingRegressor__min_samples_split=5,"
        "GradientBoostingRegressor__n_estimators=100, GradientBoostingRegressor__subsample=0.25),"
        "ExtraTreesRegressor__bootstrap=True, ExtraTreesRegressor__max_features=0.5,"
        "ExtraTreesRegressor__min_samples_leaf=5, ExtraTreesRegressor__min_samples_split=5, "
        "ExtraTreesRegressor__n_estimators=100)"
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features_r, training_classes_r)

    # Get score from TPOT
    score = tpot_obj.score(testing_features_r, testing_classes_r)

    assert np.allclose(known_score, score)


def test_sample_weight_func():
    """Assert that the TPOTRegressor score function outputs a known score for a fixed pipeline with sample weights."""
    tpot_obj = TPOTRegressor(scoring='neg_mean_squared_error')

    # Reify pipeline with known scor
    pipeline_string = (
        "ExtraTreesRegressor("
        "GradientBoostingRegressor(input_matrix, GradientBoostingRegressor__alpha=0.8,"
        "GradientBoostingRegressor__learning_rate=0.1,GradientBoostingRegressor__loss=huber,"
        "GradientBoostingRegressor__max_depth=5, GradientBoostingRegressor__max_features=0.5,"
        "GradientBoostingRegressor__min_samples_leaf=5, GradientBoostingRegressor__min_samples_split=5,"
        "GradientBoostingRegressor__n_estimators=100, GradientBoostingRegressor__subsample=0.25),"
        "ExtraTreesRegressor__bootstrap=True, ExtraTreesRegressor__max_features=0.5,"
        "ExtraTreesRegressor__min_samples_leaf=5, ExtraTreesRegressor__min_samples_split=5, "
        "ExtraTreesRegressor__n_estimators=100)"
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features_r, training_classes_r)

    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)

    # make up a sample weight
    training_classes_r_weight = np.array(range(1, len(training_classes_r)+1))
    training_classes_r_weight_dict = set_sample_weight(tpot_obj._fitted_pipeline.steps, training_classes_r_weight)

    np.random.seed(42)
    cv_score1 = cross_val_score(tpot_obj._fitted_pipeline, training_features_r, training_classes_r, cv=3, scoring='neg_mean_squared_error')

    np.random.seed(42)
    cv_score2 = cross_val_score(tpot_obj._fitted_pipeline, training_features_r, training_classes_r, cv=3, scoring='neg_mean_squared_error')

    np.random.seed(42)
    cv_score_weight = cross_val_score(tpot_obj._fitted_pipeline, training_features_r, training_classes_r, cv=3, scoring='neg_mean_squared_error', fit_params=training_classes_r_weight_dict)

    np.random.seed(42)
    tpot_obj._fitted_pipeline.fit(training_features_r, training_classes_r, **training_classes_r_weight_dict)
    # Get score from TPOT
    known_score = 12.643383517  # Assumes use of mse
    score = tpot_obj.score(testing_features_r, testing_classes_r)

    assert np.allclose(cv_score1, cv_score2)
    assert not np.allclose(cv_score1, cv_score_weight)
    assert np.allclose(known_score, score)


def test_predict():
    """Assert that the TPOT predict function raises a RuntimeError when no optimized pipeline exists."""
    tpot_obj = TPOTClassifier()
    assert_raises(RuntimeError, tpot_obj.predict, testing_features)


def test_predict_2():
    """Assert that the TPOT predict function returns a numpy matrix of shape (num_testing_rows,)."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'DecisionTreeClassifier('
        'input_matrix, '
        'DecisionTreeClassifier__criterion=gini, '
        'DecisionTreeClassifier__max_depth=8, '
        'DecisionTreeClassifier__min_samples_leaf=5, '
        'DecisionTreeClassifier__min_samples_split=5'
        ')'
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features, training_classes)
    result = tpot_obj.predict(testing_features)

    assert result.shape == (testing_features.shape[0],)


def test_predict_proba():
    """Assert that the TPOT predict_proba function returns a numpy matrix of shape (num_testing_rows, num_testing_classes)."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'DecisionTreeClassifier('
        'input_matrix, '
        'DecisionTreeClassifier__criterion=gini, '
        'DecisionTreeClassifier__max_depth=8, '
        'DecisionTreeClassifier__min_samples_leaf=5, '
        'DecisionTreeClassifier__min_samples_split=5)'
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features, training_classes)

    result = tpot_obj.predict_proba(testing_features)
    num_labels = np.amax(testing_classes) + 1

    assert result.shape == (testing_features.shape[0], num_labels)


def test_predict_proba2():
    """Assert that the TPOT predict_proba function returns a numpy matrix filled with probabilities (float)."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'DecisionTreeClassifier('
        'input_matrix, '
        'DecisionTreeClassifier__criterion=gini, '
        'DecisionTreeClassifier__max_depth=8, '
        'DecisionTreeClassifier__min_samples_leaf=5, '
        'DecisionTreeClassifier__min_samples_split=5)'
    )
    tpot_obj._optimized_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    tpot_obj._fitted_pipeline = tpot_obj._toolbox.compile(expr=tpot_obj._optimized_pipeline)
    tpot_obj._fitted_pipeline.fit(training_features, training_classes)

    result = tpot_obj.predict_proba(testing_features)
    rows, columns = result.shape

    for i in range(rows):
        for j in range(columns):
            float_range(result[i][j])


def test_warm_start():
    """Assert that the TPOT warm_start flag stores the pop and pareto_front from the first run."""
    tpot_obj = TPOTClassifier(random_state=42, population_size=1, offspring_size=2, generations=1, verbosity=0, warm_start=True)
    tpot_obj.fit(training_features, training_classes)

    assert tpot_obj._pop is not None
    assert tpot_obj._pareto_front is not None

    first_pop = tpot_obj._pop
    tpot_obj.random_state = 21
    tpot_obj.fit(training_features, training_classes)

    assert tpot_obj._pop == first_pop


def test_fit():
    """Assert that the TPOT fit function provides an optimized pipeline."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=1,
        offspring_size=2,
        generations=1,
        verbosity=0
    )
    tpot_obj.fit(training_features, training_classes)

    assert isinstance(tpot_obj._optimized_pipeline, creator.Individual)
    assert not (tpot_obj._start_datetime is None)


def test_fit2():
    """Assert that the TPOT fit function provides an optimized pipeline when config_dict is 'TPOT light'."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=1,
        offspring_size=2,
        generations=1,
        verbosity=0,
        config_dict='TPOT light'
    )
    tpot_obj.fit(training_features, training_classes)

    assert isinstance(tpot_obj._optimized_pipeline, creator.Individual)
    assert not (tpot_obj._start_datetime is None)


def test_evaluated_individuals():
    """Assert that _evaluated_individuals stores corrent pipelines and their CV scores."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        population_size=2,
        offspring_size=4,
        generations=1,
        verbosity=0,
        config_dict='TPOT light'
    )
    tpot_obj.fit(training_features, training_classes)
    assert isinstance(tpot_obj._evaluated_individuals, dict)
    for pipeline_string in sorted(tpot_obj._evaluated_individuals.keys()):
        deap_pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
        sklearn_pipeline = tpot_obj._toolbox.compile(expr=deap_pipeline)
        tpot_obj._set_param_recursive(sklearn_pipeline.steps, 'random_state', 42)
        operator_count = tpot_obj._operator_count(deap_pipeline)
        try:
            cv_scores = cross_val_score(sklearn_pipeline, training_features, training_classes, cv=5, scoring='accuracy', verbose=0)
            mean_cv_scores = np.mean(cv_scores)
        except:
            mean_cv_scores = -float('inf')
        assert np.allclose(tpot_obj._evaluated_individuals[pipeline_string][1], mean_cv_scores)
        assert np.allclose(tpot_obj._evaluated_individuals[pipeline_string][0], operator_count)


def test_evaluate_individuals():
    """Assert that _evaluate_individuals returns operator_counts and CV scores in correct order."""
    tpot_obj = TPOTClassifier(
        random_state=42,
        verbosity=0,
        config_dict='TPOT light'
    )
    tpot_obj._pbar = tqdm(total=1, disable=True)
    pop = tpot_obj._toolbox.population(n=10)
    fitness_scores = tpot_obj._evaluate_individuals(pop, training_features, training_classes)
    for deap_pipeline, fitness_score in zip(pop, fitness_scores):
        operator_count = tpot_obj._operator_count(deap_pipeline)
        sklearn_pipeline = tpot_obj._toolbox.compile(expr=deap_pipeline)
        tpot_obj._set_param_recursive(sklearn_pipeline.steps, 'random_state', 42)
        try:
            cv_scores = cross_val_score(sklearn_pipeline, training_features, training_classes, cv=5, scoring='accuracy', verbose=0)
            mean_cv_scores = np.mean(cv_scores)
        except:
            mean_cv_scores = -float('inf')
        assert isinstance(deap_pipeline, creator.Individual)
        assert np.allclose(fitness_score[0], operator_count)
        assert np.allclose(fitness_score[1], mean_cv_scores)


def testTPOTOperatorClassFactory():
    """Assert that the TPOT operators class factory."""
    test_config_dict = {
        'sklearn.svm.LinearSVC': {
            'penalty': ["l1", "l2"],
            'loss': ["hinge", "squared_hinge"],
            'dual': [True, False],
            'tol': [1e-5, 1e-4, 1e-3, 1e-2, 1e-1],
            'C': [1e-4, 1e-3, 1e-2, 1e-1, 0.5, 1., 5., 10., 15., 20., 25.]
        },

        'sklearn.linear_model.LogisticRegression': {
            'penalty': ["l1", "l2"],
            'C': [1e-4, 1e-3, 1e-2, 1e-1, 0.5, 1., 5., 10., 15., 20., 25.],
            'dual': [True, False]
        },

        'sklearn.preprocessing.Binarizer': {
            'threshold': np.arange(0.0, 1.01, 0.05)
        }
    }

    tpot_operator_list = []
    tpot_argument_list = []

    for key in sorted(test_config_dict.keys()):
        op, args = TPOTOperatorClassFactory(key, test_config_dict[key])
        tpot_operator_list.append(op)
        tpot_argument_list += args

    assert len(tpot_operator_list) == 3
    assert len(tpot_argument_list) == 9
    assert tpot_operator_list[0].root is True
    assert tpot_operator_list[1].root is False
    assert tpot_operator_list[2].type() == "Classifier or Regressor"
    assert tpot_argument_list[1].values == [True, False]


def check_export(op, tpot_obj):
    """Assert that a TPOT operator exports as expected."""
    prng = np.random.RandomState(42)
    np.random.seed(42)

    args = []
    for type_ in op.parameter_types()[0][1:]:
        args.append(prng.choice(tpot_obj._pset.terminals[type_]).value)
    export_string = op.export(*args)

    assert export_string.startswith(op.__name__ + "(") and export_string.endswith(")")


def test_operators():
    """Assert that the TPOT operators match the output of their sklearn counterparts."""
    tpot_obj = TPOTClassifier(random_state=42)
    for op in tpot_obj.operators:
        check_export.description = ("Assert that the TPOT {} operator exports "
                                    "as expected".format(op.__name__))
        yield check_export, op, tpot_obj


def test_export():
    """Assert that TPOT's export function throws a RuntimeError when no optimized pipeline exists."""
    tpot_obj = TPOTClassifier()
    assert_raises(RuntimeError, tpot_obj.export, "test_export.py")


def test_generate_pipeline_code():
    """Assert that generate_pipeline_code() returns the correct code given a specific pipeline."""
    tpot_obj = TPOTClassifier()
    pipeline = [
        'KNeighborsClassifier',
        [
            'CombineDFs',
            [
                'GradientBoostingClassifier',
                'input_matrix',
                38.0,
                5,
                5,
                5,
                0.05,
                0.5],
            [
                'GaussianNB',
                [
                    'ZeroCount',
                    'input_matrix'
                ]
            ]
        ],
        18,
        'uniform',
        2
    ]

    expected_code = """make_pipeline(
    make_union(
        make_union(VotingClassifier([('branch',
            GradientBoostingClassifier(learning_rate=38.0, max_depth=5, max_features=5, min_samples_leaf=5, min_samples_split=0.05, n_estimators=0.5)
        )]), FunctionTransformer(copy)),
        make_union(VotingClassifier([('branch',
            make_pipeline(
                ZeroCount(),
                GaussianNB()
            )
        )]), FunctionTransformer(copy))
    ),
    KNeighborsClassifier(n_neighbors=18, p="uniform", weights=2)
)"""
    assert expected_code == generate_pipeline_code(pipeline, tpot_obj.operators)


def test_generate_import_code():
    """Assert that generate_import_code() returns the correct set of dependancies for a given pipeline."""
    tpot_obj = TPOTClassifier()
    pipeline = creator.Individual.from_string('GaussianNB(RobustScaler(input_matrix))', tpot_obj._pset)

    expected_code = """import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler

# NOTE: Make sure that the class is labeled 'class' in the data file
tpot_data = np.recfromcsv('PATH/TO/DATA/FILE', delimiter='COLUMN_SEPARATOR', dtype=np.float64)
features = np.delete(tpot_data.view(np.float64).reshape(tpot_data.size, -1), tpot_data.dtype.names.index('class'), axis=1)
training_features, testing_features, training_classes, testing_classes = \\
    train_test_split(features, tpot_data['class'], random_state=42)
"""
    assert expected_code == generate_import_code(pipeline, tpot_obj.operators)


def test_mutNodeReplacement():
    """Assert that mutNodeReplacement() returns the correct type of mutation node in a fixed pipeline."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'KNeighborsClassifier(CombineDFs('
        'DecisionTreeClassifier(input_matrix, '
        'DecisionTreeClassifier__criterion=gini, '
        'DecisionTreeClassifier__max_depth=8, '
        'DecisionTreeClassifier__min_samples_leaf=5, '
        'DecisionTreeClassifier__min_samples_split=5'
        '), '
        'SelectPercentile('
        'input_matrix, '
        'SelectPercentile__percentile=20'
        ')'
        'KNeighborsClassifier__n_neighbors=10, '
        'KNeighborsClassifier__p=1, '
        'KNeighborsClassifier__weights=uniform'
        ')'
    )

    pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    pipeline[0].ret = Output_Array
    old_ret_type_list = [node.ret for node in pipeline]
    old_prims_list = [node for node in pipeline if node.arity != 0]
    mut_ind = mutNodeReplacement(pipeline, pset=tpot_obj._pset)
    new_ret_type_list = [node.ret for node in mut_ind[0]]
    new_prims_list = [node for node in mut_ind[0] if node.arity != 0]

    if new_prims_list == old_prims_list:  # Terminal mutated
        assert new_ret_type_list == old_ret_type_list
    else:  # Primitive mutated
        diff_prims = list(set(new_prims_list).symmetric_difference(old_prims_list))
        assert diff_prims[0].ret == diff_prims[1].ret

    assert mut_ind[0][0].ret == Output_Array


def test_export_pipeline():
    """Assert that exported_pipeline() generated a compile source file as expected given a fixed pipeline."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'KNeighborsClassifier(CombineDFs('
        'DecisionTreeClassifier(input_matrix, DecisionTreeClassifier__criterion=gini, '
        'DecisionTreeClassifier__max_depth=8,DecisionTreeClassifier__min_samples_leaf=5,'
        'DecisionTreeClassifier__min_samples_split=5),SelectPercentile(input_matrix, SelectPercentile__percentile=20)'
        'KNeighborsClassifier__n_neighbors=10, '
        'KNeighborsClassifier__p=1,KNeighborsClassifier__weights=uniform'
    )

    pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    expected_code = """import numpy as np

from copy import copy
from sklearn.ensemble import VotingClassifier
from sklearn.feature_selection import SelectPercentile, f_classif
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline, make_union
from sklearn.preprocessing import FunctionTransformer
from sklearn.tree import DecisionTreeClassifier

# NOTE: Make sure that the class is labeled 'class' in the data file
tpot_data = np.recfromcsv('PATH/TO/DATA/FILE', delimiter='COLUMN_SEPARATOR', dtype=np.float64)
features = np.delete(tpot_data.view(np.float64).reshape(tpot_data.size, -1), tpot_data.dtype.names.index('class'), axis=1)
training_features, testing_features, training_classes, testing_classes = \\
    train_test_split(features, tpot_data['class'], random_state=42)

exported_pipeline = make_pipeline(
    make_union(
        make_union(VotingClassifier([('branch',
            DecisionTreeClassifier(criterion="gini", max_depth=8, min_samples_leaf=5, min_samples_split=5)
        )]), FunctionTransformer(copy)),
        SelectPercentile(score_func=f_classif, percentile=20)
    ),
    KNeighborsClassifier(n_neighbors=10, p=1, weights="uniform")
)

exported_pipeline.fit(training_features, training_classes)
results = exported_pipeline.predict(testing_features)
"""
    assert expected_code == export_pipeline(pipeline, tpot_obj.operators, tpot_obj._pset)


def test_export_pipeline_2():
    """Assert that exported_pipeline() generated a compile source file as expected given a fixed simple pipeline (only one classifier)."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'KNeighborsClassifier('
        'input_matrix, '
        'KNeighborsClassifier__n_neighbors=10, '
        'KNeighborsClassifier__p=1, '
        'KNeighborsClassifier__weights=uniform'
        ')'
    )
    pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)
    expected_code = """import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier

# NOTE: Make sure that the class is labeled 'class' in the data file
tpot_data = np.recfromcsv('PATH/TO/DATA/FILE', delimiter='COLUMN_SEPARATOR', dtype=np.float64)
features = np.delete(tpot_data.view(np.float64).reshape(tpot_data.size, -1), tpot_data.dtype.names.index('class'), axis=1)
training_features, testing_features, training_classes, testing_classes = \\
    train_test_split(features, tpot_data['class'], random_state=42)

exported_pipeline = KNeighborsClassifier(n_neighbors=10, p=1, weights="uniform")

exported_pipeline.fit(training_features, training_classes)
results = exported_pipeline.predict(testing_features)
"""
    assert expected_code == export_pipeline(pipeline, tpot_obj.operators, tpot_obj._pset)


def test_export_pipeline_3():
    """Assert that exported_pipeline() generated a compile source file as expected given a fixed simple pipeline with a preprocessor."""
    tpot_obj = TPOTClassifier()
    pipeline_string = (
        'DecisionTreeClassifier(SelectPercentile(input_matrix, SelectPercentile__percentile=20),'
        'DecisionTreeClassifier__criterion=gini, DecisionTreeClassifier__max_depth=8,'
        'DecisionTreeClassifier__min_samples_leaf=5, DecisionTreeClassifier__min_samples_split=5)'
    )
    pipeline = creator.Individual.from_string(pipeline_string, tpot_obj._pset)

    expected_code = """import numpy as np

from sklearn.feature_selection import SelectPercentile, f_classif
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.tree import DecisionTreeClassifier

# NOTE: Make sure that the class is labeled 'class' in the data file
tpot_data = np.recfromcsv('PATH/TO/DATA/FILE', delimiter='COLUMN_SEPARATOR', dtype=np.float64)
features = np.delete(tpot_data.view(np.float64).reshape(tpot_data.size, -1), tpot_data.dtype.names.index('class'), axis=1)
training_features, testing_features, training_classes, testing_classes = \\
    train_test_split(features, tpot_data['class'], random_state=42)

exported_pipeline = make_pipeline(
    SelectPercentile(score_func=f_classif, percentile=20),
    DecisionTreeClassifier(criterion="gini", max_depth=8, min_samples_leaf=5, min_samples_split=5)
)

exported_pipeline.fit(training_features, training_classes)
results = exported_pipeline.predict(testing_features)
"""
    assert expected_code == export_pipeline(pipeline, tpot_obj.operators, tpot_obj._pset)


def test_operator_export():
    """Assert that a TPOT operator can export properly with a function as a parameter to a classifier."""
    export_string = TPOTSelectPercentile.export(5)
    assert export_string == "SelectPercentile(score_func=f_classif, percentile=5)"


def test_indent():
    """Assert that indenting a multiline string by 4 spaces prepends 4 spaces before each new line."""
    multiline_string = """test
test1
test2
test3"""

    indented_multiline_string = """    test
    test1
    test2
    test3"""

    assert indented_multiline_string == _indent(multiline_string, 4)


def test_operator_type():
    """Assert that TPOT operators return their type, e.g. 'Classifier', 'Preprocessor'."""
    assert TPOTSelectPercentile.type() == "Preprocessor or Selector"


def test_get_by_name():
    """Assert that the Operator class returns operators by name appropriately."""
    tpot_obj = TPOTClassifier()
    assert get_by_name("SelectPercentile", tpot_obj.operators).__class__ == TPOTSelectPercentile.__class__


def test_gen():
    """Assert that TPOT's gen_grow_safe function returns a pipeline of expected structure."""
    tpot_obj = TPOTClassifier()

    pipeline = tpot_obj._gen_grow_safe(tpot_obj._pset, 1, 3)

    assert len(pipeline) > 1
    assert pipeline[0].ret == Output_Array


def test_positive_integer():
    """Assert that the TPOT CLI interface's integer parsing throws an exception when n < 0."""
    assert_raises(Exception, positive_integer, '-1')


def test_positive_integer_2():
    """Assert that the TPOT CLI interface's integer parsing returns the integer value of a string encoded integer when n > 0."""
    assert 1 == positive_integer('1')


def test_positive_integer_3():
    """Assert that the TPOT CLI interface's integer parsing throws an exception when n is not an integer."""
    assert_raises(Exception, positive_integer, 'foobar')


def test_float_range():
    """Assert that the TPOT CLI interface's float range returns a float with input is in 0. - 1.0."""
    assert 0.5 == float_range('0.5')


def test_float_range_2():
    """Assert that the TPOT CLI interface's float range throws an exception when input it out of range."""
    assert_raises(Exception, float_range, '2.0')


def test_float_range_3():
    """Assert that the TPOT CLI interface's float range throws an exception when input is not a float."""
    assert_raises(Exception, float_range, 'foobar')
