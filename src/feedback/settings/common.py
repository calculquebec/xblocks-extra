"""
Common Django settings for eox_hooks project.
For more information on this file, see
https://docs.djangoproject.com/en/2.22/topics/settings/
For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.22/ref/settings/
"""

from feedback import ROOT_DIRECTORY

INSTALLED_APPS = [
    "feedback",
]


def plugin_settings(settings):
    """
    Set of plugin settings used by the Open Edx platform.
    More info: https://github.com/openedx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst
    """
    settings.MAKO_TEMPLATE_DIRS_BASE.append(ROOT_DIRECTORY / "templates")

    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {})

    legacy_filter_name = "org.openedx.learning.instructor.dashboard.render.started.v1"
    legacy_step = "feedback.extensions.filters.AddFeedbackTab"
    legacy_pipeline = filters_config.setdefault(legacy_filter_name, {"fail_silently": False, "pipeline": []})
    if legacy_step not in legacy_pipeline.setdefault("pipeline", []):
        legacy_pipeline["pipeline"].append(legacy_step)

    new_filter_name = "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
    new_step = "feedback.extensions.filters.AddFeedbackTabToInstructorDashboard"
    new_pipeline = filters_config.setdefault(new_filter_name, {"fail_silently": False, "pipeline": []})
    if new_step not in new_pipeline.setdefault("pipeline", []):
        new_pipeline["pipeline"].append(new_step)

    settings.OPEN_EDX_FILTERS_CONFIG = filters_config

