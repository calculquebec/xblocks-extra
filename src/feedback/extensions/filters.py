"""
Open edX Filters needed for instructor dashboard integration.
"""

import importlib.resources

from crum import get_current_request
from django.conf import settings
from django.template import Context, Template
from django.utils.translation import gettext as _
from openedx_filters import PipelineStep
from web_fragments.fragment import Fragment

try:
    from lms.djangoapps.courseware.block_render import get_block_by_usage_id, load_single_xblock
    from openedx.core.djangoapps.enrollments.data import get_user_enrollments
    from xmodule.modulestore.django import modulestore

    from feedback.utils import get_lms_link_for_item
except ImportError:
    load_single_xblock = None
    get_block_by_usage_id = None
    modulestore = None
    get_user_enrollments = None
    get_lms_link_for_item = None

TEMPLATE_ABSOLUTE_PATH = "/instructor_dashboard/"
BLOCK_CATEGORY = "feedback"
TEMPLATE_CATEGORY = "feedback_instructor"

# Tab identifier used by both the backend tab entry and the frontend route slot.
FEEDBACK_TAB_ID = "feedback"
# Placed after the platform-defined tabs (highest core sort_order is 110 for Special Exams).
FEEDBACK_TAB_SORT_ORDER = 120


class AddFeedbackTabToInstructorDashboard(PipelineStep):
    """
    Add the Course Feedback tab to the new (frontend-base) instructor dashboard.

    The legacy dashboard is extended via the ``...render.started.v1`` filter (see
    :class:`AddFeedbackTab`), which appends a server-rendered section. The new
    frontend-base instructor dashboard instead builds its navigation from the
    ``org.openedx.learning.instructor.dashboard.tabs.requested.v1`` filter, so the
    legacy step never runs there. This step registers the tab for that dashboard.

    The tab content is rendered by a frontend plugin registered in the
    ``org.openedx.frontend.slot.instructorDashboard.routes.v1`` slot for the
    ``feedback`` tab id; without that plugin the tab renders the "Page Not Found"
    fallback.
    """

    def run_filter(self, tabs, user, course_key):  # pylint: disable=unused-argument, arguments-differ
        """
        Append the Course Feedback tab to the instructor dashboard tabs list.

        Args:
            tabs (list): List of tab dicts (each with tab_id, title, url, sort_order).
            user (User): The requesting user (unused, kept for filter signature).
            course_key (CourseKey): Course key for the instructor dashboard.

        Returns:
            dict: The (possibly) modified ``tabs`` list under the ``tabs`` key.
        """
        if not settings.FEATURES.get("ENABLE_FEEDBACK_INSTRUCTOR_VIEW", False):
            return {"tabs": tabs}

        tabs.append(
            {
                "tab_id": FEEDBACK_TAB_ID,
                "title": _("Course Feedback"),
                "url": f"/instructor-dashboard/{course_key}/{FEEDBACK_TAB_ID}",
                "sort_order": FEEDBACK_TAB_SORT_ORDER,
            }
        )

        return {"tabs": tabs}


class AddFeedbackTab(PipelineStep):
    """Add forum_notifier tab to instructor dashboard by adding a new context with feedback data."""

    def run_filter(self, context, template_name):  # pylint: disable=unused-argument, arguments-differ
        """Execute filter that modifies the instructor dashboard context.
        Args:
            context (dict): the context for the instructor dashboard.
            _ (str): instructor dashboard template name.
        """
        if not settings.FEATURES.get("ENABLE_FEEDBACK_INSTRUCTOR_VIEW", False):
            return {
                "context": context,
            }

        course = context["course"]
        template = Template(self.resource_string(f"static/html/{TEMPLATE_CATEGORY}.html"))

        request = get_current_request()

        context.update(
            {
                "blocks": load_blocks(request, course),
            }
        )

        html = template.render(Context(context))
        frag = Fragment(html)
        frag.add_css(self.resource_string(f"static/css/{TEMPLATE_CATEGORY}.css"))
        frag.add_javascript(self.resource_string(f"static/js/src/{TEMPLATE_CATEGORY}.js"))

        section_data = {
            "fragment": frag,
            "section_key": TEMPLATE_CATEGORY,
            "section_display_name": "Course Feedback",
            "course_id": str(course.id),
            "template_path_prefix": TEMPLATE_ABSOLUTE_PATH,
        }
        context["sections"].append(section_data)

        return {"context": context}

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        return importlib.resources.files("feedback").joinpath(path).read_text(encoding="utf-8")


def load_blocks(request, course):
    """
    Load feedback blocks for a given course for all enrolled students.

    Arguments:
        request (HttpRequest): Django request object.
        course (CourseLocator): Course locator object.
    """
    course_id = str(course.id)

    feedback_blocks = modulestore().get_items(course.id, qualifiers={"category": BLOCK_CATEGORY})

    blocks = []

    if not feedback_blocks:
        return []

    students = get_user_enrollments(course_id).values_list("user_id", "user__username")
    for feedback_block in feedback_blocks:
        block, _ = get_block_by_usage_id(
            request,
            str(course.id),
            str(feedback_block.location),
            disable_staff_debug_info=True,
            course=course,
        )
        answers = load_xblock_answers(
            request,
            students,
            str(course.location.course_key),
            str(feedback_block.location),
            course,
        )

        vote_aggregate = []
        total_votes = 0
        total_answers = 0

        if not block.vote_aggregate:
            block.vote_aggregate = [0] * len(block.get_prompt()["scale_text"])
        for index, vote in enumerate(block.vote_aggregate):
            vote_aggregate.append(
                {
                    "scale_text": block.get_prompt()["scale_text"][index],
                    "count": vote,
                }
            )
            total_answers += vote
            # We have an inverted scale, so we need to invert the index
            # to get the correct average rating.
            # Excellent = 1, Very Good = 2, Good = 3, Fair = 4, Poor = 5
            # So Excellent = 5, Very Good = 4, Good = 3, Fair = 2, Poor = 1
            total_votes += vote * (5 - index)

        try:
            average_rating = round(total_votes / total_answers, 2)
        except ZeroDivisionError:
            average_rating = 0

        unit = block.get_parent()
        subsection = unit.get_parent()
        section = subsection.get_parent()

        blocks.append(
            {
                "display_name": block.display_name,
                "prompts": block.prompts,
                "vote_aggregate": vote_aggregate,
                "answers": answers[-10:],
                "unit_display_name": unit.display_name,
                "subsection_display_name": subsection.display_name,
                "section_display_name": section.display_name,
                "average_rating": average_rating,
                "url": get_lms_link_for_item(block.location),
            }
        )
    return blocks


def load_xblock_answers(request, students, course_id, block_id, course):
    """
    Load answers for a given feedback xblock instance.

    Arguments:
        request (HttpRequest): Django request object.
        students (list): List of enrolled students.
        course_id (str): Course ID.
        block_id (str): Block ID.
        course (CourseDescriptor): Course descriptor.
    """
    answers = []
    for user_id, username in students:
        student_xblock_instance = load_single_xblock(request, user_id, course_id, block_id, course)
        if student_xblock_instance:
            prompt = student_xblock_instance.get_prompt()
            if student_xblock_instance.user_freeform:
                if student_xblock_instance.user_vote != -1:
                    vote = prompt["scale_text"][student_xblock_instance.user_vote]
                else:
                    vote = "No vote"
                answers.append(
                    {
                        "username": username,
                        "user_vote": vote,
                        "user_freeform": student_xblock_instance.user_freeform,
                    }
                )

    return answers
