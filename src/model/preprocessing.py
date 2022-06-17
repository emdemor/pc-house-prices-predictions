from __future__ import annotations

import numpy as np
import pandas as pd
import logging
import typing
from src.config import *
from src.base.commons import dataframe_transformer, load_pickle
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import (
    MinMaxScaler,
    StandardScaler,
    RobustScaler,
    KBinsDiscretizer,
)
from sklearn import compose
from sklearn.pipeline import Pipeline

from src.model.data import add_external_data, sanitize_features
from src.model.features import build_features, neighbors_one_hot_encode


class Identity(BaseEstimator, TransformerMixin):
    """Identity transformer"""

    def __init__(self):
        pass

    def fit(self, X, y=None):
        return self

    def transform(self, X, y=None):
        return X

    def fit_transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        self.fit(X)
        return self.transform(X)


class ColumnTransformer:
    """
    Column Transformer.

    This is a pandas dataframe based implementation of sklearn.compose.ColumnTransformer.
    This estimator allows different columns or column subsets of the input
    to be transformed separately and the features generated by each transformer
    will be concatenated to form a single feature space.
    This is useful for heterogeneous or columnar data, to combine several
    feature extraction mechanisms or transformations into a single transformer.


    Parameters
    ----------
    transformers : list of tuples
        List of (name, transformer, columns) tuples specifying the
        transformer objects to be applied to subsets of the data.
    name : str
        Like in Pipeline and FeatureUnion, this allows the transformer and
        its parameters to be set using ``set_params`` and searched in grid
        search.
    transformer : {'drop', 'passthrough'} or estimator
        Estimator must support :term:`fit` and :term:`transform`.
        Special-cased strings 'drop' and 'passthrough' are accepted as
        well, to indicate to drop the columns or to pass them through
        untransformed, respectively.
    columns :  str, array-like of str, int, array-like of int, \
            array-like of bool, slice or callable
        Indexes the data on its second axis. Integers are interpreted as
        positional columns, while strings can reference DataFrame columns
        by name.  A scalar string or int should be used where
        ``transformer`` expects X to be a 1d array-like (vector),
        otherwise a 2d array will be passed to the transformer.
        A callable is passed the input data `X` and can return any of the
        above. To select multiple columns by name or dtype, you can use
        :obj:`make_column_selector`.
    remainder : {'drop', 'passthrough'} or estimator, default='drop'
        By default, only the specified columns in `transformers` are
        transformed and combined in the output, and the non-specified
        columns are dropped. (default of ``'drop'``).
        By specifying ``remainder='passthrough'``, all remaining columns that
        were not specified in `transformers` will be automatically passed
        through. This subset of columns is concatenated with the output of
        the transformers.
        By setting ``remainder`` to be an estimator, the remaining
        non-specified columns will use the ``remainder`` estimator. The
        estimator must support :term:`fit` and :term:`transform`.
        Note that using this feature requires that the DataFrame columns
        input at :term:`fit` and :term:`transform` have identical order.
    sparse_threshold : float, default=0.3
        If the output of the different transformers contains sparse matrices,
        these will be stacked as a sparse matrix if the overall density is
        lower than this value. Use ``sparse_threshold=0`` to always return
        dense.  When the transformed output consists of all dense data, the
        stacked result will be dense, and this keyword will be ignored.
    n_jobs : int, default=None
        Number of jobs to run in parallel.
        ``None`` means 1 unless in a :obj:`joblib.parallel_backend` context.
        ``-1`` means using all processors. See :term:`Glossary <n_jobs>`
        for more details.
    transformer_weights : dict, default=None
        Multiplicative weights for features per transformer. The output of the
        transformer is multiplied by these weights. Keys are transformer names,
        values the weights.
    verbose : bool, default=False
        If True, the time elapsed while fitting each transformer will be
        printed as it is completed.
    verbose_feature_names_out : bool, default=True
        If True, :meth:`get_feature_names_out` will prefix all feature names
        with the name of the transformer that generated that feature.
        If False, :meth:`get_feature_names_out` will not prefix any feature
        names and will error if feature names are not unique.
    """

    def __init__(self, *args, **kwargs):
        self.column_transformer = compose.ColumnTransformer(*args, **kwargs)

    def fit(self, X, y=None):
        """Fit all transformers using X.
        Parameters
        ----------
        X : {array-like, dataframe} of shape (n_samples, n_features)
            Input data, of which specified subsets are used to fit the
            transformers.
        y : array-like of shape (n_samples,...), default=None
            Targets for supervised learning.
        Returns
        -------
        self : ColumnTransformer
            This estimator.
        """
        self.column_transformer.fit(X, y)
        return self

    def transform(self, X: pd.DataFrame, y: pd.Series = None):
        return dataframe_transformer(X, self.column_transformer)

    def fit_transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        self.fit(X)
        return self.transform(X)


