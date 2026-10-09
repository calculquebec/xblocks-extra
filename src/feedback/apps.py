"""
forum_email_notifier Django application initialization.
"""

from django.apps import AppConfig


class FeedbackConfig(AppConfig):
    """
    Configuration for the feedback Django application.
    """

    name = "feedback"

    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "feedback_api",
                "regex": r"^api/feedback/",
                "relative_path": "urls",
            },
        },
        "settings_config": {
            "lms.djangoapp": {
                "common": {"relative_path": "settings.common"},
                "test": {"relative_path": "settings.test"},
                "production": {"relative_path": "settings.production"},
            },
            "cms.djangoapp": {
                "common": {"relative_path": "settings.common"},
                "test": {"relative_path": "settings.test"},
                "production": {"relative_path": "settings.production"},
            },
        },
    }
