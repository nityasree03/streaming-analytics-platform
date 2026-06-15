"""
upgrade_prediction.py

Trains a binary classifier to predict whether a user will have an
"upgrade" or "purchase" event, based on their behavioral activity in
raw_events. This demonstrates an end-to-end ML workflow: SQL feature
engineering -> sklearn pipeline -> evaluation -> feature importance.

Business framing:
    A model like this could help a growth/sales team prioritize outreach
    to users showing behavioral patterns associated with upgrades --
    e.g. "users with high feature diversity and many feature_used events
    are X% more likely to convert; target these segments with upgrade
    campaigns."

Run with:
    python ml/upgrade_prediction.py
"""

import pandas as pd
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)

PG_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "streaming_analytics",
    "user": "streaming_user",
    "password": "streaming_pass",
}


def load_features() -> pd.DataFrame:
    """
    Build a per-user feature table from raw_events.

    Features:
        total_events       - overall activity level
        distinct_features  - breadth of feature usage (engagement depth)
        login_count        - session frequency proxy
        logout_count       - session completion proxy
        feature_used_count - core engagement metric
        plan_tier          - current subscription tier (categorical)
        country            - user's country (categorical)

    Label:
        upgraded - 1 if the user has any 'upgrade' or 'purchase' event,
                   0 otherwise
    """
    engine = create_engine(
        f"postgresql+psycopg2://{PG_CONFIG['user']}:{PG_CONFIG['password']}"
        f"@{PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']}"
    )

    query = """
        WITH user_stats AS (
            SELECT
                user_id,
                COUNT(*) AS total_events,
                COUNT(DISTINCT feature_name) AS distinct_features,
                COUNT(*) FILTER (WHERE event_type = 'login') AS login_count,
                COUNT(*) FILTER (WHERE event_type = 'logout') AS logout_count,
                COUNT(*) FILTER (WHERE event_type = 'feature_used') AS feature_used_count,
                COUNT(*) FILTER (WHERE event_type IN ('upgrade', 'purchase')) AS conversion_events
            FROM raw_events
            GROUP BY user_id
        ),
        user_tier AS (
            SELECT DISTINCT ON (user_id)
                user_id,
                plan_tier,
                country
            FROM raw_events
            ORDER BY user_id, event_timestamp DESC
        )
        SELECT
            us.user_id,
            us.total_events,
            us.distinct_features,
            us.login_count,
            us.logout_count,
            us.feature_used_count,
            ut.plan_tier,
            ut.country,
            CASE WHEN us.conversion_events > 0 THEN 1 ELSE 0 END AS upgraded
        FROM user_stats us
        JOIN user_tier ut ON ut.user_id = us.user_id
    """

    df = pd.read_sql(query, engine)
    return df


def main():
    print("Loading per-user features from raw_events...")
    df = load_features()
    print(f"Loaded {len(df)} users.")
    print(f"Upgrade rate (label balance): {df['upgraded'].mean():.2%}\n")

    # --- Feature preparation ---
    # One-hot encode categorical features (plan_tier, country)
    feature_cols = [
        "total_events",
        "distinct_features",
        "login_count",
        "logout_count",
        "feature_used_count",
    ]
    categorical_cols = ["plan_tier", "country"]

    X = pd.get_dummies(df[feature_cols + categorical_cols], columns=categorical_cols, drop_first=True)
    y = df["upgraded"]

    # --- Train/test split ---
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    # --- Scale numeric features (helps logistic regression converge) ---
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # --- Train models ---
    print("=" * 60)
    print("Logistic Regression")
    print("=" * 60)
    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_train_scaled, y_train)
    lr_preds = lr.predict(X_test_scaled)
    print_metrics(y_test, lr_preds)

    print("\n" + "=" * 60)
    print("Random Forest")
    print("=" * 60)
    rf = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
    rf.fit(X_train, y_train)
    rf_preds = rf.predict(X_test)
    print_metrics(y_test, rf_preds)

    # --- Feature importance (Random Forest) ---
    print("\n" + "=" * 60)
    print("Feature Importances (Random Forest)")
    print("=" * 60)
    importances = pd.Series(rf.feature_importances_, index=X.columns)
    importances = importances.sort_values(ascending=False)
    print(importances.head(10).to_string())

    discuss_class_imbalance(df)


def print_metrics(y_true, y_pred):
    print(f"Accuracy:  {accuracy_score(y_true, y_pred):.3f}")
    print(f"Precision: {precision_score(y_true, y_pred, zero_division=0):.3f}")
    print(f"Recall:    {recall_score(y_true, y_pred, zero_division=0):.3f}")
    print(f"F1:        {f1_score(y_true, y_pred, zero_division=0):.3f}")
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_true, y_pred))
    print("\nClassification Report:")
    print(classification_report(y_true, y_pred, zero_division=0))


def discuss_class_imbalance(df: pd.DataFrame):
    """
    Print a discussion of the class imbalance problem observed in this
    dataset, and demonstrate one standard mitigation: class_weight='balanced'.

    With a 94.6% / 5.4% label split, a naive classifier can achieve 94.6%
    accuracy by always predicting the majority class -- which is exactly
    what happened above (recall=1.0 for class 1, but 0.00 precision/recall
    for class 0). This is a common pitfall: accuracy alone is a misleading
    metric for imbalanced classification problems.

    In a real upgrade-prediction use case, the minority class (users who
    DON'T upgrade, or conversely a smaller "will upgrade" class in a less
    saturated dataset) is often the class of interest -- e.g. "find the
    free users most likely to convert." A model that can't distinguish
    this class is useless for that business goal, regardless of its
    accuracy score.
    """
    print("\n" + "=" * 60)
    print("Class Imbalance Discussion")
    print("=" * 60)
    print(
        "The dataset has a 94.6% / 5.4% label split. Both models above\n"
        "achieved ~94% 'accuracy' by predicting the majority class for\n"
        "every user -- recall for the minority class (0) is 0.00.\n"
        "Accuracy is misleading here; precision/recall/F1 per class tell\n"
        "the real story.\n"
    )
    print("Retrying Random Forest with class_weight='balanced'...\n")

    feature_cols = [
        "total_events",
        "distinct_features",
        "login_count",
        "logout_count",
        "feature_used_count",
    ]
    categorical_cols = ["plan_tier", "country"]
    X = pd.get_dummies(df[feature_cols + categorical_cols], columns=categorical_cols, drop_first=True)
    y = df["upgraded"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    rf_balanced = RandomForestClassifier(
        n_estimators=100, random_state=42, max_depth=5, class_weight="balanced"
    )
    rf_balanced.fit(X_train, y_train)
    preds = rf_balanced.predict(X_test)
    print_metrics(y_test, preds)

    print(
        "Even with class_weight='balanced', the minority class may remain\n"
        "hard to predict if the dataset genuinely lacks distinguishing\n"
        "signal (e.g. our synthetic event generator assigns event types\n"
        "largely at random, so 'upgraded' may not correlate strongly with\n"
        "the available features). In a production setting with real user\n"
        "behavior, the next steps would be: (1) collect more historical\n"
        "data to get a larger minority-class sample, (2) engineer richer\n"
        "features (e.g. time-series trends, session patterns), and\n"
        "(3) consider techniques like SMOTE oversampling or threshold\n"
        "tuning based on the business cost of false negatives vs. false\n"
        "positives."
    )
if __name__ == "__main__":

    main()
