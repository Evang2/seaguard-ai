from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from seaguard.ml.feature_engineering import ML_FEATURE_COLUMNS

DEFAULT_RANDOM_STATE = 42
DEFAULT_N_ESTIMATORS = 200
DEFAULT_CONTAMINATION = "auto"


@dataclass(frozen=True)
class MLAnomalyResult:
    """
    Result produced for one AIS observation.

    anomaly_score:
        Higher values mean more anomalous behaviour.

    decision_function:
        Native Isolation Forest decision score.
        Lower values indicate more abnormal observations.

    is_anomaly:
        True when Isolation Forest predicts the observation
        as an outlier.
    """

    anomaly_score: float
    decision_function: float
    is_anomaly: bool


class AISIsolationForestDetector:
    """
    Unsupervised anomaly detector for engineered AIS features.

    The detector expects the feature columns produced by
    build_ais_features().
    """

    def __init__(
        self,
        *,
        n_estimators: int = DEFAULT_N_ESTIMATORS,
        contamination: str | float = DEFAULT_CONTAMINATION,
        random_state: int = DEFAULT_RANDOM_STATE,
    ) -> None:
        self.feature_columns = list(
            ML_FEATURE_COLUMNS,
        )

        self.pipeline = Pipeline(
            steps=[
                (
                    "imputer",
                    SimpleImputer(
                        strategy="median",
                    ),
                ),
                (
                    "detector",
                    IsolationForest(
                        n_estimators=n_estimators,
                        contamination=contamination,
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
            ],
        )

        self._is_fitted = False

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    def _prepare_features(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        missing_columns = [
            column for column in self.feature_columns if column not in dataframe.columns
        ]

        if missing_columns:
            missing = ", ".join(
                missing_columns,
            )

            raise ValueError(
                f"Missing required ML feature columns: {missing}",
            )

        features = dataframe[self.feature_columns].copy()

        for column in self.feature_columns:
            features[column] = pd.to_numeric(
                features[column],
                errors="coerce",
            )

        features = features.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        return features

    def fit(
        self,
        dataframe: pd.DataFrame,
    ) -> AISIsolationForestDetector:
        """
        Fit the Isolation Forest using engineered AIS features.
        """

        features = self._prepare_features(
            dataframe,
        )

        if len(features) < 2:
            raise ValueError(
                "At least 2 AIS observations are required "
                "to train the anomaly detector.",
            )

        if features.dropna(
            how="all",
        ).empty:
            raise ValueError(
                "Cannot train the anomaly detector because "
                "all ML feature values are missing.",
            )

        self.pipeline.fit(
            features,
        )

        self._is_fitted = True

        return self

    def score(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Score AIS observations.

        Returns the original dataframe with:

        - ml_decision_function
        - ml_anomaly_score
        - ml_is_anomaly
        """

        if not self._is_fitted:
            raise RuntimeError(
                "The anomaly detector must be fitted before scoring data.",
            )

        features = self._prepare_features(
            dataframe,
        )

        decision_function = self.pipeline.decision_function(
            features,
        )

        predictions = self.pipeline.predict(
            features,
        )

        scored = dataframe.copy()

        scored["ml_decision_function"] = decision_function

        # Isolation Forest gives lower values to
        # more abnormal observations.
        #
        # Negating the decision function makes our
        # application-facing score intuitive:
        #
        #     larger score = more anomalous
        scored["ml_anomaly_score"] = -decision_function

        scored["ml_is_anomaly"] = predictions == -1

        return scored

    def fit_score(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Fit the detector and immediately score the same dataset.
        """

        self.fit(
            dataframe,
        )

        return self.score(
            dataframe,
        )
