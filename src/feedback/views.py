"""
API views for the Feedback XBlock instructor dashboard report.
"""

import logging

from django.conf import settings
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

try:
    from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
    AUTHENTICATION_CLASSES = (JwtAuthentication, SessionAuthentication)
except ImportError:
    AUTHENTICATION_CLASSES = (SessionAuthentication,)

try:
    from lms.djangoapps.courseware.access import has_access
    from openedx.core.lib.courses import get_course_by_id
except ImportError:
    has_access = None
    get_course_by_id = None

from feedback.extensions.filters import load_blocks

log = logging.getLogger(__name__)


class CourseFeedbackView(APIView):
    """
    API endpoint returning course feedback blocks and aggregated ratings/comments for staff.
    """

    authentication_classes = AUTHENTICATION_CLASSES
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, course_id):
        """
        Return aggregated feedback data for the given course.
        """
        if not settings.FEATURES.get("ENABLE_FEEDBACK_INSTRUCTOR_VIEW", False):
            return Response(
                {"error": "Feedback instructor view is not enabled."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            return Response(
                {"error": "Invalid course ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if get_course_by_id is None or has_access is None:
            return Response(
                {"error": "Courseware service not available."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        course = get_course_by_id(course_key, depth=None)
        if not course:
            return Response(
                {"error": "Course not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not has_access(request.user, "staff", course):
            return Response(
                {"error": "User does not have permission to view feedback reports for this course."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            blocks = load_blocks(request, course)
        except Exception as exc:  # pylint: disable=broad-except
            log.exception("Error loading feedback blocks for course %s", course_id)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            "course_id": str(course_key),
            "blocks": blocks,
        })