class FeatureTransformer(BaseEstimator, TransformerMixin):
    """
    FeatureTransformer.
    
    Applies a transformation dataframe.

    Parameters
    ----------
        transformation : {'log', 'log10', 'exp', 'square',\
            'sqrt', 'identity'}, default='identity'
            A string with the decription of a transformation to be applied.
    """

    def __init__(self, transformation: str = "identity"):
        """Class constructor"""
        self.transformation = transformation
        self.transformer = self.__interpret_transformation(self.transformation)

    def fit(self, X: pd.DataFrame, y: pd.Series = None) -> FeatureTransformer:
        """Fit transformations using X.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        self : FeatureTransformer
            This estimator.
        """
        return self

    def transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Applies the transformation to the input dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """

        try:
            X = X.apply(self.transformer)

        except Exception as err:
            logging.error(err)
            raise err

        return X

    def fit_transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Fit transformations using X and return the transformed dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """

        self.fit(X)

        return self.transform(X)

    def __interpret_transformation(self, transformation: str = "identity") -> function:
        """Returns a function related to the transformation operation.

        Parameters
        ----------
        transformation : {'log', 'log10', 'exp', 'square',\
            'sqrt', 'identity'}, default='identity'
            A string with the decription of a transformation to be applied.

        Returns
        -------
        function
            A function related to the transformation operation.
        """

        if transformation == "log":
            return np.log

        elif transformation == "log10":
            return np.log10

        elif transformation == "log1p":
            return np.log1p

        elif transformation == "exp":
            return np.exp

        elif transformation == "square":
            return np.square

        elif transformation == "sqrt":
            return np.sqrt

        elif transformation == "identity":
            return lambda x: x

        else:
            raise ValueError(
                f"The value {transformation} for 'transformation' is not supported."
            )


class FeatureClipper(BaseEstimator, TransformerMixin):
    """
    FeatureClipper.

    Trim values at input threshold(s).

    Assigns values outside boundary to boundary values. Thresholds
    can be singular values or array like, and in the latter case
    the clipping is performed element-wise in the specified axis.

    Parameters
    ----------
        limits : array-like
            An array-like value with two elementes with lower and \
                higher limits to be clipped.
    """

    def __init__(self, limits: np.array or list or tuple):
        """Class cosntructor"""
        self.limits = limits

    def fit(self, X: pd.DataFrame, y: pd.Series = None) -> FeatureClipper:
        """Fit clipper using X.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        self : FeatureClipper
            This estimator.
        """
        return self

    def transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Applies the clip operation to the input dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """

        try:
            X = X.clip(*self.limits)

        except Exception as err:
            logging.error(err)
            raise err

        return X

    def fit_transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Fit clip operation using X and return the transformed dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """
        self.fit(X)

        return self.transform(X)


