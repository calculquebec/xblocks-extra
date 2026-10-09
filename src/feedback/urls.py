"""
URLs for the feedback API.
"""

from django.urls import path

from feedback.views import CourseFeedbackView

app_name = "feedback"

urlpatterns = [
    path("v1/courses/<str:course_id>/", CourseFeedbackView.as_view(), name="course_feedback_v1"),
    path("courses/<str:course_id>/", CourseFeedbackView.as_view(), name="course_feedback"),
]