class FeatureImputer(BaseEstimator, TransformerMixin):
    """
    FeatureImputer.

    Treatment of missing values according to previously defined strategies.

    Parameters
    ----------
    strategy : {'mean', 'median', 'constant'}, default='mean'
        A label to the imputation strategy
    parameter : typing.Any, optional
        Parameter to complement the imputation strategy.\
            For example, if the user choose imputation\
            by a constant value, this value must be passed\
            as this parameter, by default None
    """

    def __init__(self, strategy: str = "mean", parameter: typing.Any = None):

        self.strategy = strategy

        self.parameter = parameter

        self.imputer = None

    def fit(self, X: pd.DataFrame, y: pd.Series = None) -> FeatureImputer:
        """Fit imputer using X.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        self : FeatureImputer
            This estimator.
        """

        self.imputer = self.__interpret_imputation(self.strategy, self.parameter)
        self.imputer.fit(X)
        return self

    def transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Applies the imputation operation to the input dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """
        return dataframe_transformer(X, self.imputer)

    def fit_transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Fit imputation operation using X and return the transformed dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """

        self.fit(X)

        return self.transform(X)

    def __interpret_imputation(
        self, imputation: str = "mean", param: typing.Any = None
    ) -> TransformerMixin:
        """Returns a class related to the imputation strategy.

        Parameters
        ----------
        imputation : {'mean', 'median', 'constant'}, default='mean'
            A label to the imputation strategy
        param : typing.Any, optional
            Parameter to complement the imputation strategy.\
                For example, if the user choose imputation\
                by a constant value, this value must be passed\
                as this parameter, by default None

        Returns
        -------
        TransformerMixin
            A sklearn-like transformation class.
        """

        if imputation == "mean":
            return SimpleImputer(strategy="mean")

        elif imputation == "median":
            return SimpleImputer(strategy="median")

        elif imputation == "constant":
            return SimpleImputer(strategy="constant", fill_value=param)

        else:
            return Identity()


class FeatureScaler(BaseEstimator, TransformerMixin):
    """
    FeatureScaler.

    Scales the features according to a specified strategy. \
    The current strategies supported are min_max, standard \
    and robust scaler.

    Parameters
    ----------
    strategy : {'min_max', 'standard', 'robust'}, default='min_max'
        A label to the scaling strategy.
    """

    def __init__(self, strategy: str = "min_max"):
        """Class constructor"""
        self.strategy = strategy
        self.scaler = self.__interpret_scaler(self.strategy)

    def fit(self, X: pd.DataFrame, y: pd.Series = None) -> FeatureScaler:
        """Fit scaler using X.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        self : FeatureImputer
            This estimator.
        """

        self.scaler.fit(X)

        return self

    def transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Applies the scale operation to the input dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """
        return dataframe_transformer(X, self.scaler)

    def fit_transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Fit scale operation using X and return the transformed dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """

        self.fit(X)

        return self.transform(X)

    def __interpret_scaler(self, scaler: str = "min_max") -> TransformerMixin:
        """Returns a class related to the scale strategy.

        Parameters
        ----------
        scaler : {'min_max', 'standard', 'robust'}, default='min_max'
            A label to the scaling strategy.

        Returns
        -------
        TransformerMixin
            A sklearn-like transformation class.
        """

        if scaler == "min_max":
            return MinMaxScaler()

        elif scaler == "standard":
            return StandardScaler()

        elif scaler == "robust":
            return RobustScaler()

        elif scaler == None:
            return Identity()

        else:
            return Identity()


class FeatureWeigher(BaseEstimator, TransformerMixin):
    """
    FeatureWeigher.

    Multiplies features by a specified factor.

    Parameters
    ----------
    weight : float
        Features weight.
    """

    def __init__(self, weight):
        """Class constructor"""
        self.weight = weight

    def fit(self, X: pd.DataFrame, y: pd.Series = None) -> FeatureWeigher:
        """Fit weigher using X.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        self : FeatureWeigher
            This estimator.
        """
        return self

    def transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Applies the operation to the input dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """
        for col in X.columns:
            X[col] = X[col] * self.weight

        return X

    def fit_transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Fit using X and return the transformed dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """
        self.fit(X)
        return self.transform(X)


class FeatureDiscretizer(BaseEstimator, TransformerMixin):
    """
    FeatureDiscretizer.

    Discretize features according to previously defined strategies.

    Parameters
    ----------
    strategy : {'uniform', 'quantile', 'kmeans'}, default='uniform'
        A label to the discretize strategy
    n_bins : int, default=5
        The number of bins, by default 5
    """

    def __init__(self, n_bins: int = 5, strategy: str = "uniform"):

        self.strategy = strategy
        self.value_maps = None
        self.n_bins = n_bins
        self.discretizer = KBinsDiscretizer(
            encode="ordinal", strategy=self.strategy, n_bins=self.n_bins
        )

    def fit(self, X: pd.DataFrame, y: pd.Series = None) -> FeatureDiscretizer:
        """Fit discretizer using X.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        self : FeatureDiscretizer
            This estimator.
        """

        self.discretizer.fit(X)

        self.__train_value_maps(X)

        return self

    def transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Applies the operation to the input dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """
        X_result = dataframe_transformer(X, self.discretizer)

        X_result = self.__apply_value_maps(X_result)

        return X_result

    def fit_transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Fit using X and return the transformed dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """
        self.fit(X)
        return self.transform(X)

    def __train_value_maps(self, X: pd.DataFrame) -> None:
        """Fit the mean feature value in each discretized bin.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        """

        X_transf = self.discretizer.transform(X)

        self.value_maps = []

        for i in range(X_transf.shape[1]):

            # TODO
            # Here, I am using aggregation by mean.It will be great
            # If the user could choose the aggregation operation
            # as an inputparameter.
            subs = (
                pd.DataFrame({"order": X_transf[:, i], "value": X.iloc[:, i].values})
                .groupby("order")
                .mean()
                .to_dict()["value"]
            )

            self.value_maps.append(subs)

    def __apply_value_maps(self, X_transf: pd.DataFrame):
        """Apply de substitution of the bin order by\
        the fitted mean value in each discretized bin.

        Parameters
        ----------
        X_transf : pd.DataFrame
            Input data of shape (n_samples, n_features).
        """

        temp_columns = {}

        columns = X_transf.columns

        for i in range(X_transf.shape[1]):
            subs = self.value_maps[i]
            temp_columns.update(
                {columns[i]: pd.Series(X_transf.iloc[:, i]).replace(subs)}
            )

        X_result = pd.DataFrame(temp_columns)

        return X_result


class PreProcessor(BaseEstimator, TransformerMixin):
    def __repr__(self):
        return "PreProcessor()"

    def __init__(self, features_config):
        """Class constructor"""

        self.features_config = features_config

        self.feature_names = None

        self.feature_active = None

        self.feature_types = None

    def fit(self, X: pd.DataFrame, y: pd.Series = None) -> PreProcessor:
        """Fit preprocessor using X.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        self : PreProcessor
            This estimator.
        """

        self.__interpret_config()

        action_plan = self.__create_action_plan()

        self.preprocessor = self.__set_preprocessor(action_plan)

        features = self.__get_active_features()

        self.preprocessor.fit(X[features], y)

        return self

    def transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Applies the operation to the input dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """

        features = self.__get_active_features()

        X_transf = dataframe_transformer(X[features], self.preprocessor)

        X_transf = self.__cast_columns(X_transf)

        return X_transf

    def fit_transform(self, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
        """Fit using X and return the transformed dataframe.

        Parameters
        ----------
        X : pd.DataFrame
            Input data of shape (n_samples, n_features).
        y : pd.Series, optional
            Targets for supervised learning, by default None

        Returns
        -------
        pd.DataFrame
            The transformed dataframe.
        """
        self.fit(X)
        return self.transform(X)

    def __interpret_config(self) -> None:

        for config in self.features_config:
            if "active" not in config:
                config.update({"active": True})

        self.feature_names = [config["name"] for config in self.features_config]

        self.feature_active = {
            config["name"]: config["active"] for config in self.features_config
        }

        self.feature_types = {
            config["name"]: config["type"] for config in self.features_config
        }

    def __create_action_plan(self):
        """
        Generates a dataframe with ordered steps to be\
        executed on the Pipeline.
        """
        df = pd.DataFrame(
            [
                (j, config["name"], config["active"], config["type"], i, k, config[k])
                for j, config in enumerate(self.features_config)
                for i, k in enumerate(
                    {
                        k: config[k]
                        for k in filter(
                            lambda x: x
                            not in (
                                "name",
                                "active",
                                "type",
                                "encode",
                                "polynomial_degree",
                            ),
                            config.keys(),
                        )
                    }
                )
            ],
            columns=[
                "feature_order",
                "feature_name",
                "active",
                "type",
                "transform_order",
                "key",
                "value",
            ],
        )

        for order in df["transform_order"].unique():
            for col in self.feature_names:
                if (
                    len(
                        df[
                            (df["feature_name"] == col)
                            & (df["transform_order"] == order)
                        ]
                    )
                    == 0
                ):
                    df = pd.concat(
                        [
                            df,
                            pd.DataFrame(
                                [
                                    {
                                        "feature_order": self.feature_names.index(col),
                                        "feature_name": col,
                                        "active": self.feature_active[col],
                                        "type": self.feature_types[col],
                                        "transform_order": order,
                                        "key": "transformation",
                                        "value": "identity",
                                    }
                                ]
                            ),
                        ]
                    )

        df = df.sort_values(["transform_order", "feature_order"])

        return df

    def __set_preprocessor(self, action_plan: pd.DataFrame):
        """
        Gets the action plan a generates a Pipeline.

        Parameters
        ----------
        action_plan : pd.DataFrame
            A dataframe with ordered steps to be\
            executed on the Pipeline.
        """
        steps = []

        for transform_order in action_plan["transform_order"].unique():

            df_step = action_plan[
                action_plan["transform_order"] == transform_order
            ].sort_values("feature_order")

            transformers = [
                (n, self.__interpret_process_step(key, value, tp), [o])
                for n, o, key, value, tp in df_step[
                    ["feature_name", "feature_order", "key", "value", "type"]
                ].to_numpy()
            ]

            steps.append(
                (
                    f"step_{transform_order}",
                    ColumnTransformer(transformers=transformers),
                )
            )

        if len(steps) > 0:
            preprocessor = Pipeline(steps=steps)
        else:
            preprocessor = Pipeline(steps=[("step_0", Identity())])

        return preprocessor

    def __get_active_features(self):
        return [
            x[0]
            for x in filter(
                lambda x: x[1],
                [(k, self.feature_active[k]) for k in self.feature_active],
            )
        ]

    def __interpret_process_step(self, key, value, type_):
        if key == "transformation":
            return FeatureTransformer(transformation=value)

        elif key == "limits":
            return FeatureClipper(limits=value)

        elif key == "imputation_strategy":

            strategy, *param = str(value).split(":")

            if strategy == "constant":
                if type_ in ["string", "str", "object"]:
                    param = param[0]
                else:
                    param = float(param[0])
            else:
                param = None

            return FeatureImputer(strategy="constant", parameter=param)

        elif key == "discretizer":

            strategy, n_bins = str(value).split(":")

            n_bins = int(n_bins)

            return FeatureDiscretizer(n_bins=n_bins, strategy=strategy)

        elif key == "scaler":
            return FeatureScaler(strategy=value)

        elif key == "weight":
            return FeatureWeigher(weight=value)

        else:
            print(f"[error] KeyError. {key} not found.")
            return Identity()

    def __cast_columns(self, X):

        for column in self.feature_types:

            type_ = self.feature_types[column]

            if "int" in type_.lower():
                X[column] = X[column].round(0).astype(type_)

            else:
                X[column] = X[column].astype(type_)

        return X


def apply_preprocess(preprocessor: PreProcessor, X: pd.DataFrame):

    X = preprocessor.transform(X)

    X = neighbors_one_hot_encode(X)

    return X


def preprocess_transform(features: dict):

    data_config = get_config(filename="config/filepaths.yaml")

    preprocessor = load_pickle(data_config["model_preprocessor_path"])

    X = pd.DataFrame([features])
    X = sanitize_features(X)
    X = add_external_data(X, data_config)

    X = build_features(X)
    X = apply_preprocess(preprocessor, X)

    return X


def get_preprocessor():
    filepaths = get_config(filename="config/filepaths.yaml")
    preprocessor = load_pickle(filepaths["model_preprocessor_path"])
    return preprocessor